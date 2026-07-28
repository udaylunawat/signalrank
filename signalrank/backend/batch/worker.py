import asyncio
import inspect
import logging
import math
import socket
import uuid
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.config import is_desktop_mode, settings
from api.deps_llm import get_llm_client
from api.models import JobResult, Profile, Run, RunSourceTelemetry
from batch.company_enrichment import enrich_company_reputations
from batch.ingest import refresh_job_catalog
from batch.job_enrichment import enrich_job_postings
from batch.ranker import score_jobs_for_user

logger = logging.getLogger(__name__)

LEASE_SECONDS = 300
HEARTBEAT_SECONDS = 30
POLL_SECONDS = 2

_queue: asyncio.Queue | None = None


def get_queue() -> asyncio.Queue:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue(maxsize=100)
    return _queue


def wake_worker() -> None:
    queue = get_queue()
    try:
        queue.put_nowait(None)
    except asyncio.QueueFull:
        pass


def _now() -> datetime:
    return datetime.now(UTC)


def _worker_id() -> str:
    return f"{socket.gethostname()}:{uuid.uuid4().hex[:12]}"


async def _claim_next_run(
    session_factory: async_sessionmaker,
    owner: str,
) -> tuple[str, str] | None:
    now = _now()
    async with session_factory() as db:
        sqlite = db.get_bind().dialect.name == "sqlite"
        if sqlite:
            await db.execute(text("BEGIN IMMEDIATE"))
        statement = (
            select(Run)
            .where(
                or_(
                    Run.status == "pending",
                    (Run.status == "running")
                    & or_(Run.lease_expires_at.is_(None), Run.lease_expires_at < now),
                )
            )
            .order_by(Run.started_at.asc())
            .limit(1)
        )
        if not sqlite:
            statement = statement.with_for_update(skip_locked=True)
        result = await db.execute(statement)
        run = result.scalar_one_or_none()
        if run is None:
            await db.rollback()
            return None

        run.status = "running"
        run.stage = "starting"
        run.progress = max(run.progress or 0, 2)
        run.error_summary = None
        run.lease_owner = owner
        run.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
        run.heartbeat_at = now
        run.attempt_count = (run.attempt_count or 0) + 1
        await db.commit()
        return run.id, run.user_id


async def _claim_run(
    run_id: str,
    session_factory: async_sessionmaker,
    owner: str,
) -> tuple[str, str] | None:
    now = _now()
    async with session_factory() as db:
        sqlite = db.get_bind().dialect.name == "sqlite"
        if sqlite:
            await db.execute(text("BEGIN IMMEDIATE"))
        statement = select(Run).where(Run.id == run_id)
        if not sqlite:
            statement = statement.with_for_update(skip_locked=True)
        result = await db.execute(statement)
        run = result.scalar_one_or_none()
        if run is None or run.status not in {"pending", "running"}:
            await db.rollback()
            return None
        if (
            run.status == "running"
            and run.lease_expires_at is not None
            and run.lease_expires_at >= now
            and run.lease_owner != owner
        ):
            await db.rollback()
            return None

        run.status = "running"
        run.stage = "starting"
        run.progress = max(run.progress or 0, 2)
        run.error_summary = None
        run.lease_owner = owner
        run.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
        run.heartbeat_at = now
        run.attempt_count = (run.attempt_count or 0) + 1
        await db.commit()
        return run.id, run.user_id


async def _heartbeat(
    run_id: str,
    owner: str,
    session_factory: async_sessionmaker,
) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        now = _now()
        async with session_factory() as db:
            await db.execute(
                update(Run)
                .where(
                    Run.id == run_id,
                    Run.status == "running",
                    Run.lease_owner == owner,
                )
                .values(
                    heartbeat_at=now,
                    lease_expires_at=now + timedelta(seconds=LEASE_SECONDS),
                )
            )
            await db.commit()


async def _update_progress(
    db: AsyncSession,
    run_id: str,
    owner: str,
    stage: str,
    progress: int,
) -> None:
    await db.execute(
        update(Run)
        .where(Run.id == run_id, Run.lease_owner == owner)
        .values(stage=stage, progress=progress)
    )
    await db.commit()


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    parsed = float(value)
    return None if math.isnan(parsed) else parsed


def _optional_text(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return str(value)


def _catalog_count(result: Any) -> int:
    if isinstance(result, int):
        return result
    for name in (
        "jobs_persisted",
        "count",
        "persisted",
        "unique_jobs",
        "total",
    ):
        value = _field(result, name)
        if value is not None:
            return int(value)
    return 0


def _catalog_reports(result: Any) -> list[Any]:
    reports = _field(result, "reports", [])
    return list(reports or [])


def _as_datetime(value: Any, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    return fallback


def _summarize_source_errors(reports: list[Any]) -> str | None:
    sources: dict[str, dict[str, Any]] = {}
    for report in reports:
        source = str(_field(report, "source", "source"))
        summary = sources.setdefault(source, {"completed": False, "errors": []})
        status = _field(report, "status", "success")
        if status not in {"partial", "failed", "error"}:
            summary["completed"] = True
            continue
        if status == "partial" and int(_field(report, "jobs_found", 0) or 0) > 0:
            summary["completed"] = True
            continue
        query = _field(report, "query")
        error = str(_field(report, "error_summary") or "source did not complete")
        label = f"{source} ({query})" if query else source
        summary["errors"].append(f"{label}: {error}")

    errors = [
        error
        for summary in sources.values()
        if not summary["completed"]
        for error in summary["errors"]
    ]
    if not errors:
        return None
    return "; ".join(errors)[:2000]


async def _persist_source_telemetry(
    db: AsyncSession,
    run_id: str,
    catalog_result: Any,
    fallback_started_at: datetime,
) -> list[Any]:
    reports = _catalog_reports(catalog_result)
    await db.execute(
        delete(RunSourceTelemetry).where(RunSourceTelemetry.run_id == run_id)
    )

    if not reports:
        now = _now()
        reports = [
            {
                "source": "catalog",
                "status": "success",
                "jobs_found": _catalog_count(catalog_result),
                "jobs_persisted": _catalog_count(catalog_result),
                "started_at": fallback_started_at,
                "finished_at": now,
                "duration_ms": int((now - fallback_started_at).total_seconds() * 1000),
            }
        ]

    for report in reports:
        finished_at = _as_datetime(_field(report, "finished_at"), _now())
        started_at = _as_datetime(_field(report, "started_at"), fallback_started_at)
        duration_ms = _field(report, "duration_ms")
        if duration_ms is None:
            duration_ms = max(0, int((finished_at - started_at).total_seconds() * 1000))
        db.add(
            RunSourceTelemetry(
                run_id=run_id,
                source=str(_field(report, "source", "unknown"))[:100],
                query=(
                    str(query)[:500] if (query := _field(report, "query")) else None
                ),
                location=(
                    str(location)[:255]
                    if (location := _field(report, "location"))
                    else None
                ),
                status=str(_field(report, "status", "success"))[:50],
                jobs_found=int(_field(report, "jobs_found", 0) or 0),
                jobs_persisted=int(_field(report, "jobs_persisted", 0) or 0),
                duration_ms=int(duration_ms),
                error_summary=(
                    str(error)[:2000]
                    if (error := _field(report, "error_summary"))
                    else None
                ),
                started_at=started_at,
                finished_at=finished_at,
            )
        )
    await db.commit()
    return reports


async def _execute_claimed_run(
    run_id: str,
    user_id: str,
    owner: str,
    session_factory: async_sessionmaker,
) -> None:
    heartbeat_task = asyncio.create_task(
        _heartbeat(run_id, owner, session_factory),
        name=f"signalrank-heartbeat-{run_id}",
    )
    try:
        async with session_factory() as db:
            await _update_progress(db, run_id, owner, "loading_profile", 5)
            profile_result = await db.execute(
                select(Profile).where(Profile.user_id == user_id)
            )
            profile = profile_result.scalar_one_or_none()
            resume_text = profile.resume_text if profile else ""
            distilled_text = profile.distilled_text if profile else None
            resume_skills = (
                list(profile.skills)
                if profile and isinstance(profile.skills, list)
                else None
            )
            config_overrides = (
                deepcopy(profile.config_overrides or {}) if profile else {}
            )
            overrides = config_overrides
            roles = overrides.get("profile_intent", {}).get("roles")
            if not roles and profile:
                roles = profile.target_roles
                if roles:
                    overrides.setdefault("profile_intent", {})["roles"] = roles
            locations = overrides.get("scraping", {}).get("locations")
            if not locations and profile:
                locations = profile.preferred_locations
            if profile and profile.max_yoe is not None:
                overrides.setdefault("experience", {})["max_yoe"] = profile.max_yoe

            await _update_progress(db, run_id, owner, "discovering_jobs", 10)
            ingest_started_at = _now()
            ingestion_error = None
            try:
                kwargs: dict[str, Any] = {"roles": roles}
                if "locations" in inspect.signature(refresh_job_catalog).parameters:
                    kwargs["locations"] = locations
                catalog_result = await refresh_job_catalog(db, **kwargs)
                logger.info(
                    "Refreshed job catalog: %d jobs", _catalog_count(catalog_result)
                )
            except Exception as exc:
                logger.exception("Job catalog refresh failed; ranking cached jobs")
                await db.rollback()
                ingestion_error = f"Catalog refresh failed: {type(exc).__name__}: {exc}"
                catalog_result = {
                    "count": 0,
                    "reports": [
                        {
                            "source": "catalog",
                            "status": "failed",
                            "jobs_found": 0,
                            "jobs_persisted": 0,
                            "error_summary": ingestion_error,
                            "started_at": ingest_started_at,
                            "finished_at": _now(),
                        }
                    ],
                }

            reports = await _persist_source_telemetry(
                db, run_id, catalog_result, ingest_started_at
            )
            source_error = _summarize_source_errors(reports)

            await _update_progress(db, run_id, owner, "assessing_companies", 50)
            try:
                enrichment_task = enrich_company_reputations(
                    db,
                    get_llm_client(),
                    max_companies=(
                        settings.desktop_company_enrichment_limit
                        if is_desktop_mode()
                        else None
                    ),
                )
                enrichment = await asyncio.wait_for(
                    enrichment_task,
                    timeout=(
                        settings.desktop_company_enrichment_timeout_seconds
                        if is_desktop_mode()
                        else settings.company_enrichment_timeout_seconds
                    ),
                )
                logger.info(
                    "Company reputation enrichment: %d assessed, %d unknown, %d cached (%s)",
                    enrichment.assessed,
                    enrichment.unknown,
                    enrichment.cached,
                    enrichment.status,
                )
            except TimeoutError:
                logger.warning(
                    "Company reputation enrichment exceeded the time budget; "
                    "continuing with deterministic ranking"
                )
                await db.rollback()
            except Exception:
                logger.exception(
                    "Company reputation enrichment failed; ranking without new assessments"
                )
                await db.rollback()

            await _update_progress(db, run_id, owner, "assessing_listings", 55)
            try:
                listing_enrichment = await asyncio.wait_for(
                    enrich_job_postings(
                        db,
                        get_llm_client(),
                        max_jobs=(
                            settings.desktop_job_enrichment_limit
                            if is_desktop_mode()
                            else settings.job_enrichment_limit
                        ),
                    ),
                    timeout=(
                        settings.desktop_job_enrichment_timeout_seconds
                        if is_desktop_mode()
                        else settings.job_enrichment_timeout_seconds
                    ),
                )
                logger.info(
                    "Job enrichment: %d assessed, %d unavailable, %d cached (%s)",
                    listing_enrichment.assessed,
                    listing_enrichment.unavailable,
                    listing_enrichment.cached,
                    listing_enrichment.status,
                )
            except TimeoutError:
                logger.warning(
                    "Job enrichment exceeded the time budget; "
                    "continuing with neutral listing assessments"
                )
                await db.rollback()
            except Exception:
                logger.exception(
                    "Job enrichment failed; ranking without new listing assessments"
                )
                await db.rollback()

            await _update_progress(db, run_id, owner, "ranking_jobs", 60)
            ranked_df = await score_jobs_for_user(
                db=db,
                user_id=user_id,
                resume_text=resume_text,
                distilled_text=distilled_text,
                resume_skills=resume_skills,
                config_overrides=config_overrides,
            )

            await _update_progress(db, run_id, owner, "saving_results", 90)
            await db.execute(delete(JobResult).where(JobResult.run_id == run_id))
            for _, row in ranked_df.iterrows():
                db.add(
                    JobResult(
                        run_id=run_id,
                        user_id=user_id,
                        job_id=row["id"],
                        semantic_score=float(row.get("semantic_score", 0)),
                        skills_score=float(row.get("skills_score", 0)),
                        company_score=float(row.get("company_score", 0)),
                        seniority_score=float(row.get("seniority_score_dim", 0)),
                        location_score=float(row.get("location_score", 0)),
                        recency_score=float(row.get("recency_score", 0)),
                        final_score=float(row.get("final_score", 0)),
                        company_tier=str(row.get("company_tier", "")),
                        company_reputation_confidence=_optional_float(
                            row.get("company_reputation_confidence")
                        ),
                        company_reputation_rationale=_optional_text(
                            row.get("company_reputation_rationale")
                        ),
                        explanation=row.get("explanation"),
                        is_contract=bool(row.get("is_contract", False)),
                    )
                )

            status = "partial" if ingestion_error or source_error else "success"
            error_summary = source_error or ingestion_error
            await db.execute(
                update(Run)
                .where(Run.id == run_id, Run.lease_owner == owner)
                .values(
                    status=status,
                    stage="complete",
                    progress=100,
                    finished_at=_now(),
                    job_count=len(ranked_df),
                    error_summary=error_summary,
                    lease_owner=None,
                    lease_expires_at=None,
                )
            )
            await db.commit()
            logger.info(
                "Run %s completed with status %s: %d results",
                run_id,
                status,
                len(ranked_df),
            )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Run %s failed", run_id)
        async with session_factory() as db:
            await db.execute(
                update(Run)
                .where(Run.id == run_id, Run.lease_owner == owner)
                .values(
                    status="failed",
                    stage="failed",
                    progress=100,
                    error_summary=f"{type(exc).__name__}: {exc}"[:2000],
                    finished_at=_now(),
                    lease_owner=None,
                    lease_expires_at=None,
                )
            )
            await db.commit()
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass


async def process_run(
    run_id: str,
    user_id: str,
    session_factory: async_sessionmaker,
) -> None:
    owner = _worker_id()
    claimed = await _claim_run(run_id, session_factory, owner)
    if claimed is None:
        return
    _, claimed_user_id = claimed
    if claimed_user_id != user_id:
        logger.warning("Run %s user mismatch; processing persisted owner", run_id)
    await _execute_claimed_run(run_id, claimed_user_id, owner, session_factory)


async def worker_loop(session_factory: async_sessionmaker) -> None:
    queue = get_queue()
    owner = _worker_id()
    logger.info("Durable background worker started as %s", owner)
    while True:
        try:
            claimed = await _claim_next_run(session_factory, owner)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Worker %s could not claim a run", owner)
            await asyncio.sleep(POLL_SECONDS)
            continue
        if claimed is not None:
            run_id, user_id = claimed
            await _execute_claimed_run(run_id, user_id, owner, session_factory)
            continue

        try:
            await asyncio.wait_for(queue.get(), timeout=POLL_SECONDS)
        except TimeoutError:
            continue
        else:
            queue.task_done()

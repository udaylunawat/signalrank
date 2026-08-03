import csv
import json
from io import StringIO
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from api.database import get_db
from api.deps import get_current_user
from api.models import JobFeedback, JobRaw, JobResult, Run, User

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

CSV_COLUMNS = (
    "run_id",
    "run_completed_at",
    "job_id",
    "title",
    "company",
    "location",
    "source",
    "job_url",
    "date_posted",
    "description",
    "final_score",
    "semantic_score",
    "skills_score",
    "company_score",
    "seniority_score",
    "location_score",
    "recency_score",
    "company_tier",
    "company_reputation_confidence",
    "company_reputation_rationale",
    "score_explanation_json",
    "is_contract",
)


async def _latest_completed_run(db: AsyncSession, user_id: str) -> Run | None:
    result = await db.execute(
        select(Run)
        .where(Run.user_id == user_id, Run.status.in_(("success", "partial")))
        .order_by(Run.finished_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _job_payload(
    result: JobResult,
    job: JobRaw,
    feedback: dict[str, str | None] | None,
    *,
    include_description: bool = False,
) -> dict[str, Any]:
    payload = {
        "id": job.id,
        "job_url": job.job_url,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "site": job.site,
        "date_posted": str(job.date_posted) if job.date_posted else None,
        "final_score": result.final_score,
        "semantic_score": result.semantic_score,
        "skills_score": result.skills_score,
        "company_score": result.company_score,
        "seniority_score": result.seniority_score,
        "location_score": result.location_score,
        "recency_score": result.recency_score,
        "company_tier": result.company_tier,
        "company_reputation_confidence": result.company_reputation_confidence,
        "company_reputation_rationale": result.company_reputation_rationale,
        "explanation": result.explanation,
        "is_contract": result.is_contract,
        "feedback": feedback,
    }
    if include_description:
        payload["description"] = job.description
    return payload


def _safe_csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _csv_line(values: Any, *, bom: bool = False) -> str:
    output = StringIO(newline="")
    csv.writer(output).writerow(_safe_csv_value(value) for value in values)
    return ("\ufeff" if bom else "") + output.getvalue()


@router.get("")
async def list_jobs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    q: str | None = Query(None, max_length=200),
    min_score: float | None = Query(None, ge=0, le=100),
    source: str | None = Query(None, max_length=100),
    sort: Literal["match", "newest", "company"] = Query("match"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    run = await _latest_completed_run(db, current_user.id)
    if not run:
        return {
            "jobs": [],
            "total": 0,
            "page": page,
            "limit": limit,
            "run_id": None,
            "completed_at": None,
            "strong_count": 0,
            "source_counts": {},
        }

    filters = [
        JobResult.run_id == run.id,
        JobResult.user_id == current_user.id,
    ]
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                JobRaw.title.ilike(pattern),
                JobRaw.company.ilike(pattern),
                JobRaw.location.ilike(pattern),
            )
        )
    if min_score is not None:
        filters.append(JobResult.final_score >= min_score)
    if source:
        filters.append(func.lower(JobRaw.site) == source.strip().lower())

    total_result = await db.execute(
        select(func.count())
        .select_from(JobResult)
        .join(JobRaw, JobResult.job_id == JobRaw.id)
        .where(*filters)
    )
    total = total_result.scalar()

    strong_result = await db.execute(
        select(func.count()).where(
            JobResult.run_id == run.id,
            JobResult.user_id == current_user.id,
            JobResult.final_score >= 70,
        )
    )
    strong_count = strong_result.scalar() or 0

    sources_result = await db.execute(
        select(JobRaw.site, func.count())
        .select_from(JobResult)
        .join(JobRaw, JobResult.job_id == JobRaw.id)
        .where(JobResult.run_id == run.id, JobResult.user_id == current_user.id)
        .group_by(JobRaw.site)
    )
    source_counts = {
        str(site or "unknown"): count for site, count in sources_result.all()
    }

    if sort == "newest":
        ordering = (JobRaw.date_posted.desc().nullslast(), JobResult.final_score.desc())
    elif sort == "company":
        ordering = (JobRaw.company.asc().nullslast(), JobResult.final_score.desc())
    else:
        ordering = (JobResult.final_score.desc(), JobRaw.date_posted.desc().nullslast())

    results = await db.execute(
        select(JobResult, JobRaw)
        .join(JobRaw, JobResult.job_id == JobRaw.id)
        .options(
            load_only(
                JobResult.final_score,
                JobResult.semantic_score,
                JobResult.skills_score,
                JobResult.company_score,
                JobResult.seniority_score,
                JobResult.location_score,
                JobResult.recency_score,
                JobResult.company_tier,
                JobResult.company_reputation_confidence,
                JobResult.company_reputation_rationale,
                JobResult.explanation,
                JobResult.is_contract,
            ),
            load_only(
                JobRaw.id,
                JobRaw.job_url,
                JobRaw.title,
                JobRaw.company,
                JobRaw.location,
                JobRaw.site,
                JobRaw.date_posted,
            ),
        )
        .where(*filters)
        .order_by(*ordering)
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = results.all()
    feedback_result = await db.execute(
        select(JobFeedback.job_id, JobFeedback.value, JobFeedback.reason).where(
            JobFeedback.user_id == current_user.id,
            JobFeedback.job_id.in_([job.id for _, job in rows]),
        )
    )
    feedback_by_job = {
        job_id: {"value": value, "reason": reason}
        for job_id, value, reason in feedback_result.all()
    }

    jobs = [
        _job_payload(result, job, feedback_by_job.get(job.id)) for result, job in rows
    ]

    return {
        "jobs": jobs,
        "total": total,
        "page": page,
        "limit": limit,
        "run_id": run.id,
        "completed_at": str(run.finished_at) if run.finished_at else None,
        "strong_count": strong_count,
        "source_counts": source_counts,
    }


@router.get("/export.csv")
async def export_jobs_csv(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    run = await _latest_completed_run(db, current_user.id)

    async def rows():
        yield _csv_line(CSV_COLUMNS, bom=True)
        if not run:
            return

        results = await db.stream(
            select(JobResult, JobRaw)
            .join(JobRaw, JobResult.job_id == JobRaw.id)
            .where(
                JobResult.run_id == run.id,
                JobResult.user_id == current_user.id,
            )
            .order_by(
                JobResult.final_score.desc().nullslast(),
                JobRaw.date_posted.desc().nullslast(),
            )
            .execution_options(yield_per=100)
        )
        completed_at = run.finished_at.isoformat() if run.finished_at else ""
        async for result, job in results:
            yield _csv_line(
                (
                    run.id,
                    completed_at,
                    job.id,
                    job.title,
                    job.company,
                    job.location,
                    job.site,
                    job.job_url,
                    job.date_posted.isoformat() if job.date_posted else "",
                    job.description,
                    result.final_score,
                    result.semantic_score,
                    result.skills_score,
                    result.company_score,
                    result.seniority_score,
                    result.location_score,
                    result.recency_score,
                    result.company_tier,
                    result.company_reputation_confidence,
                    result.company_reputation_rationale,
                    (
                        json.dumps(
                            result.explanation, ensure_ascii=False, sort_keys=True
                        )
                        if result.explanation
                        else ""
                    ),
                    result.is_contract,
                )
            )

    date_suffix = (
        run.finished_at.date().isoformat()
        if run and run.finished_at
        else "no-completed-run"
    )
    return StreamingResponse(
        rows(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="signalrank-jobs-{date_suffix}.csv"'
            )
        },
    )


@router.get("/{job_id}")
async def get_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    run = await _latest_completed_run(db, current_user.id)
    if not run:
        raise HTTPException(status_code=404, detail="Job not found")
    row_result = await db.execute(
        select(JobResult, JobRaw)
        .join(JobRaw, JobResult.job_id == JobRaw.id)
        .where(
            JobResult.run_id == run.id,
            JobResult.user_id == current_user.id,
            JobResult.job_id == job_id,
        )
    )
    row = row_result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    job_result, job = row
    feedback_result = await db.execute(
        select(JobFeedback.value, JobFeedback.reason).where(
            JobFeedback.user_id == current_user.id,
            JobFeedback.job_id == job.id,
        )
    )
    feedback = feedback_result.one_or_none()
    feedback_payload = (
        {"value": feedback.value, "reason": feedback.reason} if feedback else None
    )
    return _job_payload(
        job_result,
        job,
        feedback_payload,
        include_description=True,
    ) | {
        "run_id": run.id,
        "completed_at": str(run.finished_at) if run.finished_at else None,
    }

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pandas as pd
from api.models import Profile, Run, RunSourceTelemetry, User
from batch import worker
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker


async def _create_user_and_run(db, *, status="pending", lease_expires_at=None):
    user = User(email=f"worker-{status}@test.com", password_hash="hash")
    db.add(user)
    await db.flush()
    db.add(Profile(user_id=user.id, resume_text="AI platform engineer"))
    run = Run(
        user_id=user.id,
        status=status,
        lease_expires_at=lease_expires_at,
        lease_owner="dead-worker" if status == "running" else None,
    )
    db.add(run)
    await db.commit()
    return user, run


async def test_claim_next_run_recovers_expired_lease(db, test_engine):
    user, run = await _create_user_and_run(
        db,
        status="running",
        lease_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    claimed = await worker._claim_next_run(session_factory, "new-worker")

    assert claimed == (run.id, user.id)
    await db.refresh(run)
    assert run.status == "running"
    assert run.lease_owner == "new-worker"
    assert run.attempt_count == 1


async def test_claim_next_run_does_not_steal_live_lease(db, test_engine):
    await _create_user_and_run(
        db,
        status="running",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    assert await worker._claim_next_run(session_factory, "new-worker") is None


async def test_process_run_persists_partial_source_telemetry(
    db, test_engine, monkeypatch
):
    user, run = await _create_user_and_run(db)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)

    async def fake_refresh(db, roles=None):
        return {
            "jobs_persisted": 0,
            "reports": [
                {
                    "source": "linkedin",
                    "query": "AI engineer",
                    "location": "India",
                    "status": "error",
                    "jobs_found": 0,
                    "duration_ms": 10,
                    "error_summary": "rate limited",
                    "started_at": now,
                    "finished_at": now,
                }
            ],
        }

    async def fake_score(**kwargs):
        return pd.DataFrame(columns=["id", "final_score"])

    monkeypatch.setattr(worker, "refresh_job_catalog", fake_refresh)
    monkeypatch.setattr(worker, "score_jobs_for_user", fake_score)

    await worker.process_run(run.id, user.id, session_factory)

    await db.refresh(run)
    assert run.status == "partial"
    assert run.stage == "complete"
    assert run.progress == 100
    assert run.job_count == 0
    assert "rate limited" in run.error_summary
    telemetry = (
        await db.execute(
            select(RunSourceTelemetry).where(RunSourceTelemetry.run_id == run.id)
        )
    ).scalar_one()
    assert telemetry.source == "linkedin"
    assert telemetry.query == "AI engineer"
    assert telemetry.status == "error"


async def test_process_run_keeps_success_when_source_has_partial_query_coverage(
    db, test_engine, monkeypatch
):
    user, run = await _create_user_and_run(db)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)

    async def fake_refresh(db, roles=None):
        return {
            "jobs_persisted": 0,
            "reports": [
                {
                    "source": "linkedin",
                    "query": "AI engineer",
                    "status": "success",
                    "jobs_found": 4,
                    "duration_ms": 10,
                    "started_at": now,
                    "finished_at": now,
                },
                {
                    "source": "linkedin",
                    "query": "ML engineer",
                    "status": "error",
                    "jobs_found": 0,
                    "duration_ms": 10,
                    "error_summary": "request timed out",
                    "started_at": now,
                    "finished_at": now,
                },
            ],
        }

    async def fake_score(**kwargs):
        return pd.DataFrame(columns=["id", "final_score"])

    monkeypatch.setattr(worker, "refresh_job_catalog", fake_refresh)
    monkeypatch.setattr(worker, "score_jobs_for_user", fake_score)

    await worker.process_run(run.id, user.id, session_factory)

    await db.refresh(run)
    assert run.status == "success"
    assert run.error_summary is None


async def test_process_run_passes_profile_roles_and_experience_to_ranker(
    db, test_engine, monkeypatch
):
    user, run = await _create_user_and_run(db)
    profile = (
        await db.execute(select(Profile).where(Profile.user_id == user.id))
    ).scalar_one()
    profile.target_roles = ["ML Platform Engineer"]
    profile.max_yoe = 6
    await db.commit()
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    captured = {}

    async def fake_refresh(db, roles=None, locations=None):
        captured["discovery_roles"] = roles
        return {"jobs_persisted": 0, "reports": []}

    async def fake_enrichment(*args, **kwargs):
        return SimpleNamespace(assessed=0, unknown=0, cached=0, status="success")

    async def fake_score(**kwargs):
        captured["config_overrides"] = kwargs["config_overrides"]
        return pd.DataFrame(columns=["id", "final_score"])

    monkeypatch.setattr(worker, "refresh_job_catalog", fake_refresh)
    monkeypatch.setattr(worker, "enrich_company_reputations", fake_enrichment)
    monkeypatch.setattr(worker, "score_jobs_for_user", fake_score)

    await worker.process_run(run.id, user.id, session_factory)

    assert captured["discovery_roles"] == ["ML Platform Engineer"]
    assert captured["config_overrides"] == {
        "profile_intent": {"roles": ["ML Platform Engineer"]},
        "experience": {"max_yoe": 6},
    }


async def test_process_run_recovers_from_aborted_catalog_transaction(
    db, test_engine, monkeypatch
):
    user, run = await _create_user_and_run(db)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def fake_refresh(db, roles=None):
        await db.execute(text("select * from missing_catalog_table"))

    async def fake_score(**kwargs):
        return pd.DataFrame(columns=["id", "final_score"])

    monkeypatch.setattr(worker, "refresh_job_catalog", fake_refresh)
    monkeypatch.setattr(worker, "score_jobs_for_user", fake_score)

    await worker.process_run(run.id, user.id, session_factory)

    await db.refresh(run)
    assert run.status == "partial"
    assert run.stage == "complete"
    assert run.progress == 100
    assert run.job_count == 0
    assert "Catalog refresh failed" in run.error_summary


async def test_desktop_run_continues_when_company_enrichment_times_out(
    db, test_engine, monkeypatch
):
    user, run = await _create_user_and_run(db)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def fake_refresh(db, roles=None):
        return {"jobs_persisted": 0, "reports": []}

    async def slow_enrichment(*args, **kwargs):
        await asyncio.sleep(1)

    async def fake_score(**kwargs):
        return pd.DataFrame(columns=["id", "final_score"])

    monkeypatch.setattr(worker, "refresh_job_catalog", fake_refresh)
    monkeypatch.setattr(worker, "enrich_company_reputations", slow_enrichment)
    monkeypatch.setattr(worker, "score_jobs_for_user", fake_score)
    monkeypatch.setattr(worker, "is_desktop_mode", lambda: True)
    monkeypatch.setattr(
        worker.settings, "desktop_company_enrichment_timeout_seconds", 0.01
    )

    await worker.process_run(run.id, user.id, session_factory)

    await db.refresh(run)
    assert run.status == "success"
    assert run.stage == "complete"


async def test_server_run_continues_when_job_enrichment_times_out(
    db, test_engine, monkeypatch
):
    user, run = await _create_user_and_run(db)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def fake_refresh(db, roles=None):
        return {"jobs_persisted": 0, "reports": []}

    async def slow_enrichment(*args, **kwargs):
        await asyncio.sleep(1)

    async def fake_score(**kwargs):
        return pd.DataFrame(columns=["id", "final_score"])

    monkeypatch.setattr(worker, "refresh_job_catalog", fake_refresh)
    monkeypatch.setattr(worker, "enrich_job_postings", slow_enrichment)
    monkeypatch.setattr(worker, "score_jobs_for_user", fake_score)
    monkeypatch.setattr(worker, "is_desktop_mode", lambda: False)
    monkeypatch.setattr(worker.settings, "job_enrichment_timeout_seconds", 0.01)

    await worker.process_run(run.id, user.id, session_factory)

    await db.refresh(run)
    assert run.status == "success"
    assert run.stage == "complete"

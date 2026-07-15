from datetime import datetime, timedelta, timezone

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

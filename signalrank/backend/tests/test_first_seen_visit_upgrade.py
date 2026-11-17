"""First-match timestamp must survive each rerank; desktop DB upgrades are additive."""

import asyncio
import pandas as pd
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from api.database import Base, ensure_runtime_schema_compatibility
from api.models import JobRaw, JobResult, Run, User
from batch.run_results import persist_ranked_results


@pytest.mark.asyncio
async def test_first_seen_at_survives_rerank_with_updated_score():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            user = User(email="first-seen-rerank@example.test")
            job = JobRaw(job_url="https://example.test/identity", title="Data Engineer", company="Example")
            db.add_all([user, job])
            await db.flush()
            first_run = Run(user_id=user.id, status="success")
            second_run = Run(user_id=user.id, status="success")
            db.add_all([first_run, second_run])
            await db.flush()
            user_id, job_id = user.id, job.id
            first_run_id, second_run_id = first_run.id, second_run.id
            df = pd.DataFrame([{
                "id": job_id,
                "semantic_score": 70, "skills_score": 75, "company_score": 80,
                "seniority_score": 90, "location_score": 95, "recency_score": 60,
                "final_score": 86, "company_tier": "tier_a", "is_contract": False,
            }])
            await persist_ranked_results(db, ranked_df=df, run_id=first_run_id, user_id=user_id)
            original = await db.scalar(
                select(JobResult).where(JobResult.user_id == user_id, JobResult.job_id == job_id)
            )
            first_seen = original.first_seen_at
            assert first_seen is not None
            await asyncio.sleep(0.025)
            df["final_score"] = 96
            await persist_ranked_results(db, ranked_df=df, run_id=second_run_id, user_id=user_id)
            await db.refresh(original)
            assert original.run_id == second_run_id
            assert original.final_score == 96
            assert original.first_seen_at == first_seen
            count = (await db.execute(select(JobResult).where(JobResult.user_id == user_id))).scalars().all()
            assert len(count) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_desktop_legacy_job_results_receive_first_seen_without_losing_rows():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(
                "CREATE TABLE job_results (id VARCHAR(36) PRIMARY KEY, run_id VARCHAR(36), "
                "user_id VARCHAR(36), job_id VARCHAR(36), final_score FLOAT)"
            ))
            await conn.execute(text(
                "INSERT INTO job_results (id, run_id, user_id, job_id, final_score) "
                "VALUES ('old-result', 'old-run', 'old-user', 'old-job', 73)"
            ))
        await ensure_runtime_schema_compatibility(bind=engine)
        await ensure_runtime_schema_compatibility(bind=engine)
        async with engine.begin() as conn:
            row = (await conn.execute(text(
                "SELECT id, final_score, first_seen_at FROM job_results WHERE id = 'old-result'"
            ))).one()
            assert row.id == "old-result" and row.final_score == 73
            assert row.first_seen_at is not None
            assert (await conn.execute(text("SELECT COUNT(*) FROM job_results"))).scalar_one() == 1
            assert (await conn.execute(text(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='user_inbox_visits'"
            ))).scalar_one() == 1
    finally:
        await engine.dispose()

"""SQLite regression for the later atomic resume tailoring fix."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from api.database import Base
from api.models import JobRaw, Profile, TailoredResume, User
from api.routes.resume import TailorRequest, tailor
from llm.resume_tailor import TailoredContent


@pytest.mark.asyncio
async def test_tailoring_twice_updates_one_row_and_replaces_pdf_bytes():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            user = User(email="resume-upsert@example.test")
            db.add(user)
            await db.flush()
            profile = Profile(user_id=user.id, resume_text="Experience with Python.")
            job = JobRaw(
                job_url="https://example.test/job",
                title="Engineer",
                description="Looking for Python.",
                company="Example",
            )
            db.add_all([profile, job])
            await db.commit()
            body = TailorRequest(job_id=job.id)
            with (
                patch("api.routes.resume.enforce_user_rate_limit", new_callable=AsyncMock),
                patch(
                    "llm.resume_tailor.tailor_resume",
                    new_callable=AsyncMock,
                    side_effect=[
                        TailoredContent(summary="First draft", certifications=["AWS"]),
                        TailoredContent(summary="Second draft", certifications=["GCP"]),
                    ],
                ),
                patch(
                    "llm.resume_tailor.render_compile_validate_content",
                    side_effect=[("src1", b"pdf-first", None), ("src2", b"pdf-second", None)],
                ),
            ):
                first = await tailor(body, profile=profile, db=db, llm=None)
                second = await tailor(body, profile=profile, db=db, llm=None)
            assert first["pdf_available"] and second["pdf_available"]
            await db.refresh(profile)

        async with factory() as db:
            assert await db.scalar(select(func.count(TailoredResume.id))) == 1
            saved = (await db.execute(select(TailoredResume))).scalar_one()
            assert saved.content_json["summary"] == "Second draft"
            assert saved.content_json["certifications"] == ["GCP"]
            assert saved.pdf_bytes == b"pdf-second"
    finally:
        await engine.dispose()

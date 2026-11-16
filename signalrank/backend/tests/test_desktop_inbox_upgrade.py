"""Additive, idempotent upgrade of an existing SQLite desktop tracker."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from api.database import ensure_runtime_schema_compatibility
import api.models  # noqa: F401 - registers metadata


@pytest.mark.asyncio
async def test_existing_desktop_application_rows_survive_review_upgrade():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.execute(text(
            "CREATE TABLE applications (id VARCHAR(36) PRIMARY KEY, "
            "user_id VARCHAR(36) NOT NULL, status VARCHAR(100))"
        ))
        await conn.execute(text(
            "INSERT INTO applications (id, user_id, status) "
            "VALUES ('existing-id', 'existing-user', 'interested')"
        ))
    try:
        await ensure_runtime_schema_compatibility(bind=engine)
        await ensure_runtime_schema_compatibility(bind=engine)
        async with engine.begin() as conn:
            columns = {
                row[1] for row in (await conn.execute(
                    text("PRAGMA table_info(applications)")
                )).all()
            }
            assert {"next_action", "next_action_due_date"} <= columns
            assert (await conn.execute(text(
                "SELECT status FROM applications WHERE id = 'existing-id'"
            ))).scalar_one() == "interested"
            assert (await conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name = 'job_review_states'"
            ))).scalar_one() == "job_review_states"
    finally:
        await engine.dispose()

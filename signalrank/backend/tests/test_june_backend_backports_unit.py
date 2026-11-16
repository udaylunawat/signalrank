"""Database-free regression coverage for June 6 backend hardening."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from api.routes.applications import (
    ApplicationCreate,
    ApplicationUpdate,
    create_application,
    update_application,
)
from api.routes.jobs import _job_search_clause


def _mock_db(app=None):
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    if app is not None:
        result = MagicMock()
        result.scalar_one_or_none.return_value = app
        db.execute.return_value = result
    return db


def test_city_search_includes_location_column():
    clause = _job_search_clause("Vadodara")
    compiled = clause.compile(dialect=postgresql.dialect())
    sql = str(compiled).lower()
    for field in ("jobs_raw.title", "jobs_raw.company", "jobs_raw.location"):
        assert field in sql
    assert list(compiled.params.values()) == ["%Vadodara%"] * 3


@pytest.mark.asyncio
async def test_saving_job_does_not_enqueue_or_discover():
    db = _mock_db()
    user = SimpleNamespace(id="example-user")
    response = await create_application(
        ApplicationCreate(job_id="job-123", company="Acme", title="Engineer"),
        current_user=user,
        db=db,
    )
    assert response["status"] == "interested"
    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_null_clears_saved_tracker_fields():
    app = SimpleNamespace(
        status="interested",
        notes="Follow up",
        priority="P1",
        location_group="Pune",
        interview_date=datetime(2026, 12, 1),
        offer_lpa=41.0,
        applied_at=None,
    )
    db = _mock_db(app)
    await update_application(
        "app-123",
        ApplicationUpdate(
            notes=None,
            priority=None,
            location_group=None,
            interview_date=None,
            offer_lpa=None,
        ),
        current_user=SimpleNamespace(id="example-user"),
        db=db,
    )
    for field in ("notes", "priority", "location_group", "interview_date", "offer_lpa"):
        assert getattr(app, field) is None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_omitted_fields_are_not_cleared():
    app = SimpleNamespace(
        status="interested",
        notes="Keep these notes",
        priority="P1",
        location_group="Pune",
        interview_date=datetime(2026, 12, 1),
        offer_lpa=41.0,
        applied_at=None,
    )
    db = _mock_db(app)
    await update_application(
        "app-123",
        ApplicationUpdate(status="interview"),
        current_user=SimpleNamespace(id="example-user"),
        db=db,
    )
    assert app.status == "interview"
    assert app.priority == "P1"
    assert app.notes == "Keep these notes"
    assert app.interview_date == datetime(2026, 12, 1)


@pytest.mark.asyncio
async def test_invalid_interview_date_is_validation_error():
    app = SimpleNamespace(
        status="interested",
        notes=None,
        priority=None,
        location_group=None,
        interview_date=None,
        offer_lpa=None,
        applied_at=None,
    )
    db = _mock_db(app)
    with pytest.raises(HTTPException) as exc_info:
        await update_application(
            "app-123",
            ApplicationUpdate(interview_date="not-a-date"),
            current_user=SimpleNamespace(id="example-user"),
            db=db,
        )
    assert exc_info.value.status_code == 422
    db.commit.assert_not_awaited()

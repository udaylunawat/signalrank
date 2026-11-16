"""Isolated SQLite API regression coverage; never touches a personal database."""

from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from api.auth import create_access_token
from api.database import Base, get_db
from api.main import app
from api.models import JobRaw, JobResult, Run, User


@pytest.fixture
async def sqlite_api(monkeypatch):
    from api.config import settings
    monkeypatch.setattr(settings, "nextauth_secret", "isolated-review-inbox-tests")
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        alice = User(email="alice-inbox@example.test")
        bob = User(email="bob-inbox@example.test")
        session.add_all([alice, bob])
        await session.flush()
        run_a = Run(user_id=alice.id, status="success", finished_at=datetime.now(timezone.utc))
        run_b = Run(user_id=bob.id, status="success", finished_at=datetime.now(timezone.utc))
        shared = JobRaw(job_url="https://example.test/shared", title="Data Engineer",
                        company="Example", location="Pune", site="manual")
        other = JobRaw(job_url="https://example.test/other", title="ML Engineer",
                       company="Acme", location="Mumbai", site="manual")
        session.add_all([run_a, run_b, shared, other])
        await session.flush()
        session.add_all([
            JobResult(run_id=run_a.id, user_id=alice.id, job_id=shared.id, final_score=87),
            JobResult(run_id=run_a.id, user_id=alice.id, job_id=other.id, final_score=75),
            JobResult(run_id=run_b.id, user_id=bob.id, job_id=shared.id, final_score=90),
        ])
        await session.commit()
        shared_id, other_id = shared.id, other.id
        alice_headers = {"Authorization": "Bearer " + create_access_token(alice.id, alice.email)}
        bob_headers = {"Authorization": "Bearer " + create_access_token(bob.id, bob.email)}

    async def overridden_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = overridden_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, alice_headers, bob_headers, shared_id, other_id
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


@pytest.mark.asyncio
async def test_inbox_review_state_persists_and_is_user_scoped(sqlite_api):
    client, alice, bob, shared_id, other_id = sqlite_api
    summary = await client.get("/api/inbox/summary", headers=alice)
    assert summary.status_code == 200, summary.text
    assert summary.json()["new"] == 2

    res = await client.put(
        f"/api/inbox/{shared_id}", json={"state": "dismissed"}, headers=alice
    )
    assert res.status_code == 200, res.text
    assert (await client.get("/api/inbox/summary", headers=alice)).json()["dismissed"] == 1
    assert (await client.get("/api/inbox/summary", headers=bob)).json()["new"] == 1

    # A separate API read, like a browser reload, retains the dismissal.
    dismissed = await client.get("/api/inbox?bucket=dismissed", headers=alice)
    assert [item["id"] for item in dismissed.json()["jobs"]] == [shared_id]
    matches = await client.get("/api/jobs", headers=alice)
    assert matches.status_code == 200, matches.text
    assert shared_id not in [j["id"] for j in matches.json()["jobs"]]
    assert other_id in [j["id"] for j in matches.json()["jobs"]]

    await client.put(
        f"/api/inbox/{shared_id}", json={"state": "unreviewed"}, headers=alice
    )
    assert (await client.get("/api/inbox/summary", headers=alice)).json()["new"] == 2


@pytest.mark.asyncio
async def test_inbox_snooze_resurfaces_on_due_date(sqlite_api):
    client, alice, _, shared_id, _ = sqlite_api
    tomorrow = date.today() + timedelta(days=1)
    response = await client.put(
        f"/api/inbox/{shared_id}",
        json={"state": "snoozed", "snoozed_until": tomorrow.isoformat()},
        headers=alice,
    )
    assert response.status_code == 200, response.text
    assert (await client.get("/api/inbox/summary", headers=alice)).json()["snoozed"] == 1
    due = await client.get(
        f"/api/inbox?bucket=due&today={tomorrow.isoformat()}", headers=alice
    )
    assert [j["id"] for j in due.json()["jobs"]] == [shared_id]
    summary = await client.get(
        f"/api/inbox/summary?today={tomorrow.isoformat()}", headers=alice
    )
    assert summary.json()["due"] == 1
    assert (await client.get("/api/inbox?bucket=new", headers=alice)).json()["total"] == 1


@pytest.mark.asyncio
async def test_inbox_batch_only_marks_unreviewed_and_checks_ownership(sqlite_api):
    client, alice, bob, shared_id, other_id = sqlite_api
    res = await client.post(
        "/api/inbox/mark-page-reviewed",
        json={"job_ids": [shared_id, other_id, other_id]},
        headers=alice,
    )
    assert res.status_code == 200, res.text
    assert res.json()["reviewed"] == 2
    assert (await client.get("/api/inbox/summary", headers=alice)).json()["review_complete"] is True
    assert (await client.get("/api/inbox/summary", headers=bob)).json()["new"] == 1
    denied = await client.put(
        f"/api/inbox/{other_id}", json={"state": "dismissed"}, headers=bob
    )
    assert denied.status_code == 404
    denied_batch = await client.post(
        "/api/inbox/mark-page-reviewed",
        json={"job_ids": [shared_id, other_id]}, headers=bob
    )
    assert denied_batch.status_code == 404
    assert (await client.get("/api/inbox/summary", headers=bob)).json()["new"] == 1


@pytest.mark.asyncio
async def test_followup_due_and_tracker_fields_can_be_cleared(sqlite_api):
    client, alice, _, shared_id, _ = sqlite_api
    today = date.today().isoformat()
    res = await client.post(
        "/api/applications",
        json={
            "job_id": shared_id,
            "company": "Example",
            "title": "Data Engineer",
            "next_action": "Email hiring manager",
            "next_action_due_date": today,
        },
        headers=alice,
    )
    assert res.status_code == 201, res.text
    app_id = res.json()["id"]
    assert (await client.get("/api/inbox/summary", headers=alice)).json()["followups_due"] == 1
    assert (await client.get("/api/inbox/summary", headers=alice)).json()["saved"] == 1

    update = await client.patch(
        f"/api/applications/{app_id}",
        json={"next_action": None, "next_action_due_date": None},
        headers=alice,
    )
    assert update.status_code == 200, update.text
    listing = await client.get("/api/applications", headers=alice)
    assert listing.status_code == 200, listing.text
    assert listing.json()["applications"][0]["next_action"] is None
    assert listing.json()["applications"][0]["next_action_due_date"] is None
    assert (await client.get("/api/inbox/summary", headers=alice)).json()["followups_due"] == 0


@pytest.mark.asyncio
async def test_invalid_inbox_actions_and_dates_are_rejected(sqlite_api):
    client, alice, _, shared_id, _ = sqlite_api
    for payload in (
        {"state": "snoozed"},
        {"state": "snoozed", "snoozed_until": date.today().isoformat()},
        {"state": "dismissed", "snoozed_until": "2030-01-01"},
        {"state": "not-a-real-state"},
    ):
        response = await client.put(f"/api/inbox/{shared_id}", json=payload, headers=alice)
        assert response.status_code == 422, (payload, response.text)

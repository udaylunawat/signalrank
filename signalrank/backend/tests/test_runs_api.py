from datetime import datetime, timezone

import pytest
from api.models import Run, RunSourceTelemetry
from sqlalchemy import select


@pytest.fixture
async def auth_token(client):
    await client.post(
        "/api/auth/register", json={"email": "runner@test.com", "password": "pass"}
    )
    r = await client.post(
        "/api/auth/login", json={"email": "runner@test.com", "password": "pass"}
    )
    return r.json()["access_token"]


async def test_trigger_run_returns_run_id(client, auth_token):
    r = await client.post(
        "/api/runs/trigger",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert r.status_code == 202
    data = r.json()
    assert "run_id" in data
    assert data["status"] == "pending"
    assert data["stage"] == "queued"
    assert data["progress"] == 0
    assert data["coalesced"] is False


async def test_trigger_coalesces_with_active_run(client, auth_token):
    first = await client.post(
        "/api/runs/trigger",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    second = await client.post(
        "/api/runs/trigger",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert second.status_code == 202
    assert second.json()["run_id"] == first.json()["run_id"]
    assert second.json()["coalesced"] is True


async def test_get_run_status(client, auth_token):
    trigger = await client.post(
        "/api/runs/trigger",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    run_id = trigger.json()["run_id"]
    r = await client.get(
        f"/api/runs/{run_id}/status",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert r.status_code == 200
    assert r.json()["run_id"] == run_id
    assert r.json()["status"] in (
        "pending",
        "running",
        "success",
        "partial",
        "failed",
    )
    assert r.json()["stage"] == "queued"
    assert r.json()["progress"] == 0


async def test_get_latest_run(client, auth_token):
    await client.post(
        "/api/runs/trigger",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    r = await client.get(
        "/api/runs/latest",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert r.status_code == 200


async def test_run_status_includes_source_telemetry(client, db, auth_token):
    trigger = await client.post(
        "/api/runs/trigger",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    run_id = trigger.json()["run_id"]
    now = datetime.now(timezone.utc)
    db.add(
        RunSourceTelemetry(
            run_id=run_id,
            source="indeed",
            query="AI engineer",
            location="India",
            status="success",
            jobs_found=42,
            jobs_persisted=40,
            duration_ms=1250,
            started_at=now,
            finished_at=now,
        )
    )
    run = (await db.execute(select(Run).where(Run.id == run_id))).scalar_one()
    run.status = "partial"
    run.stage = "complete"
    run.progress = 100
    run.error_summary = "linkedin: rate limited"
    await db.commit()

    response = await client.get(
        f"/api/runs/{run_id}/status",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "partial"
    assert payload["progress"] == 100
    assert payload["error_summary"] == "linkedin: rate limited"
    assert payload["sources"] == [
        {
            "source": "indeed",
            "query": "AI engineer",
            "location": "India",
            "status": "success",
            "jobs_found": 42,
            "jobs_persisted": 40,
            "duration_ms": 1250,
            "error_summary": None,
            "started_at": now.isoformat().replace("+00:00", "Z"),
            "finished_at": now.isoformat().replace("+00:00", "Z"),
        }
    ]

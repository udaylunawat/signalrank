import pytest


@pytest.fixture
async def auth_token(client):
    await client.post(
        "/api/auth/register", json={"email": "appuser@test.com", "password": "pass"}
    )
    r = await client.post(
        "/api/auth/login", json={"email": "appuser@test.com", "password": "pass"}
    )
    return r.json()["access_token"]


async def test_list_applications_empty(client, auth_token):
    r = await client.get(
        "/api/applications", headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert r.status_code == 200
    assert r.json() == []


async def test_create_and_list_application(client, auth_token):
    r = await client.post(
        "/api/applications",
        json={"company": "Acme", "title": "ML Engineer", "status": "interested"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert r.status_code == 201
    app_id = r.json()["id"]

    r = await client.get(
        "/api/applications", headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert any(a["id"] == app_id for a in r.json())


async def test_create_application_is_idempotent_for_job(client, auth_token, db):
    from api.models import JobRaw

    job = JobRaw(
        job_url="https://example.com/idempotent-job",
        title="Staff AI Engineer",
        company="Acme",
        site="indeed",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    payload = {
        "job_id": job.id,
        "company": job.company,
        "title": job.title,
        "status": "interested",
    }
    first = await client.post(
        "/api/applications",
        json=payload,
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    second = await client.post(
        "/api/applications",
        json=payload,
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["created"] is False


async def test_update_application_status(client, auth_token):
    r = await client.post(
        "/api/applications",
        json={"company": "Acme2", "title": "SRE", "status": "interested"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    app_id = r.json()["id"]

    r = await client.patch(
        f"/api/applications/{app_id}",
        json={"status": "applied"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert r.status_code == 200


async def test_update_application_notes_and_applied_at(client, auth_token):
    created = await client.post(
        "/api/applications",
        json={"company": "Acme", "title": "SRE", "status": "interested"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    app_id = created.json()["id"]

    updated = await client.patch(
        f"/api/applications/{app_id}",
        json={
            "notes": "Follow up after the synthetic interview.",
            "applied_at": "2026-08-01T12:30:00Z",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert updated.status_code == 200

    listed = await client.get(
        "/api/applications", headers={"Authorization": f"Bearer {auth_token}"}
    )
    row = next(item for item in listed.json() if item["id"] == app_id)
    assert row["notes"] == "Follow up after the synthetic interview."
    assert row["applied_at"].startswith("2026-08-01 12:30:00")


async def test_update_application_rejects_invalid_applied_at(client, auth_token):
    created = await client.post(
        "/api/applications",
        json={"company": "Acme", "title": "SRE"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    response = await client.patch(
        f"/api/applications/{created.json()['id']}",
        json={"applied_at": "not-a-date"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 422


async def test_delete_application(client, auth_token):
    r = await client.post(
        "/api/applications",
        json={"company": "Del Inc", "title": "Dev", "status": "interested"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    app_id = r.json()["id"]

    r = await client.delete(
        f"/api/applications/{app_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert r.status_code == 204


async def test_create_application_invalid_status(client, auth_token):
    r = await client.post(
        "/api/applications",
        json={"company": "Bad", "title": "Dev", "status": "gibberish"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert r.status_code == 422

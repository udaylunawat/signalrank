import pytest

from api.models import JobRaw


@pytest.fixture
async def auth_token(client):
    await client.post(
        "/api/auth/register", json={"email": "feedback@test.com", "password": "pass"}
    )
    response = await client.post(
        "/api/auth/login", json={"email": "feedback@test.com", "password": "pass"}
    )
    return response.json()["access_token"]


async def test_feedback_is_upserted_and_can_be_removed(client, auth_token, db):
    job = JobRaw(
        job_url="https://example.com/feedback-job",
        title="Data Engineer",
        company="Acme",
        site="indeed",
    )
    db.add(job)
    await db.commit()

    headers = {"Authorization": f"Bearer {auth_token}"}
    first = await client.put(
        f"/api/jobs/{job.id}/feedback",
        json={"value": "not_relevant", "reason": "wrong_location"},
        headers=headers,
    )
    second = await client.put(
        f"/api/jobs/{job.id}/feedback",
        json={"value": "relevant"},
        headers=headers,
    )
    removed = await client.delete(f"/api/jobs/{job.id}/feedback", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == {"job_id": job.id, "value": "relevant", "reason": None}
    assert removed.status_code == 204

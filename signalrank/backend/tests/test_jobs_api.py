import csv
from io import StringIO

import pytest
from api.models import JobRaw, JobResult, Run


@pytest.fixture
async def auth_token(client):
    await client.post(
        "/api/auth/register", json={"email": "jobuser@test.com", "password": "pass"}
    )
    r = await client.post(
        "/api/auth/login", json={"email": "jobuser@test.com", "password": "pass"}
    )
    return r.json()["access_token"]


async def test_list_jobs_no_run_returns_empty(client, auth_token):
    r = await client.get("/api/jobs", headers={"Authorization": f"Bearer {auth_token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["jobs"] == []
    assert data["total"] == 0


async def test_get_profile(client, auth_token):
    r = await client.get(
        "/api/profile", headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert r.status_code == 200
    assert "user_id" in r.json()


async def test_patch_profile(client, auth_token):
    r = await client.patch(
        "/api/profile",
        json={"role_intent": "ml_engineer", "min_salary": 5000000},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "updated"

    cleared = await client.patch(
        "/api/profile",
        json={"min_salary": None},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert cleared.status_code == 200
    profile = await client.get(
        "/api/profile", headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert profile.json()["profile"]["min_salary"] is None


async def test_profile_rejects_contradictory_or_unknown_company_tiers(
    client, auth_token
):
    headers = {"Authorization": f"Bearer {auth_token}"}
    contradictory = await client.patch(
        "/api/profile",
        json={
            "config_overrides": {"company_preferences": {"tiers": ["any", "tier_s"]}}
        },
        headers=headers,
    )
    unknown = await client.patch(
        "/api/profile",
        json={"config_overrides": {"company_preferences": {"tiers": ["tier_unicorn"]}}},
        headers=headers,
    )

    assert contradictory.status_code == 422
    assert unknown.status_code == 422


async def test_get_job_not_found(client, auth_token):
    r = await client.get(
        "/api/jobs/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert r.status_code == 404


async def test_jobs_search_and_sort_apply_to_the_full_result_set(
    client, auth_token, db
):
    profile = await client.get(
        "/api/profile", headers={"Authorization": f"Bearer {auth_token}"}
    )
    user_id = profile.json()["user_id"]
    run = Run(user_id=user_id, status="success", job_count=2)
    first = JobRaw(
        job_url="https://example.com/backend-engineer",
        title="Backend Engineer",
        company="Alpha",
        site="indeed",
    )
    second = JobRaw(
        job_url="https://example.com/agentic-engineer",
        title="Senior Agentic AI Engineer",
        company="Zulu AI",
        site="linkedin",
    )
    db.add_all([run, first, second])
    await db.flush()
    db.add_all(
        [
            JobResult(
                run_id=run.id,
                user_id=user_id,
                job_id=first.id,
                final_score=92,
            ),
            JobResult(
                run_id=run.id,
                user_id=user_id,
                job_id=second.id,
                final_score=81,
            ),
        ]
    )
    await db.commit()

    response = await client.get(
        "/api/jobs",
        params={"q": "Agentic", "source": "linkedin", "limit": 1},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["jobs"][0]["title"] == "Senior Agentic AI Engineer"
    assert payload["source_counts"] == {"indeed": 1, "linkedin": 1}


async def test_export_jobs_csv_includes_all_jobs_and_score_breakdown(
    client, auth_token, db
):
    profile = await client.get(
        "/api/profile", headers={"Authorization": f"Bearer {auth_token}"}
    )
    user_id = profile.json()["user_id"]
    run = Run(user_id=user_id, status="success", job_count=2)
    first = JobRaw(
        job_url="https://example.com/first",
        title="=Spreadsheet Formula",
        company='Alpha, "Labs"',
        description="First line\nSecond line",
        location="Remote",
        site="indeed",
    )
    second = JobRaw(
        job_url="https://example.com/second",
        title="Platform Engineer",
        company="Beta",
        site="linkedin",
    )
    db.add_all([run, first, second])
    await db.flush()
    db.add_all(
        [
            JobResult(
                run_id=run.id,
                user_id=user_id,
                job_id=first.id,
                final_score=91,
                semantic_score=88,
                skills_score=85,
                company_score=100,
                seniority_score=75,
                location_score=90,
                recency_score=80,
                company_tier="tier_s",
                company_reputation_confidence=0.95,
                company_reputation_rationale="Strong engineering reputation",
                explanation={"summary": "Strong fit"},
                is_contract=False,
            ),
            JobResult(
                run_id=run.id,
                user_id=user_id,
                job_id=second.id,
                final_score=72,
            ),
        ]
    )
    await db.commit()

    response = await client.get(
        "/api/jobs/export.csv",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "signalrank-jobs-" in response.headers["content-disposition"]
    rows = list(csv.DictReader(StringIO(response.text.lstrip("\ufeff"))))
    assert len(rows) == 2
    assert rows[0]["title"] == "'=Spreadsheet Formula"
    assert rows[0]["company"] == 'Alpha, "Labs"'
    assert rows[0]["description"] == "First line\nSecond line"
    assert rows[0]["final_score"] == "91.0"
    assert rows[0]["semantic_score"] == "88.0"
    assert rows[0]["company_tier"] == "tier_s"
    assert rows[0]["company_reputation_confidence"] == "0.95"
    assert rows[0]["company_reputation_rationale"] == ("Strong engineering reputation")
    assert rows[0]["score_explanation_json"] == '{"summary": "Strong fit"}'
    assert rows[0]["is_contract"] == "False"


async def test_export_jobs_csv_without_a_run_returns_headers_only(client, auth_token):
    response = await client.get(
        "/api/jobs/export.csv",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 200
    rows = list(csv.reader(StringIO(response.text.lstrip("\ufeff"))))
    assert len(rows) == 1
    assert "final_score" in rows[0]

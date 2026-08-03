import csv
from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest
from api.models import JobFeedback, JobRaw, JobResult, Run


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


async def test_get_job_rejects_malformed_id(client, auth_token):
    response = await client.get(
        "/api/jobs/not-a-uuid", headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 422


async def test_get_job_returns_only_the_current_users_latest_result(
    client, auth_token, db
):
    profile = await client.get(
        "/api/profile", headers={"Authorization": f"Bearer {auth_token}"}
    )
    user_id = profile.json()["user_id"]
    completed_at = datetime.now(UTC)
    run = Run(
        user_id=user_id,
        status="success",
        finished_at=completed_at,
        job_count=1,
    )
    job = JobRaw(
        job_url="https://example.com/platform-engineer",
        title="Platform Engineer",
        company="Alpha",
        description="Build platform systems.",
        site="indeed",
    )
    db.add_all([run, job])
    await db.flush()
    db.add(
        JobResult(
            run_id=run.id,
            user_id=user_id,
            job_id=job.id,
            final_score=91,
            semantic_score=88,
            skills_score=85,
            company_score=80,
            seniority_score=75,
            location_score=90,
            recency_score=70,
            explanation={"matched_skills": ["Python"], "concerns": []},
        )
    )
    db.add(
        JobFeedback(
            user_id=user_id,
            job_id=job.id,
            value="not_relevant",
            reason="wrong_location",
        )
    )
    await db.commit()

    response = await client.get(
        f"/api/jobs/{job.id}", headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["description"] == "Build platform systems."
    assert payload["final_score"] == 91
    assert payload["semantic_score"] == 88
    assert payload["run_id"] == str(run.id)
    assert payload["completed_at"].startswith(completed_at.date().isoformat())
    assert payload["feedback"] == {
        "value": "not_relevant",
        "reason": "wrong_location",
    }
    assert payload["explanation"] == {
        "matched_skills": ["Python"],
        "concerns": [],
    }

    other_register = await client.post(
        "/api/auth/register", json={"email": "other-job@test.com", "password": "pass"}
    )
    assert other_register.status_code == 201
    other_login = await client.post(
        "/api/auth/login", json={"email": "other-job@test.com", "password": "pass"}
    )
    other_token = other_login.json()["access_token"]
    forbidden = await client.get(
        f"/api/jobs/{job.id}", headers={"Authorization": f"Bearer {other_token}"}
    )

    assert forbidden.status_code == 404


async def test_get_job_exposes_only_the_latest_completed_run(client, auth_token, db):
    profile = await client.get(
        "/api/profile", headers={"Authorization": f"Bearer {auth_token}"}
    )
    user_id = profile.json()["user_id"]
    now = datetime.now(UTC)
    older_run = Run(
        user_id=user_id,
        status="success",
        finished_at=now - timedelta(days=1),
        job_count=1,
    )
    latest_run = Run(
        user_id=user_id,
        status="partial",
        finished_at=now,
        job_count=1,
    )
    older_job = JobRaw(
        job_url="https://example.com/older-result",
        title="Older role",
        company="Alpha",
        site="indeed",
    )
    latest_job = JobRaw(
        job_url="https://example.com/latest-result",
        title="Latest role",
        company="Alpha",
        site="indeed",
    )
    db.add_all([older_run, latest_run, older_job, latest_job])
    await db.flush()
    db.add_all(
        [
            JobResult(
                run_id=older_run.id,
                user_id=user_id,
                job_id=older_job.id,
                final_score=95,
            ),
            JobResult(
                run_id=latest_run.id,
                user_id=user_id,
                job_id=latest_job.id,
                final_score=80,
            ),
        ]
    )
    await db.commit()

    old_result = await client.get(
        f"/api/jobs/{older_job.id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    latest_result = await client.get(
        f"/api/jobs/{latest_job.id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert old_result.status_code == 404
    assert latest_result.status_code == 200
    assert latest_result.json()["run_id"] == str(latest_run.id)


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

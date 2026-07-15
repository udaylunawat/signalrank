import pytest


@pytest.fixture
async def auth_token(client):
    await client.post(
        "/api/auth/register", json={"email": "onboard@test.com", "password": "pass"}
    )
    r = await client.post(
        "/api/auth/login", json={"email": "onboard@test.com", "password": "pass"}
    )
    return r.json()["access_token"]


async def test_onboarding_status_initial(client, auth_token):
    r = await client.get(
        "/api/onboarding/status", headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert r.status_code == 200
    assert r.json()["onboarding_complete"] is False
    assert r.json()["has_resume"] is False


async def test_upload_resume_txt(client, auth_token, monkeypatch):
    import api.routes.onboarding as onboarding_route
    from llm.resume_parser import ResumeParseResult

    async def mock_parse(text, llm_client):
        return ResumeParseResult(skills=["python"], years_of_experience=3)

    monkeypatch.setattr(onboarding_route, "parse_resume", mock_parse)

    r = await client.post(
        "/api/onboarding/resume",
        files={
            "file": (
                "resume.txt",
                b"Python developer with 3 years experience",
                "text/plain",
            )
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "questions" in data
    assert len(data["questions"]) >= 3


async def test_refine_saves_answer(client, auth_token):
    await client.patch(
        "/api/profile",
        json={"role_intent": "ml"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    r = await client.post(
        "/api/onboarding/refine",
        json={"question_id": "target_roles", "answer": ["AI/ML Engineer"]},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "saved"

    r = await client.post(
        "/api/onboarding/refine",
        json={"question_id": "preferred_locations", "answer": ["Bengaluru", "Remote"]},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert r.status_code == 200

    profile = await client.get(
        "/api/profile", headers={"Authorization": f"Bearer {auth_token}"}
    )
    overrides = profile.json()["profile"]["config_overrides"]
    assert overrides["profile_intent"] == {"roles": ["AI/ML Engineer"]}
    assert overrides["location_scoring"]["preferred_locations"] == [
        "Bengaluru",
        "Remote",
    ]


async def test_onboarding_status_restores_durable_draft(
    client, auth_token, monkeypatch
):
    import api.routes.onboarding as onboarding_route
    from llm.resume_parser import ResumeParseResult

    async def mock_parse(text, llm_client):
        return ResumeParseResult(
            skills=["Playwright"],
            recent_titles=["QA Automation Engineer"],
            status="degraded",
            confidence=0.7,
            source="heuristic",
        )

    monkeypatch.setattr(onboarding_route, "parse_resume", mock_parse)
    headers = {"Authorization": f"Bearer {auth_token}"}
    uploaded = await client.post(
        "/api/onboarding/resume",
        files={"file": ("resume.txt", b"QA Automation Engineer", "text/plain")},
        headers=headers,
    )
    await client.post(
        "/api/onboarding/refine",
        json={"question_id": "target_roles", "answer": ["SDET"]},
        headers=headers,
    )

    status = (await client.get("/api/onboarding/status", headers=headers)).json()
    assert uploaded.status_code == 200
    assert status["draft"]["answers"]["target_roles"] == ["SDET"]
    assert status["parse_status"] == "degraded"


async def test_resume_upload_rejects_files_over_10_mb(client, auth_token):
    response = await client.post(
        "/api/onboarding/resume",
        files={"file": ("resume.txt", b"x" * (10 * 1024 * 1024 + 1), "text/plain")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 413


async def test_refine_wires_company_preferences_and_exclusions(client, auth_token):
    await client.patch(
        "/api/profile",
        json={"role_intent": "ml"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    headers = {"Authorization": f"Bearer {auth_token}"}
    await client.post(
        "/api/onboarding/refine",
        json={"question_id": "preferred_companies", "answer": "OpenAI, Anthropic"},
        headers=headers,
    )
    tiers = await client.post(
        "/api/onboarding/refine",
        json={
            "question_id": "company_tiers",
            "answer": [
                "S-tier (FAANG, top startups)",
                "A-tier (strong tech companies)",
            ],
        },
        headers=headers,
    )
    await client.post(
        "/api/onboarding/refine",
        json={"question_id": "excluded_companies", "answer": "Deloitte"},
        headers=headers,
    )
    await client.post(
        "/api/onboarding/refine",
        json={"question_id": "excluded_titles", "answer": "QA roles"},
        headers=headers,
    )

    profile = (await client.get("/api/profile", headers=headers)).json()["profile"]
    preferences = profile["config_overrides"]["company_preferences"]
    assert tiers.status_code == 200
    assert preferences["tiers"] == ["tier_s", "tier_a"]
    assert preferences["preferred_companies"] == ["OpenAI", "Anthropic"]
    assert preferences["excluded_companies"] == ["Deloitte"]
    assert profile["config_overrides"]["title_blocklist"] == ["QA roles"]


async def test_refine_rejects_any_company_with_specific_tier(client, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    await client.patch("/api/profile", json={"role_intent": "ml"}, headers=headers)
    response = await client.post(
        "/api/onboarding/refine",
        json={
            "question_id": "company_tiers",
            "answer": ["Any company", "S-tier (FAANG, top startups)"],
        },
        headers=headers,
    )

    assert response.status_code == 422

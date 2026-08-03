from io import BytesIO

import pytest
from api.deps_llm import get_llm_client
from api.main import app
from api.models import JobRaw, Profile, TailoredResume
from pypdf import PdfReader
from sqlalchemy import select


class FakeLLM:
    last_error = None

    def __init__(self):
        self.calls = []

    async def llm_json(self, **kwargs):
        self.calls.append(("json", kwargs))
        return {
            "name": "Priya Sharma",
            "email": "priya@example.com",
            "phone": "+91 90000 00000",
            "location": "Pune",
            "homepage": "",
            "linkedin": "priya-sharma",
            "github": "",
            "position": "Clinical Educator",
            "summary": "Pediatric nurse with eight years of patient-care experience.",
            "skills": ["Patient education", "Clinical training"],
            "experiences": [
                {
                    "title": "Pediatric Nurse",
                    "company": "City Hospital",
                    "location": "Pune",
                    "dates": "2018-present",
                    "tech": "",
                    "bullets": ["Trained 40 nurses on updated care protocols."],
                }
            ],
            "projects": [],
            "education": [
                {
                    "degree": "BSc Nursing",
                    "institution": "Health University",
                    "year": "2018",
                }
            ],
        }

    async def llm_text(self, system_prompt, user_message, **kwargs):
        self.calls.append(("text", {"system": system_prompt, "user": user_message}))
        return (
            "SUBJECT: Clinical Educator - pediatric training experience\n"
            "BODY:\n"
            "Hi Hiring team,\n\n"
            "I applied for the Clinical Educator role at HealthCo. In my current "
            "pediatric nursing role, I trained 40 nurses on updated care protocols.\n\n"
            "I would welcome a brief conversation if that experience is useful."
        )


@pytest.fixture
async def auth_token(client):
    await client.post(
        "/api/auth/register", json={"email": "tailor@test.com", "password": "pass"}
    )
    r = await client.post(
        "/api/auth/login", json={"email": "tailor@test.com", "password": "pass"}
    )
    return r.json()["access_token"]


async def test_list_templates(client, auth_token):
    r = await client.get(
        "/api/resume/templates", headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert r.status_code == 200
    assert "templates" in r.json()
    assert "classic" in r.json()["templates"]


async def add_profile_and_job(client, auth_token, db):
    profile_response = await client.get(
        "/api/profile", headers={"Authorization": f"Bearer {auth_token}"}
    )
    user_id = profile_response.json()["user_id"]
    profile_result = await db.execute(select(Profile).where(Profile.user_id == user_id))
    profile = profile_result.scalar_one()
    profile.resume_text = (
        "Priya Sharma\nPediatric Nurse\nTrained 40 nurses on updated care protocols."
    )
    job = JobRaw(
        title="Clinical Educator",
        company="HealthCo",
        description="Train clinical teams and develop patient education programs.",
        job_url="https://jobs.example.com/clinical-educator",
    )
    db.add(job)
    await db.commit()
    return job


async def test_tailor_no_resume_returns_404(client, auth_token):
    r = await client.post(
        "/api/resume/tailor",
        json={"job_id": "00000000-0000-0000-0000-000000000000", "template": "classic"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert r.status_code == 404


async def test_tailor_invalid_template(client, auth_token, monkeypatch):
    import llm.resume_parser as rp
    from llm.resume_parser import ResumeParseResult

    async def mock_parse(text, llm_client):
        return ResumeParseResult(skills=["python"], years_of_experience=2)

    monkeypatch.setattr(rp, "parse_resume", mock_parse)

    await client.post(
        "/api/onboarding/resume",
        files={"file": ("r.txt", b"Python dev", "text/plain")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    r = await client.post(
        "/api/resume/tailor",
        json={
            "job_id": "00000000-0000-0000-0000-000000000000",
            "template": "badtemplate",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert r.status_code == 422


async def test_tailor_download_and_email_are_role_agnostic(client, auth_token, db):
    job = await add_profile_and_job(client, auth_token, db)
    fake_llm = FakeLLM()
    app.dependency_overrides[get_llm_client] = lambda: fake_llm
    headers = {"Authorization": f"Bearer {auth_token}"}

    tailored = await client.post(
        "/api/resume/tailor",
        json={"job_id": job.id, "template": "modern"},
        headers=headers,
    )
    regenerated = await client.post(
        "/api/resume/tailor",
        json={"job_id": job.id, "template": "minimal"},
        headers=headers,
    )
    downloaded = await client.get(f"/api/resume/tailor/{job.id}", headers=headers)
    email = await client.post(
        "/api/resume/email",
        json={"job_id": job.id, "recipient_name": "Hiring team"},
        headers=headers,
    )

    assert tailored.status_code == 200
    assert tailored.json()["pdf_available"] is True
    assert regenerated.status_code == 200
    saved = await db.execute(
        select(TailoredResume).where(TailoredResume.job_id == job.id)
    )
    drafts = saved.scalars().all()
    assert len(drafts) == 1
    assert drafts[0].template == "minimal"
    json_call = next(call for call in fake_llm.calls if call[0] == "json")
    assert json_call[1]["response_schema"]["additionalProperties"] is False
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF")
    assert (
        "priya_sharma_healthco_clinical_educator.pdf"
        in downloaded.headers["content-disposition"]
    )
    reader = PdfReader(BytesIO(downloaded.content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Priya Sharma" in text
    assert "Pediatric Nurse" in text
    assert email.status_code == 200
    assert "Clinical Educator" in email.json()["subject"]
    assert "trained 40 nurses" in email.json()["body"]
    assert any(
        "Pediatric Nurse" in call[1]["user"]
        for call in fake_llm.calls
        if call[0] == "text"
    )


async def test_tailor_reports_openrouter_failure(client, auth_token, db):
    job = await add_profile_and_job(client, auth_token, db)

    class FailedLLM(FakeLLM):
        async def llm_json(self, **kwargs):
            return {"_error": "auth_failed", "_details": "API key rejected"}

    app.dependency_overrides[get_llm_client] = lambda: FailedLLM()
    response = await client.post(
        "/api/resume/tailor",
        json={"job_id": job.id, "template": "classic"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 503
    assert "API key rejected" in response.json()["detail"]

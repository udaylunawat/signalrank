import pytest
from api.models import JobRaw
from llm.resume_tailor import TailoredContent


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


async def test_tailor_persists_content_generates_pdf_and_isolates_download(
    client, auth_token, db, monkeypatch
):
    from api.routes import resume as resume_route

    await client.post(
        "/api/onboarding/resume",
        files={"file": ("r.txt", b"Synthetic Python developer", "text/plain")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    job = JobRaw(
        job_url="https://jobs.example.test/tailor",
        title="Platform Engineer",
        description="Build platform services with Python.",
        company="Synthetic Labs",
    )
    db.add(job)
    await db.commit()

    async def fake_tailor_resume(**_kwargs):
        return TailoredContent(
            name="Synthetic Candidate",
            position="Platform Engineer",
            summary="A truthful synthetic summary.",
            skills=["Python"],
        )

    monkeypatch.setattr(resume_route, "tailor_resume", fake_tailor_resume)
    monkeypatch.setattr(resume_route, "render_typst", lambda *_args: "synthetic typst")
    monkeypatch.setattr(resume_route, "compile_pdf", lambda _source: b"%PDF-synthetic")
    headers = {"Authorization": f"Bearer {auth_token}"}

    tailored = await client.post(
        "/api/resume/tailor",
        json={"job_id": str(job.id), "template": "modern"},
        headers=headers,
    )
    assert tailored.status_code == 200
    assert tailored.json()["pdf_available"] is True
    assert tailored.json()["content"]["skills"] == ["Python"]

    download = await client.get(f"/api/resume/tailor/{job.id}", headers=headers)
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/pdf")
    assert download.content == b"%PDF-synthetic"
    assert f"resume_{str(job.id)[:8]}.pdf" in download.headers["content-disposition"]

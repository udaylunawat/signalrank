import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from llm.email_generator import EmailGenerationError, generate_email
from llm.openrouter import OpenRouterClient
from llm.resume_tailor import (
    VALID_TEMPLATES,
    ResumeRenderError,
    ResumeTailorError,
    TailoredContent,
    compile_pdf,
    tailor_resume,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.deps import get_current_user
from api.deps_llm import get_llm_client
from api.models import JobRaw, Profile, TailoredResume, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resume", tags=["resume"])


class TailorRequest(BaseModel):
    job_id: str
    template: str = "classic"


class EmailRequest(BaseModel):
    job_id: str
    recipient_name: str = Field(default="Hiring team", max_length=100)


@router.post("/tailor")
async def tailor(
    body: TailorRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm: OpenRouterClient = Depends(get_llm_client),
):
    if body.template not in VALID_TEMPLATES:
        raise HTTPException(
            status_code=422, detail=f"Template must be one of: {VALID_TEMPLATES}"
        )

    profile_res = await db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    )
    profile = profile_res.scalar_one_or_none()
    if not profile or not profile.resume_text:
        raise HTTPException(
            status_code=404, detail="Upload a resume first via /api/onboarding/resume"
        )

    job_res = await db.execute(select(JobRaw).where(JobRaw.id == body.job_id))
    job = job_res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        content = await tailor_resume(
            resume_text=profile.resume_text,
            job_title=job.title,
            job_description=job.description or "",
            llm=llm,
        )
    except ResumeTailorError as error:
        logger.warning("Resume tailoring failed: %s", error)
        raise HTTPException(
            status_code=503,
            detail=f"OpenRouter could not generate a tailored resume: {error}",
        ) from error

    content_dict = {
        "name": content.name,
        "position": content.position,
        "email": content.email,
        "phone": content.phone,
        "homepage": content.homepage,
        "linkedin": content.linkedin,
        "github": content.github,
        "location": content.location,
        "summary": content.summary,
        "skills": content.skills,
        "experiences": content.experiences,
        "education": content.education,
        "projects": content.projects,
    }

    dialect_name = db.get_bind().dialect.name
    insert_factory = sqlite_insert if dialect_name == "sqlite" else postgresql_insert
    statement = insert_factory(TailoredResume).values(
        user_id=current_user.id,
        job_id=body.job_id,
        content_json=content_dict,
        template=body.template,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[TailoredResume.user_id, TailoredResume.job_id],
        set_={
            "content_json": statement.excluded.content_json,
            "template": statement.excluded.template,
            "pdf_path": None,
        },
    )
    await db.execute(statement)
    await db.commit()

    return {
        "status": "ok",
        "job_id": body.job_id,
        "template": body.template,
        "content": content_dict,
        "pdf_available": True,
    }


@router.get("/tailor/{job_id}")
async def download_tailored(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(TailoredResume).where(
            TailoredResume.user_id == current_user.id,
            TailoredResume.job_id == job_id,
        )
    )
    tailored = res.scalar_one_or_none()
    if not tailored:
        raise HTTPException(status_code=404, detail="No tailored resume for this job")

    content = TailoredContent(**tailored.content_json)
    try:
        pdf_bytes = compile_pdf(content, tailored.template or "classic")
    except ResumeRenderError as error:
        logger.exception("Tailored resume rendering failed")
        raise HTTPException(status_code=503, detail=str(error)) from error

    job_res = await db.execute(select(JobRaw).where(JobRaw.id == job_id))
    job = job_res.scalar_one_or_none()
    filename_parts = [content.name or "candidate"]
    if job:
        filename_parts.extend([job.company or "", job.title or ""])
    filename = "_".join(
        part
        for part in (
            re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
            for value in filename_parts
        )
        if part
    )[:120]
    filename = f"{filename or 'tailored_resume'}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/email")
async def generate_outreach_email(
    body: EmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm: OpenRouterClient = Depends(get_llm_client),
):
    profile_res = await db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    )
    profile = profile_res.scalar_one_or_none()
    if not profile or not profile.resume_text:
        raise HTTPException(status_code=404, detail="Upload a resume first")

    job_res = await db.execute(select(JobRaw).where(JobRaw.id == body.job_id))
    job = job_res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        email = await generate_email(
            resume_text=profile.resume_text,
            job_description=job.description or "",
            company=job.company or "the company",
            role=job.title or "the role",
            recipient_name=body.recipient_name,
            job_url=job.job_url,
            llm=llm,
        )
    except EmailGenerationError as error:
        logger.warning("Outreach generation failed: %s", error)
        raise HTTPException(
            status_code=503,
            detail=f"OpenRouter could not generate outreach: {error}",
        ) from error

    return {"subject": email.subject, "body": email.body}


@router.get("/templates")
async def list_templates():
    return {"templates": sorted(VALID_TEMPLATES)}

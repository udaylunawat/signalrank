import io
import logging
import re
from copy import deepcopy

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from llm.onboarding import generate_onboarding_questions
from llm.openrouter import OpenRouterClient
from llm.resume_parser import parse_resume
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.deps import get_current_user
from api.deps_llm import get_llm_client
from api.models import Profile, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


def _extract_text_from_pdf(content: bytes) -> str:
    try:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(content))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    except Exception as e:
        logger.warning("PDF extraction failed: %s", e)
        return ""


def _extract_text_from_docx(content: bytes) -> str:
    try:
        import docx

        doc = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        logger.warning("DOCX extraction failed: %s", e)
        return ""


@router.post("/resume")
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm: OpenRouterClient = Depends(get_llm_client),
):
    content = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".pdf"):
        resume_text = _extract_text_from_pdf(content)
    elif filename.endswith(".docx"):
        resume_text = _extract_text_from_docx(content)
    elif filename.endswith(".txt"):
        resume_text = content.decode("utf-8", errors="replace")
    else:
        raise HTTPException(status_code=422, detail="Supported formats: PDF, DOCX, TXT")

    if not resume_text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from file")

    parsed = await parse_resume(resume_text, llm)

    result = await db.execute(select(Profile).where(Profile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = Profile(user_id=current_user.id)
        db.add(profile)

    profile.resume_text = resume_text
    profile.skills = parsed.skills
    if parsed.skills or parsed.recent_titles or parsed.years_of_experience:
        parts = []
        if parsed.recent_titles:
            parts.append("Recent roles: " + ", ".join(parsed.recent_titles))
        if parsed.skills:
            parts.append("Skills: " + ", ".join(parsed.skills))
        if parsed.years_of_experience:
            parts.append(f"Experience: {parsed.years_of_experience} years")
        profile.distilled_text = "\n".join(parts)
    await db.commit()

    questions = generate_onboarding_questions(parsed)
    return {
        "extracted": {
            "skills": parsed.skills,
            "years_of_experience": parsed.years_of_experience,
            "recent_titles": parsed.recent_titles,
        },
        "questions": questions,
    }


@router.get("/status")
async def onboarding_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Profile).where(Profile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    return {
        "onboarding_complete": profile.onboarding_complete if profile else False,
        "has_resume": bool(profile and profile.resume_text),
    }


class RefineAnswer(BaseModel):
    question_id: str
    answer: str | list[str]


def _answer_values(answer: str | list[str]) -> list[str]:
    if isinstance(answer, list):
        return [value.strip() for value in answer if value.strip()]
    return [item.strip() for item in re.split(r"[,;\n]+", answer) if item.strip()]


def _parse_salary(answer: str | list[str]) -> int | None:
    value = answer[0] if isinstance(answer, list) and answer else answer
    text = str(value or "").strip().lower().replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    amount = float(match.group(1))
    if "lpa" in text or "lakh" in text or re.search(r"\d\s*l\b", text):
        amount *= 100_000
    elif re.search(r"\d\s*k\b", text):
        amount *= 1_000
    return round(amount)


def _infer_role_preset(answer: str | list[str]) -> str:
    roles = answer if isinstance(answer, list) else [answer]
    value = " ".join(roles).lower()
    if any(
        term in value for term in ("agent", "llm", " ai ", "machine learning", "ml ")
    ):
        return "agentic_systems"
    if any(term in value for term in ("platform", "devops", "sre", "infrastructure")):
        return "platform_devops"
    return "software_general"


@router.post("/refine")
async def refine_onboarding(
    body: RefineAnswer,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Profile).where(Profile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=404, detail="Profile not found — upload resume first"
        )

    answer = body.answer
    qid = body.question_id

    if qid == "salary_expectations":
        if value := _parse_salary(answer):
            profile.min_salary = value
    elif qid == "target_roles":
        roles = _answer_values(answer)
        overrides = deepcopy(profile.config_overrides or {})
        intent = overrides.setdefault("profile_intent", {})
        intent["roles"] = roles
        intent["preset"] = _infer_role_preset(roles)
        profile.config_overrides = overrides
        profile.target_roles = roles
    elif qid == "preferred_locations":
        locations = _answer_values(answer)
        overrides = deepcopy(profile.config_overrides or {})
        overrides.setdefault("scraping", {})["locations"] = locations
        scoring = overrides.setdefault("location_scoring", {})
        scoring["preferred_locations"] = locations
        scoring["preferred_weight"] = 1.4
        profile.config_overrides = overrides
        profile.preferred_locations = locations
    elif qid == "company_tiers":
        overrides = deepcopy(profile.config_overrides or {})
        tier_lookup = {
            "s-tier (faang, top startups)": "tier_s",
            "a-tier (strong tech companies)": "tier_a",
            "b-tier (good companies)": "tier_b",
            "any company": "any",
        }
        tiers = [
            tier_lookup.get(value.casefold(), value) for value in _answer_values(answer)
        ]
        allowed_tiers = {"tier_s", "tier_a", "tier_b", "any"}
        if set(tiers) - allowed_tiers or ("any" in tiers and len(tiers) > 1):
            raise HTTPException(
                status_code=422, detail="Invalid company tier selection"
            )
        overrides.setdefault("company_preferences", {})["tiers"] = tiers
        profile.config_overrides = overrides
    elif qid == "preferred_companies":
        companies = _answer_values(answer)
        overrides = deepcopy(profile.config_overrides or {})
        overrides.setdefault("company_preferences", {})["preferred_companies"] = (
            companies
        )
        profile.target_companies = companies
        profile.config_overrides = overrides
    elif qid == "excluded_companies":
        overrides = deepcopy(profile.config_overrides or {})
        exclusions = _answer_values(answer)
        overrides.setdefault("company_preferences", {})["excluded_companies"] = (
            exclusions
        )
        profile.config_overrides = overrides
    elif qid == "excluded_titles":
        overrides = deepcopy(profile.config_overrides or {})
        overrides["title_blocklist"] = _answer_values(answer)
        profile.config_overrides = overrides
    elif qid == "onboarding_complete":
        profile.onboarding_complete = True

    await db.commit()
    return {"status": "saved", "question_id": qid}

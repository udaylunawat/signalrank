import hashlib
import io
import logging
import re
from copy import deepcopy

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.deps import get_current_user
from api.deps_llm import get_llm_client
from api.models import Profile, User
from llm.onboarding import generate_onboarding_questions
from llm.openrouter import OpenRouterClient
from llm.resume_parser import RESUME_PARSER_VERSION, parse_resume

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])
MAX_RESUME_BYTES = 10 * 1024 * 1024


def _extracted_payload(parsed) -> dict:
    return {
        "skills": parsed.skills,
        "years_of_experience": parsed.years_of_experience,
        "recent_titles": parsed.recent_titles,
        "industries": parsed.industries,
        "education": parsed.education,
        "skill_evidence": parsed.skill_evidence,
        "experiences": parsed.experiences,
        "declared_years_of_experience": parsed.declared_years_of_experience,
        "computed_years_of_experience": parsed.computed_years_of_experience,
        "field_confidence": parsed.field_confidence,
        "intent_suggestions": parsed.intent_suggestions,
        "parse_status": parsed.status,
        "parse_confidence": parsed.confidence,
        "parse_source": parsed.source,
        "parser_model": parsed.model,
        "parse_error": parsed.error,
    }


def _apply_parsed_profile(profile: Profile, parsed) -> None:
    profile.skills = parsed.skills
    if parsed.years_of_experience is not None and profile.max_yoe is None:
        profile.max_yoe = parsed.years_of_experience
    profile.resume_parse_status = parsed.status
    profile.resume_parse_error = parsed.error
    profile.resume_parse_confidence = parsed.confidence
    profile.resume_parser_model = parsed.model
    if parsed.skills or parsed.recent_titles or parsed.years_of_experience:
        parts = []
        if parsed.recent_titles:
            parts.append("Recent roles: " + ", ".join(parsed.recent_titles))
        if parsed.skills:
            parts.append("Skills: " + ", ".join(parsed.skills))
        if parsed.years_of_experience:
            parts.append(f"Experience: {parsed.years_of_experience} years")
        profile.distilled_text = "\n".join(parts)


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
    content = await file.read(MAX_RESUME_BYTES + 1)
    if len(content) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=413, detail="Resume must be 10 MB or smaller")
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

    result = await db.execute(select(Profile).where(Profile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = Profile(user_id=current_user.id)
        db.add(profile)

    resume_sha256 = hashlib.sha256(content).hexdigest()
    if (
        profile.resume_sha256 == resume_sha256
        and profile.onboarding_draft
        and profile.resume_parse_status == "complete"
        and profile.onboarding_draft.get("parser_version") == RESUME_PARSER_VERSION
    ):
        return profile.onboarding_draft

    parsed = await parse_resume(resume_text, llm)

    profile.resume_text = resume_text
    _apply_parsed_profile(profile, parsed)
    profile.resume_sha256 = resume_sha256
    questions = generate_onboarding_questions(parsed)
    draft = {
        "extracted": _extracted_payload(parsed),
        "questions": questions,
        "answers": {},
        "current_step": "questions",
        "resume_filename": file.filename,
        "resume_sha256": resume_sha256,
        "parser_version": RESUME_PARSER_VERSION,
    }
    profile.onboarding_draft = draft
    profile.onboarding_complete = False
    await db.commit()
    return draft


@router.post("/resume/retry")
async def retry_resume_parse(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm: OpenRouterClient = Depends(get_llm_client),
):
    result = await db.execute(select(Profile).where(Profile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if not profile or not profile.resume_text:
        raise HTTPException(status_code=404, detail="Upload a resume first")

    parsed = await parse_resume(profile.resume_text, llm)
    _apply_parsed_profile(profile, parsed)
    previous_draft = deepcopy(profile.onboarding_draft or {})
    draft = {
        **previous_draft,
        "extracted": _extracted_payload(parsed),
        "questions": generate_onboarding_questions(parsed),
        "answers": previous_draft.get("answers", {}),
        "current_step": "questions",
        "parser_version": RESUME_PARSER_VERSION,
    }
    profile.onboarding_draft = draft
    await db.commit()
    return draft


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
        "draft": profile.onboarding_draft if profile else None,
        "parse_status": profile.resume_parse_status if profile else None,
        "parse_confidence": profile.resume_parse_confidence if profile else None,
        "parse_error": profile.resume_parse_error if profile else None,
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
        intent.pop("preset", None)
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
            "s-tier (exceptional reputation)": "tier_s",
            "a-tier (strong reputation)": "tier_a",
            "b-tier (established reputation)": "tier_b",
            "c-tier (limited reputation evidence)": "tier_c",
            "any company": "any",
        }
        tiers = [
            tier_lookup.get(value.casefold(), value) for value in _answer_values(answer)
        ]
        allowed_tiers = {"tier_s", "tier_a", "tier_b", "tier_c", "any"}
        if set(tiers) - allowed_tiers or ("any" in tiers and len(tiers) > 1):
            raise HTTPException(
                status_code=422, detail="Invalid company tier selection"
            )
        overrides.setdefault("company_preferences", {})["tiers"] = tiers
        overrides["company_preferences"]["filter_mode"] = (
            "all" if tiers == ["any"] else "selected_tiers"
        )
        profile.config_overrides = overrides
    elif qid == "company_filter_mode":
        mode = str(answer[0] if isinstance(answer, list) and answer else answer)
        if mode not in {"all", "top_reputed", "selected_tiers"}:
            raise HTTPException(status_code=422, detail="Invalid company filter mode")
        overrides = deepcopy(profile.config_overrides or {})
        preferences = overrides.setdefault("company_preferences", {})
        preferences["filter_mode"] = mode
        if mode == "all":
            preferences["tiers"] = ["any"]
        elif mode == "top_reputed":
            preferences["tiers"] = ["tier_s", "tier_a"]
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

    draft = deepcopy(profile.onboarding_draft or {})
    answers = draft.setdefault("answers", {})
    answers[qid] = answer
    draft["current_step"] = "complete" if qid == "onboarding_complete" else qid
    profile.onboarding_draft = draft

    await db.commit()
    return {"status": "saved", "question_id": qid, "draft": draft}

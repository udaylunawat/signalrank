from copy import deepcopy

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.deps import get_current_user
from api.models import Profile, User

router = APIRouter(prefix="/api", tags=["profile"])


class ProfileUpdate(BaseModel):
    resume_text: str | None = None
    distilled_text: str | None = None
    min_salary: int | None = None
    min_yoe: int | None = None
    max_yoe: int | None = None
    role_intent: str | None = None
    target_roles: list[str] | None = None
    target_companies: list[str] | None = None
    preferred_locations: list[str] | None = None
    config_overrides: dict | None = None
    onboarding_complete: bool | None = None

    @field_validator("config_overrides")
    @classmethod
    def validate_company_tiers(cls, value: dict | None) -> dict | None:
        if value is None:
            return value
        tiers = value.get("company_preferences", {}).get("tiers", [])
        allowed = {"tier_s", "tier_a", "tier_b", "tier_c", "any"}
        unknown = {str(tier) for tier in tiers} - allowed
        if unknown:
            raise ValueError(f"Unknown company tiers: {', '.join(sorted(unknown))}")
        if "any" in tiers and len(tiers) > 1:
            raise ValueError("Any company cannot be combined with specific tiers")
        filter_mode = value.get("company_preferences", {}).get("filter_mode", "all")
        allowed_modes = {"all", "top_reputed", "selected_tiers"}
        if filter_mode not in allowed_modes:
            raise ValueError(f"Unknown company filter mode: {filter_mode}")
        intent = value.get("profile_intent", {})
        if not isinstance(intent, dict):
            raise ValueError("profile_intent must be an object")
        roles = intent.get("roles", [])
        if not isinstance(roles, list) or any(
            not isinstance(role, str) or not role.strip() for role in roles
        ):
            raise ValueError("profile_intent.roles must be a list of non-empty text")
        aliases = intent.get("role_aliases", {})
        if not isinstance(aliases, dict) or any(
            not isinstance(role, str)
            or not isinstance(values, list)
            or any(not isinstance(alias, str) or not alias.strip() for alias in values)
            for role, values in aliases.items()
        ):
            raise ValueError("profile_intent.role_aliases must map text to text lists")
        return value


@router.get("/profile")
async def get_profile(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Profile).where(Profile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "profile": (
            {
                "resume_text": profile.resume_text if profile else None,
                "distilled_text": profile.distilled_text if profile else None,
                "min_salary": profile.min_salary if profile else None,
                "role_intent": profile.role_intent if profile else None,
                "target_roles": profile.target_roles if profile else None,
                "target_companies": profile.target_companies if profile else None,
                "preferred_locations": profile.preferred_locations if profile else None,
                "config_overrides": profile.config_overrides if profile else None,
                "onboarding_draft": profile.onboarding_draft if profile else None,
                "resume_parse_status": profile.resume_parse_status if profile else None,
                "resume_parse_error": profile.resume_parse_error if profile else None,
                "resume_parse_confidence": (
                    profile.resume_parse_confidence if profile else None
                ),
                "resume_parser_model": profile.resume_parser_model if profile else None,
                "onboarding_complete": (
                    profile.onboarding_complete if profile else False
                ),
            }
            if profile
            else None
        ),
    }


@router.patch("/profile", status_code=200)
async def update_profile(
    body: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Profile).where(Profile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = Profile(user_id=current_user.id)
        db.add(profile)

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(profile, field, value)

    if "config_overrides" not in updates:
        overrides = deepcopy(profile.config_overrides or {})
        if "target_roles" in updates:
            intent = overrides.setdefault("profile_intent", {})
            intent["roles"] = updates["target_roles"] or []
            intent.pop("preset", None)
        if "preferred_locations" in updates:
            locations = updates["preferred_locations"] or []
            overrides.setdefault("scraping", {})["locations"] = locations
            overrides.setdefault("location_scoring", {})[
                "preferred_locations"
            ] = locations
        profile.config_overrides = overrides

    await db.commit()
    return {"status": "updated"}

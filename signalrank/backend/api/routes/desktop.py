import logging
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import create_access_token
from api.config import (
    is_desktop_mode,
    load_or_create_desktop_install_secret,
    settings,
)
from api.database import get_db
from api.models import Profile, User
from llm.openrouter import OpenRouterClient

router = APIRouter(prefix="/api/desktop", tags=["desktop"])
logger = logging.getLogger(__name__)

DESKTOP_USER_EMAIL = "local@signalrank.desktop"
KEYRING_SERVICE = "SignalRank Desktop"
KEYRING_USERNAME = "openrouter_api_key"
_session_openrouter_key = ""


class ProviderKeyRequest(BaseModel):
    provider: str = "openrouter"
    api_key: str


def require_desktop_bootstrap(
    token: str | None = Header(
        default=None,
        alias="X-SignalRank-Desktop-Token",
    ),
) -> None:
    if not is_desktop_mode():
        raise HTTPException(status_code=404, detail="Desktop endpoints are disabled")
    expected = settings.signalrank_desktop_bootstrap_token.strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Desktop bootstrap token is not configured",
        )
    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid desktop bootstrap token",
        )


def _load_keyring_key() -> str:
    try:
        import keyring

        return (keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME) or "").strip()
    except Exception as exc:
        logger.debug(
            "Desktop credential-store read unavailable: %s", type(exc).__name__
        )
        return ""


def _save_keyring_key(api_key: str) -> bool:
    try:
        import keyring

        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, api_key)
        return True
    except Exception as exc:
        logger.debug(
            "Desktop credential-store write unavailable: %s", type(exc).__name__
        )
        return False


def _delete_keyring_key() -> bool:
    try:
        import keyring

        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
        except keyring.errors.PasswordDeleteError:
            pass
        return True
    except Exception as exc:
        logger.debug(
            "Desktop credential-store delete unavailable: %s", type(exc).__name__
        )
        return False


def load_openrouter_key() -> str:
    global _session_openrouter_key
    if _session_openrouter_key:
        return _session_openrouter_key
    key = _load_keyring_key()
    if key:
        _session_openrouter_key = key
        settings.openrouter_api_key = key
    return key


def _reset_llm_client() -> None:
    import api.deps_llm as deps_llm

    deps_llm._client = None


async def ensure_desktop_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == DESKTOP_USER_EMAIL))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(email=DESKTOP_USER_EMAIL, password_hash=None, provider="desktop")
        db.add(user)
        try:
            await db.flush()
            await db.commit()
        except IntegrityError:
            await db.rollback()
        user = (
            await db.execute(select(User).where(User.email == DESKTOP_USER_EMAIL))
        ).scalar_one()

    profile = (
        await db.execute(select(Profile).where(Profile.user_id == user.id))
    ).scalar_one_or_none()
    if profile is None:
        db.add(Profile(user_id=user.id))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
    return user


@router.get("/status", dependencies=[Depends(require_desktop_bootstrap)])
async def desktop_status(db: AsyncSession = Depends(get_db)):
    user = await ensure_desktop_user(db)
    profile = (
        await db.execute(select(Profile).where(Profile.user_id == user.id))
    ).scalar_one()
    return {
        "mode": "desktop",
        "provider_configured": bool(load_openrouter_key()),
        "resume_uploaded": bool(profile.resume_text),
        "onboarding_complete": bool(profile.onboarding_complete),
        "user_id": user.id,
    }


@router.post("/session", dependencies=[Depends(require_desktop_bootstrap)])
async def desktop_session(db: AsyncSession = Depends(get_db)):
    user = await ensure_desktop_user(db)
    if not settings.nextauth_secret:
        settings.nextauth_secret = load_or_create_desktop_install_secret(
            settings.signalrank_app_data_dir
        )
    return {
        "access_token": create_access_token(user.id, user.email),
        "token_type": "bearer",
    }


@router.post("/provider-key", dependencies=[Depends(require_desktop_bootstrap)])
async def save_provider_key(body: ProviderKeyRequest):
    global _session_openrouter_key
    if body.provider.strip().lower() != "openrouter":
        raise HTTPException(status_code=422, detail="Only OpenRouter is supported")
    api_key = body.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=422, detail="OpenRouter API key is required")

    client = OpenRouterClient(api_key=api_key, timeout=15.0)
    try:
        preflight = await client.preflight()
    finally:
        await client.close()
    if not preflight.authenticated:
        raise HTTPException(
            status_code=400,
            detail=preflight.details or "OpenRouter key could not be validated",
        )
    if not preflight.compatible_free_models:
        raise HTTPException(
            status_code=400,
            detail=preflight.details
            or "No compatible free structured-output model is available",
        )

    persisted = _save_keyring_key(api_key)
    _session_openrouter_key = api_key
    settings.openrouter_api_key = api_key
    _reset_llm_client()
    return {
        "status": "ok",
        "provider": "openrouter",
        "persistence": "credential_store" if persisted else "session",
        "preflight_status": preflight.status,
        "compatible_free_models": list(preflight.compatible_free_models),
    }


@router.delete("/provider-key", dependencies=[Depends(require_desktop_bootstrap)])
async def delete_provider_key():
    global _session_openrouter_key
    if _load_keyring_key() and not _delete_keyring_key():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not remove the key from the operating system credential store",
        )
    _session_openrouter_key = ""
    settings.openrouter_api_key = ""
    _reset_llm_client()
    return {"status": "ok", "provider_configured": False}

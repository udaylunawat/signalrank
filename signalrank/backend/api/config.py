import json
import os
import secrets
import sys
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


APP_ID = "app.signalrank.desktop"


def desktop_data_dir(configured: str | None = None) -> Path:
    value = (
        configured
        if configured is not None
        else os.getenv("SIGNALRANK_APP_DATA_DIR", "")
    )
    if value:
        root = Path(value).expanduser()
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / APP_ID
    elif sys.platform.startswith("win"):
        root = Path(os.getenv("APPDATA", str(Path.home()))) / APP_ID
    else:
        data_home = Path(
            os.getenv("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
        )
        root = data_home / APP_ID
    root.mkdir(parents=True, exist_ok=True)
    return root


def _is_desktop_environment() -> bool:
    return os.getenv("SIGNALRANK_MODE", "").strip().lower() == "desktop"


def _default_database_url() -> str:
    if _is_desktop_environment():
        return f"sqlite+aiosqlite:///{desktop_data_dir() / 'signalrank.db'}"
    return "postgresql+asyncpg://postgres:postgres@localhost:5432/signalrank"


def load_or_create_desktop_install_secret(
    configured_data_dir: str | None = None,
    *,
    require_desktop_env: bool = False,
) -> str:
    if require_desktop_env and not _is_desktop_environment():
        return ""
    path = desktop_data_dir(configured_data_dir) / "install-secret"
    try:
        existing = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        existing = ""
    if len(existing) >= 32:
        return existing

    secret = secrets.token_urlsafe(48)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        existing = path.read_text(encoding="utf-8").strip()
        if len(existing) >= 32:
            return existing
        path.unlink(missing_ok=True)
        return load_or_create_desktop_install_secret(configured_data_dir)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(secret)
    return secret


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    signalrank_mode: str = "server"
    signalrank_app_data_dir: str = ""
    signalrank_desktop_bootstrap_token: str = ""
    database_url: str = _default_database_url()
    nextauth_secret: str = load_or_create_desktop_install_secret(
        require_desktop_env=True
    )
    environment: str = "development"
    allowed_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    openrouter_api_key: str = ""
    desktop_busy_timeout_ms: int = 10_000
    desktop_company_enrichment_limit: int = 15
    desktop_company_enrichment_timeout_seconds: float = 45.0

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if not isinstance(value, str):
            return value
        text = value.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        return [item.strip() for item in text.split(",") if item.strip()]


settings = Settings()
if settings.signalrank_mode.strip().lower() == "desktop":
    settings.database_url = (
        f"sqlite+aiosqlite:///"
        f"{desktop_data_dir(settings.signalrank_app_data_dir) / 'signalrank.db'}"
    )
    settings.nextauth_secret = load_or_create_desktop_install_secret(
        settings.signalrank_app_data_dir
    )
    settings.openrouter_api_key = ""


def is_desktop_mode() -> bool:
    return settings.signalrank_mode.strip().lower() == "desktop"


def configured_desktop_data_dir() -> Path:
    return desktop_data_dir(settings.signalrank_app_data_dir)

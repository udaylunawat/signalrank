import asyncio
import logging
import re
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from api.config import is_desktop_mode, settings

logger = logging.getLogger(__name__)
DESKTOP_SCHEMA_VERSION = 4
desktop_writer_lock = asyncio.Lock()


def _normalize_database_url(url: str) -> str:
    if url.startswith("sqlite"):
        return url
    return re.sub(r"^postgresql(?:\+\w+)?://", "postgresql+asyncpg://", url)


def _build_engine(url: str):
    normalized = _normalize_database_url(url)
    engine_kwargs: dict = {"echo": False}
    if normalized.startswith("sqlite"):
        engine_kwargs["connect_args"] = {
            "timeout": settings.desktop_busy_timeout_ms / 1000
        }
    built_engine = create_async_engine(normalized, **engine_kwargs)
    if normalized.startswith("sqlite"):

        @event.listens_for(built_engine.sync_engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute(f"PRAGMA busy_timeout={settings.desktop_busy_timeout_ms}")
            cursor.close()

    return built_engine


engine = _build_engine(settings.database_url)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def _sqlite_path(url: str) -> Path | None:
    parsed = make_url(_normalize_database_url(url))
    if parsed.get_backend_name() != "sqlite" or not parsed.database:
        return None
    return Path(parsed.database)


def _read_desktop_schema_version(path: Path) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    import sqlite3

    with sqlite3.connect(path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='desktop_schema_version'"
        ).fetchone()
        if not exists:
            return 0
        row = connection.execute(
            "SELECT version FROM desktop_schema_version WHERE id=1"
        ).fetchone()
        return int(row[0]) if row else 0


def _backup_before_migration(path: Path, old_version: int) -> Path | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_dir / f"signalrank-v{old_version}-{timestamp}.db"
    import sqlite3

    with sqlite3.connect(path) as source, sqlite3.connect(backup) as destination:
        source.backup(destination)
    return backup


async def initialize_database(bind=None) -> None:
    target = bind or engine
    if target.dialect.name != "sqlite":
        return

    path = _sqlite_path(str(target.url))
    current_version = _read_desktop_schema_version(path) if path else 0
    if current_version > DESKTOP_SCHEMA_VERSION:
        raise RuntimeError("Desktop database was created by a newer SignalRank version")
    if path and current_version < DESKTOP_SCHEMA_VERSION:
        backup = _backup_before_migration(path, current_version)
        if backup:
            logger.info("Created desktop database migration backup at %s", backup)

    async with desktop_writer_lock, target.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_jobs_raw_active_last_seen "
                "ON jobs_raw (active, last_seen)"
            )
        )
        await connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_runs_user_status_finished_at "
                "ON runs (user_id, status, finished_at)"
            )
        )
        await connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_job_results_run_user_score "
                "ON job_results (run_id, user_id, final_score)"
            )
        )
        await connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_job_results_run_user_job "
                "ON job_results (run_id, user_id, job_id)"
            )
        )
        await connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS desktop_schema_version "
                "(id INTEGER PRIMARY KEY CHECK (id = 1), version INTEGER NOT NULL)"
            )
        )
        await connection.execute(
            text(
                "INSERT INTO desktop_schema_version (id, version) VALUES (1, :version) "
                "ON CONFLICT(id) DO UPDATE SET version=excluded.version"
            ),
            {"version": DESKTOP_SCHEMA_VERSION},
        )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def desktop_database_path() -> Path | None:
    if not is_desktop_mode():
        return None
    return _sqlite_path(settings.database_url)

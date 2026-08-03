import asyncio
import os
import time
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from api.config import settings
from api.database import _build_engine, get_db, initialize_database
from api.desktop_main import _desktop_parent_pid, _process_is_running
from api.main import app
from api.models import Embedding, Profile, Run, User
from api.routes import desktop
from batch.embedding_cache import PgEmbeddingCache
from batch.worker import _claim_next_run


def test_desktop_parent_pid_accepts_a_valid_process(monkeypatch):
    monkeypatch.setenv("SIGNALRANK_DESKTOP_PARENT_PID", "1234")

    assert _desktop_parent_pid() == 1234


@pytest.mark.parametrize("value", ["", "invalid", "0", "1", "-1"])
def test_desktop_parent_pid_rejects_invalid_values(monkeypatch, value):
    monkeypatch.setenv("SIGNALRANK_DESKTOP_PARENT_PID", value)

    assert _desktop_parent_pid() is None


def test_desktop_parent_watch_detects_current_process():
    assert _process_is_running(os.getpid())


@pytest.fixture
async def desktop_runtime(tmp_path, monkeypatch):
    database_path = tmp_path / "signalrank.db"
    engine = _build_engine(f"sqlite+aiosqlite:///{database_path}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    await initialize_database(engine)

    monkeypatch.setattr(settings, "signalrank_mode", "desktop")
    monkeypatch.setattr(settings, "signalrank_app_data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "signalrank_desktop_bootstrap_token", "test-token")
    monkeypatch.setattr(
        settings, "nextauth_secret", "test-session-secret-32-bytes-long"
    )
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(desktop, "_session_openrouter_key", "")
    monkeypatch.setattr(desktop, "_keyring_load_task", None)
    monkeypatch.setattr(desktop, "_load_keyring_key", lambda: "")

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    client = AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://127.0.0.1",
    )
    try:
        yield client, engine, session_factory, database_path
    finally:
        await client.aclose()
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


async def test_desktop_routes_require_bootstrap_and_create_local_identity(
    desktop_runtime,
):
    client, _, session_factory, _ = desktop_runtime

    unauthorized = await client.get("/api/desktop/status")
    assert unauthorized.status_code == 401

    headers = {"X-SignalRank-Desktop-Token": "test-token"}
    status_response = await client.get("/api/desktop/status", headers=headers)
    session_response = await client.post("/api/desktop/session", headers=headers)

    assert status_response.status_code == 200
    assert status_response.json() == {
        "mode": "desktop",
        "provider_configured": False,
        "resume_uploaded": False,
        "onboarding_complete": False,
        "user_id": status_response.json()["user_id"],
    }
    assert session_response.status_code == 200
    assert session_response.json()["access_token"]

    async with session_factory() as db:
        users = (
            (
                await db.execute(
                    select(User).where(User.email == desktop.DESKTOP_USER_EMAIL)
                )
            )
            .scalars()
            .all()
        )
        profile = (
            await db.execute(select(Profile).where(Profile.user_id == users[0].id))
        ).scalar_one()
    assert len(users) == 1
    assert users[0].provider == "desktop"
    assert profile.user_id == users[0].id


async def test_desktop_session_can_trigger_first_scan(desktop_runtime):
    client, _, _, _ = desktop_runtime
    bootstrap_headers = {"X-SignalRank-Desktop-Token": "test-token"}
    session_response = await client.post(
        "/api/desktop/session", headers=bootstrap_headers
    )
    token = session_response.json()["access_token"]

    trigger_response = await client.post(
        "/api/runs/trigger",
        headers={
            **bootstrap_headers,
            "Authorization": f"Bearer {token}",
        },
    )

    assert trigger_response.status_code == 202
    assert trigger_response.json()["status"] == "pending"


async def test_desktop_provider_key_uses_keyring_or_session_only(
    desktop_runtime, monkeypatch
):
    client, _, _, database_path = desktop_runtime
    saved: list[str] = []

    class FakeOpenRouterClient:
        def __init__(self, api_key, timeout):
            assert api_key == "sk-or-test"
            assert timeout == 15.0

        async def preflight(self):
            return SimpleNamespace(
                status="ready",
                authenticated=True,
                compatible_free_models=("example/model:free",),
                details=None,
            )

        async def close(self):
            return None

    monkeypatch.setattr(desktop, "OpenRouterClient", FakeOpenRouterClient)
    monkeypatch.setattr(
        desktop, "_save_keyring_key", lambda key: saved.append(key) or False
    )

    response = await client.post(
        "/api/desktop/provider-key",
        headers={"X-SignalRank-Desktop-Token": "test-token"},
        json={"provider": "openrouter", "api_key": "sk-or-test"},
    )

    assert response.status_code == 200
    assert response.json()["persistence"] == "session"
    assert saved == ["sk-or-test"]
    assert desktop._session_openrouter_key == "sk-or-test"
    database_bytes = database_path.read_bytes()
    assert b"sk-or-test" not in database_bytes
    assert not list(database_path.parent.glob("*.json"))


async def test_desktop_keyring_key_is_loaded_before_worker_use(
    desktop_runtime, monkeypatch
):
    monkeypatch.setattr(desktop, "_session_openrouter_key", "")
    monkeypatch.setattr(desktop, "_load_keyring_key", lambda: "sk-or-persisted")

    assert desktop.load_openrouter_key() == "sk-or-persisted"
    assert settings.openrouter_api_key == "sk-or-persisted"


async def test_desktop_keyring_timeout_does_not_block_api(desktop_runtime, monkeypatch):
    monkeypatch.setattr(desktop, "_session_openrouter_key", "")
    monkeypatch.setattr(desktop, "KEYRING_TIMEOUT_SECONDS", 0.005)
    monkeypatch.setattr(desktop, "_load_keyring_key", lambda: time.sleep(0.05) or "")

    started = time.monotonic()
    assert await desktop.load_openrouter_key_async() == ""
    assert time.monotonic() - started < 0.04
    await asyncio.sleep(0.06)


async def test_sqlite_pragmas_embeddings_and_worker_claim_are_portable(
    desktop_runtime,
):
    _, engine, session_factory, _ = desktop_runtime
    async with engine.connect() as connection:
        journal_mode = (await connection.execute(text("PRAGMA journal_mode"))).scalar()
        busy_timeout = (await connection.execute(text("PRAGMA busy_timeout"))).scalar()
    assert journal_mode.lower() == "wal"
    assert busy_timeout == settings.desktop_busy_timeout_ms

    async with session_factory() as db:
        cache = PgEmbeddingCache(db, "cfg")
        await cache.store_vectors([("fingerprint", [1.0, 0.0, 0.0])])
        await db.commit()
        user = User(email="worker@desktop.local", provider="desktop")
        db.add(user)
        await db.flush()
        run = Run(user_id=user.id, status="pending")
        db.add(run)
        await db.commit()

    first, second = await asyncio.gather(
        _claim_next_run(session_factory, "worker-a"),
        _claim_next_run(session_factory, "worker-b"),
    )
    assert sorted((first is None, second is None)) == [False, True]

    async with session_factory() as db:
        stored = (
            await db.execute(
                select(Embedding).where(Embedding.text_fp == "fingerprint")
            )
        ).scalar_one()
    assert stored.vector == [1.0, 0.0, 0.0]


async def test_desktop_schema_migration_creates_backup(desktop_runtime):
    _, engine, _, database_path = desktop_runtime
    async with engine.begin() as connection:
        await connection.execute(
            text("UPDATE desktop_schema_version SET version=0 WHERE id=1")
        )

    await initialize_database(engine)

    backups = list((database_path.parent / "backups").glob("signalrank-v0-*.db"))
    assert len(backups) == 1
    assert backups[0].stat().st_size > 0

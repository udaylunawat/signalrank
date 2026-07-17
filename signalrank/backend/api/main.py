import asyncio
import logging
from contextlib import asynccontextmanager

from batch.worker import worker_loop
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.config import is_desktop_mode, settings
from api.database import AsyncSessionLocal, initialize_database
from api.routes import (
    applications,
    auth,
    desktop,
    feedback,
    jobs,
    onboarding,
    profile,
    resume,
    runs,
)

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_database()
    if is_desktop_mode():
        desktop.load_openrouter_key()
    worker_task = asyncio.create_task(
        worker_loop(AsyncSessionLocal), name="signalrank-durable-worker"
    )
    app.state.worker_task = worker_task
    try:
        yield
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="SignalRank API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=(
        r"^http://(?:localhost|127\.0\.0\.1):\d+$" if is_desktop_mode() else None
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def enforce_desktop_loopback(request: Request, call_next):
    if not is_desktop_mode():
        return await call_next(request)

    if request.url.path.startswith("/api/auth/"):
        return JSONResponse(
            status_code=404, content={"detail": "Cloud authentication is disabled"}
        )

    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        return JSONResponse(status_code=403, content={"detail": "Loopback only"})

    host = request.headers.get("host", "").split(":", 1)[0].strip("[]").lower()
    if host not in {"127.0.0.1", "::1", "localhost"}:
        return JSONResponse(status_code=400, content={"detail": "Invalid host"})

    origin = request.headers.get("origin")
    if origin:
        from urllib.parse import urlparse

        origin_host = (urlparse(origin).hostname or "").lower()
        if origin_host not in {"127.0.0.1", "::1", "localhost"}:
            return JSONResponse(status_code=403, content={"detail": "Invalid origin"})
    return await call_next(request)


app.include_router(desktop.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(runs.router)
app.include_router(jobs.router)
app.include_router(feedback.router)
app.include_router(applications.router)
app.include_router(onboarding.router)
app.include_router(resume.router)


@app.get("/health")
async def health():
    return {"status": "ok"}

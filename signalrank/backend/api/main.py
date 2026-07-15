import asyncio
import logging
from contextlib import asynccontextmanager

from batch.worker import worker_loop
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.database import AsyncSessionLocal
from api.routes import applications, auth, jobs, onboarding, profile, resume, runs

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(runs.router)
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(onboarding.router)
app.include_router(resume.router)


@app.get("/health")
async def health():
    return {"status": "ok"}

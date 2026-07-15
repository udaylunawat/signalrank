from datetime import datetime

from batch.worker import wake_worker
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.database import get_db
from api.deps import get_current_user
from api.models import Run, User

router = APIRouter(prefix="/api/runs", tags=["runs"])


class SourceTelemetryResponse(BaseModel):
    source: str
    query: str | None = None
    location: str | None = None
    status: str
    jobs_found: int
    jobs_persisted: int
    duration_ms: int | None = None
    error_summary: str | None = None
    started_at: datetime
    finished_at: datetime


class RunResponse(BaseModel):
    run_id: str
    status: str
    stage: str
    progress: int
    job_count: int | None = None
    error_summary: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    attempt_count: int = 0
    sources: list[SourceTelemetryResponse] = Field(default_factory=list)


def _response(run: Run) -> RunResponse:
    telemetry = sorted(
        run.source_telemetry,
        key=lambda item: (item.started_at, item.source, item.query or ""),
    )
    return RunResponse(
        run_id=run.id,
        status=run.status,
        stage=run.stage,
        progress=run.progress,
        job_count=run.job_count,
        error_summary=run.error_summary,
        started_at=str(run.started_at) if run.started_at else None,
        finished_at=str(run.finished_at) if run.finished_at else None,
        attempt_count=run.attempt_count,
        sources=[
            SourceTelemetryResponse(
                source=item.source,
                query=item.query,
                location=item.location,
                status=item.status,
                jobs_found=item.jobs_found,
                jobs_persisted=item.jobs_persisted,
                duration_ms=item.duration_ms,
                error_summary=item.error_summary,
                started_at=item.started_at,
                finished_at=item.finished_at,
            )
            for item in telemetry
        ],
    )


async def _load_run(db: AsyncSession, run_id: str, user_id: str) -> Run | None:
    result = await db.execute(
        select(Run)
        .options(selectinload(Run.source_telemetry))
        .where(Run.id == run_id, Run.user_id == user_id)
    )
    return result.scalar_one_or_none()


@router.post("/trigger", status_code=202)
async def trigger_run(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        select(User.id).where(User.id == current_user.id).with_for_update()
    )
    active_result = await db.execute(
        select(Run)
        .where(
            Run.user_id == current_user.id,
            Run.status.in_(("pending", "running")),
        )
        .order_by(Run.started_at.desc())
        .limit(1)
    )
    active_run = active_result.scalar_one_or_none()
    if active_run is not None:
        await db.commit()
        wake_worker()
        return {
            "run_id": active_run.id,
            "status": active_run.status,
            "stage": active_run.stage,
            "progress": active_run.progress,
            "coalesced": True,
        }

    run = Run(
        user_id=current_user.id,
        status="pending",
        stage="queued",
        progress=0,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    wake_worker()

    return {
        "run_id": run.id,
        "status": run.status,
        "stage": run.stage,
        "progress": run.progress,
        "coalesced": False,
    }


@router.get("/latest", response_model=RunResponse)
async def get_latest_run(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Run)
        .options(selectinload(Run.source_telemetry))
        .where(Run.user_id == current_user.id)
        .order_by(Run.started_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="No runs found")
    return _response(run)


@router.get("/{run_id}/status", response_model=RunResponse)
async def get_run_status(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    run = await _load_run(db, run_id, current_user.id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _response(run)

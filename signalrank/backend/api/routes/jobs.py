import csv
import json
from io import StringIO
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.deps import get_current_user
from api.models import JobFeedback, JobRaw, JobResult, Run, User

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

CSV_COLUMNS = (
    "run_id",
    "run_completed_at",
    "job_id",
    "title",
    "company",
    "location",
    "source",
    "job_url",
    "date_posted",
    "description",
    "final_score",
    "semantic_score",
    "skills_score",
    "company_score",
    "seniority_score",
    "location_score",
    "recency_score",
    "company_tier",
    "company_reputation_confidence",
    "company_reputation_rationale",
    "score_explanation_json",
    "is_contract",
)


async def _latest_completed_run(db: AsyncSession, user_id: str) -> Run | None:
    result = await db.execute(
        select(Run)
        .where(Run.user_id == user_id, Run.status.in_(("success", "partial")))
        .order_by(Run.finished_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _safe_csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


@router.get("")
async def list_jobs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    q: str | None = Query(None, max_length=200),
    min_score: float | None = Query(None, ge=0, le=100),
    source: str | None = Query(None, max_length=100),
    sort: Literal["match", "newest", "company"] = Query("match"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    run = await _latest_completed_run(db, current_user.id)
    if not run:
        return {
            "jobs": [],
            "total": 0,
            "page": page,
            "limit": limit,
            "run_id": None,
            "completed_at": None,
            "strong_count": 0,
            "source_counts": {},
        }

    filters = [
        JobResult.run_id == run.id,
        JobResult.user_id == current_user.id,
    ]
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                JobRaw.title.ilike(pattern),
                JobRaw.company.ilike(pattern),
                JobRaw.location.ilike(pattern),
            )
        )
    if min_score is not None:
        filters.append(JobResult.final_score >= min_score)
    if source:
        filters.append(func.lower(JobRaw.site) == source.strip().lower())

    total_result = await db.execute(
        select(func.count())
        .select_from(JobResult)
        .join(JobRaw, JobResult.job_id == JobRaw.id)
        .where(*filters)
    )
    total = total_result.scalar()

    strong_result = await db.execute(
        select(func.count()).where(
            JobResult.run_id == run.id,
            JobResult.user_id == current_user.id,
            JobResult.final_score >= 70,
        )
    )
    strong_count = strong_result.scalar() or 0

    sources_result = await db.execute(
        select(JobRaw.site, func.count())
        .select_from(JobResult)
        .join(JobRaw, JobResult.job_id == JobRaw.id)
        .where(JobResult.run_id == run.id, JobResult.user_id == current_user.id)
        .group_by(JobRaw.site)
    )
    source_counts = {
        str(site or "unknown"): count for site, count in sources_result.all()
    }

    if sort == "newest":
        ordering = (JobRaw.date_posted.desc().nullslast(), JobResult.final_score.desc())
    elif sort == "company":
        ordering = (JobRaw.company.asc().nullslast(), JobResult.final_score.desc())
    else:
        ordering = (JobResult.final_score.desc(), JobRaw.date_posted.desc().nullslast())

    results = await db.execute(
        select(JobResult, JobRaw)
        .join(JobRaw, JobResult.job_id == JobRaw.id)
        .where(*filters)
        .order_by(*ordering)
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = results.all()
    feedback_result = await db.execute(
        select(JobFeedback.job_id, JobFeedback.value, JobFeedback.reason).where(
            JobFeedback.user_id == current_user.id,
            JobFeedback.job_id.in_([job.id for _, job in rows]),
        )
    )
    feedback_by_job = {
        job_id: {"value": value, "reason": reason}
        for job_id, value, reason in feedback_result.all()
    }

    jobs = []
    for result, job in rows:
        jobs.append(
            {
                "id": job.id,
                "job_url": job.job_url,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "site": job.site,
                "date_posted": str(job.date_posted) if job.date_posted else None,
                "final_score": result.final_score,
                "semantic_score": result.semantic_score,
                "skills_score": result.skills_score,
                "company_score": result.company_score,
                "seniority_score": result.seniority_score,
                "location_score": result.location_score,
                "recency_score": result.recency_score,
                "company_tier": result.company_tier,
                "company_reputation_confidence": (result.company_reputation_confidence),
                "company_reputation_rationale": (result.company_reputation_rationale),
                "explanation": result.explanation,
                "is_contract": result.is_contract,
                "feedback": feedback_by_job.get(job.id),
            }
        )

    return {
        "jobs": jobs,
        "total": total,
        "page": page,
        "limit": limit,
        "run_id": run.id,
        "completed_at": str(run.finished_at) if run.finished_at else None,
        "strong_count": strong_count,
        "source_counts": source_counts,
    }


@router.get("/export.csv")
async def export_jobs_csv(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    run = await _latest_completed_run(db, current_user.id)
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)

    if run:
        results = await db.execute(
            select(JobResult, JobRaw)
            .join(JobRaw, JobResult.job_id == JobRaw.id)
            .where(
                JobResult.run_id == run.id,
                JobResult.user_id == current_user.id,
            )
            .order_by(
                JobResult.final_score.desc().nullslast(),
                JobRaw.date_posted.desc().nullslast(),
            )
        )
        completed_at = run.finished_at.isoformat() if run.finished_at else ""
        for result, job in results.all():
            writer.writerow(
                _safe_csv_value(value)
                for value in (
                    run.id,
                    completed_at,
                    job.id,
                    job.title,
                    job.company,
                    job.location,
                    job.site,
                    job.job_url,
                    job.date_posted.isoformat() if job.date_posted else "",
                    job.description,
                    result.final_score,
                    result.semantic_score,
                    result.skills_score,
                    result.company_score,
                    result.seniority_score,
                    result.location_score,
                    result.recency_score,
                    result.company_tier,
                    result.company_reputation_confidence,
                    result.company_reputation_rationale,
                    (
                        json.dumps(
                            result.explanation, ensure_ascii=False, sort_keys=True
                        )
                        if result.explanation
                        else ""
                    ),
                    result.is_contract,
                )
            )

    date_suffix = (
        run.finished_at.date().isoformat()
        if run and run.finished_at
        else "no-completed-run"
    )
    return Response(
        content=f"\ufeff{output.getvalue()}",
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="signalrank-jobs-{date_suffix}.csv"'
            )
        },
    )


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(JobRaw).where(JobRaw.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job.id,
        "job_url": job.job_url,
        "title": job.title,
        "company": job.company,
        "description": job.description,
        "location": job.location,
        "site": job.site,
        "date_posted": str(job.date_posted) if job.date_posted else None,
    }

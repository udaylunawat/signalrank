"""User-scoped review inbox with durable decisions and automatic snooze resurfacing."""

from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import and_, case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.deps import get_current_user
from api.models import Application, JobRaw, JobResult, JobReviewState, User, UserInboxVisit
from api.stats_cache import invalidate_stats_cache
from api.sql_compat import dialect_insert, conflict_kwargs

router = APIRouter(prefix="/api/inbox", tags=["inbox"])
InboxBucket = Literal["new", "since_visit", "reviewed", "due", "snoozed", "dismissed", "saved"]
ReviewDecision = Literal["reviewed", "dismissed", "snoozed", "unreviewed"]
CLOSED_APPLICATION_STATUSES = ("rejected", "archived")


class ReviewUpdate(BaseModel):
    state: ReviewDecision
    snoozed_until: date | None = None

    @model_validator(mode="after")
    def validate_snooze(self):
        if self.state == "snoozed":
            if self.snoozed_until is None or self.snoozed_until <= date.today():
                raise ValueError("Snooze date must be in the future")
        elif self.snoozed_until is not None:
            raise ValueError("snoozed_until is only valid when snoozing a job")
        return self


class BatchReview(BaseModel):
    job_ids: list[str] = Field(min_length=1, max_length=100)


class VisitRequest(BaseModel):
    # Stable across React effect replays within the same page instance.
    client_visit_id: str = Field(min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")


def since_visit_filter(today: date):
    """First matched during the active visit window; not every unreviewed job."""
    return and_(
        inbox_bucket(today) == "new",
        (
            UserInboxVisit.previous_visited_at.is_(None)
            | (JobResult.first_seen_at > UserInboxVisit.previous_visited_at)
        ),
        (
            UserInboxVisit.user_id.is_(None)
            | (JobResult.first_seen_at <= UserInboxVisit.last_visited_at)
        ),
    )


@router.post("/visit")
async def check_inbox_visit(
    body: VisitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    stmt = dialect_insert(db, UserInboxVisit).values(
        user_id=current_user.id,
        previous_visited_at=None,
        last_visited_at=now,
        client_visit_id=body.client_visit_id,
    )
    # The per-user primary key also serializes competing check-ins. Replayed
    # POSTs with the same visit ID leave the cursor unchanged.
    stmt = stmt.on_conflict_do_update(
        **conflict_kwargs(db, index_elements=[UserInboxVisit.user_id]),
        set_={
            "previous_visited_at": UserInboxVisit.last_visited_at,
            "last_visited_at": stmt.excluded.last_visited_at,
            "client_visit_id": stmt.excluded.client_visit_id,
        },
        where=UserInboxVisit.client_visit_id != stmt.excluded.client_visit_id,
    )
    await db.execute(stmt)
    await db.commit()
    visit = await db.scalar(
        select(UserInboxVisit).where(UserInboxVisit.user_id == current_user.id)
    )
    return {
        "last_visited_at": visit.last_visited_at.isoformat(),
        "previous_visited_at": (
            visit.previous_visited_at.isoformat() if visit.previous_visited_at else None
        ),
    }


def inbox_bucket(today: date):
    """Use identical classification for summary counts and paginated rows."""
    return case(
        (Application.id.is_not(None), "saved"),
        (JobReviewState.state == "dismissed", "dismissed"),
        (
            JobReviewState.state == "snoozed",
            case((JobReviewState.snoozed_until <= today, "due"), else_="snoozed"),
        ),
        (JobReviewState.state == "reviewed", "reviewed"),
        else_="new",
    )


def matching_jobs_query(user_id: str, min_score: int):
    return (
        select(JobResult, JobRaw, JobReviewState, Application)
        .join(JobRaw, JobRaw.id == JobResult.job_id)
        .outerjoin(
            JobReviewState,
            and_(JobReviewState.job_id == JobResult.job_id, JobReviewState.user_id == user_id),
        )
        .outerjoin(
            Application,
            and_(Application.job_id == JobResult.job_id, Application.user_id == user_id),
        )
        .outerjoin(UserInboxVisit, UserInboxVisit.user_id == user_id)
        .where(
            JobResult.user_id == user_id,
            JobResult.final_score >= min_score,
            JobResult.archived_by_llm.is_not(True),
        )
    )


async def _counts(db: AsyncSession, user_id: str, today: date, min_score: int):
    bucket = inbox_bucket(today)
    statement = matching_jobs_query(user_id, min_score).with_only_columns(
        bucket.label("bucket"), func.count()
    ).group_by(bucket)
    rows = (await db.execute(statement)).all()
    counts = {key: 0 for key in ("new", "reviewed", "due", "snoozed", "dismissed", "saved")}
    for name, count in rows:
        if name in counts:
            counts[name] = count
    counts["since_visit"] = await db.scalar(
        matching_jobs_query(user_id, min_score).with_only_columns(func.count())
        .where(since_visit_filter(today))
    ) or 0
    return counts


@router.get("/summary")
async def inbox_summary(
    today: date = Query(default_factory=date.today),
    min_score: int = Query(65, ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    counts = await _counts(db, current_user.id, today, min_score)
    due = await db.scalar(
        select(func.count()).select_from(Application).where(
            Application.user_id == current_user.id,
            Application.next_action_due_date.is_not(None),
            Application.next_action_due_date <= today,
            Application.status.notin_(CLOSED_APPLICATION_STATUSES),
        )
    )
    now = datetime.now(timezone.utc)
    interviews = await db.scalar(
        select(func.count()).select_from(Application).where(
            Application.user_id == current_user.id,
            Application.status.in_(("interview", "phone_screen")),
            Application.interview_date >= now,
            Application.interview_date < now + timedelta(days=7),
        )
    )
    return {
        **counts,
        "followups_due": due or 0,
        "upcoming_interviews": interviews or 0,
        "review_complete": counts["new"] == 0 and counts["due"] == 0,
        "min_score": min_score,
    }


@router.get("")
async def list_inbox(
    bucket: InboxBucket = Query("new"),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    min_score: int = Query(65, ge=0, le=100),
    today: date = Query(default_factory=date.today),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bucket_clause = since_visit_filter(today) if bucket == "since_visit" else inbox_bucket(today) == bucket
    base = matching_jobs_query(current_user.id, min_score).where(bucket_clause)
    total = await db.scalar(base.with_only_columns(func.count()).order_by(None))
    rows = (
        await db.execute(
            base.order_by(JobResult.final_score.desc(), JobRaw.ingested_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).all()
    return {
        "jobs": [
            {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "job_url": job.job_url,
                "site": job.site,
                "score": round(float(result.final_score or 0) / 100, 4),
                "review_state": review.state if review else "unreviewed",
                "snoozed_until": (
                    review.snoozed_until.isoformat() if review and review.snoozed_until else None
                ),
                "is_saved": application is not None,
            }
            for result, job, review, application in rows
        ],
        "total": total or 0,
        "bucket": bucket,
        "page": page,
        "limit": limit,
    }


async def _require_matching_job(db: AsyncSession, user_id: str, job_id: str):
    owned = await db.scalar(
        select(JobResult.id).where(
            JobResult.user_id == user_id, JobResult.job_id == job_id
        ).limit(1)
    )
    if owned is None:
        raise HTTPException(status_code=404, detail="Matching job not found")


@router.put("/{job_id}")
async def update_review(
    job_id: str,
    body: ReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_matching_job(db, current_user.id, job_id)
    row = await db.scalar(
        select(JobReviewState).where(
            JobReviewState.user_id == current_user.id,
            JobReviewState.job_id == job_id,
        )
    )
    if body.state == "unreviewed":
        if row is not None:
            await db.delete(row)
    elif row is not None:
        row.state = body.state
        row.snoozed_until = body.snoozed_until
    else:
        db.add(JobReviewState(
            user_id=current_user.id,
            job_id=job_id,
            state=body.state,
            snoozed_until=body.snoozed_until,
        ))
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Review updated concurrently; retry"
        ) from exc
    invalidate_stats_cache()
    return {"job_id": job_id, "state": body.state, "snoozed_until": body.snoozed_until}


@router.post("/mark-page-reviewed")
async def mark_page_reviewed(
    body: BatchReview,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    unique_ids = list(dict.fromkeys(body.job_ids))
    owned = (
        await db.execute(select(JobResult.job_id).where(
            JobResult.user_id == current_user.id,
            JobResult.job_id.in_(unique_ids),
        ))
    ).scalars().all()
    if set(owned) != set(unique_ids):
        raise HTTPException(status_code=404, detail="At least one matching job was not found")
    already_reviewed = (
        await db.execute(select(JobReviewState.job_id).where(
            JobReviewState.user_id == current_user.id,
            JobReviewState.job_id.in_(unique_ids),
        ))
    ).scalars().all()
    unseen = set(unique_ids) - set(already_reviewed)
    for job_id in unseen:
        db.add(JobReviewState(user_id=current_user.id, job_id=job_id, state="reviewed"))
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Review batch changed concurrently; retry") from exc
    invalidate_stats_cache()
    return {"reviewed": len(unseen)}

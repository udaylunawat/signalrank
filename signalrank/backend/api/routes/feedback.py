from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.deps import get_current_user
from api.models import JobFeedback, JobRaw, User

router = APIRouter(prefix="/api/jobs", tags=["feedback"])

FeedbackValue = Literal["relevant", "not_relevant"]
FeedbackReason = Literal[
    "wrong_role",
    "wrong_seniority",
    "wrong_location",
    "other",
]


class FeedbackUpsert(BaseModel):
    value: FeedbackValue
    reason: FeedbackReason | None = None


@router.put("/{job_id}/feedback")
async def upsert_feedback(
    job_id: str,
    body: FeedbackUpsert,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(JobRaw, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    existing_result = await db.execute(
        select(JobFeedback).where(
            JobFeedback.user_id == current_user.id,
            JobFeedback.job_id == job_id,
        )
    )
    feedback = existing_result.scalar_one_or_none()
    if feedback:
        feedback.value = body.value
        feedback.reason = body.reason
    else:
        feedback = JobFeedback(
            user_id=current_user.id,
            job_id=job_id,
            value=body.value,
            reason=body.reason,
        )
        db.add(feedback)
    await db.commit()
    return {
        "job_id": job_id,
        "value": feedback.value,
        "reason": feedback.reason,
    }


@router.delete("/{job_id}/feedback", status_code=204)
async def delete_feedback(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JobFeedback).where(
            JobFeedback.user_id == current_user.id,
            JobFeedback.job_id == job_id,
        )
    )
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    await db.delete(feedback)
    await db.commit()

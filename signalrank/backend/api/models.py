import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from api.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=gen_uuid
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(50), default="credentials")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped["Profile"] = relationship(back_populates="user", uselist=False)
    runs: Mapped[list["Run"]] = relationship(back_populates="user")
    applications: Mapped[list["Application"]] = relationship(back_populates="user")


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=gen_uuid
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), unique=True, nullable=False
    )
    resume_text: Mapped[str | None] = mapped_column(Text)
    resume_embedding: Mapped[list[float] | None] = mapped_column(Vector(384))
    distilled_text: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[dict | None] = mapped_column(JSONB)
    target_roles: Mapped[dict | None] = mapped_column(JSONB)
    target_companies: Mapped[dict | None] = mapped_column(JSONB)
    preferred_locations: Mapped[dict | None] = mapped_column(JSONB)
    min_salary: Mapped[int | None] = mapped_column(Integer)
    min_yoe: Mapped[int | None] = mapped_column(Integer)
    max_yoe: Mapped[int | None] = mapped_column(Integer)
    role_intent: Mapped[str | None] = mapped_column(String(100))
    config_overrides: Mapped[dict | None] = mapped_column(JSONB)
    onboarding_draft: Mapped[dict | None] = mapped_column(JSONB)
    resume_sha256: Mapped[str | None] = mapped_column(String(64))
    resume_parse_status: Mapped[str | None] = mapped_column(String(50))
    resume_parse_error: Mapped[str | None] = mapped_column(Text)
    resume_parse_confidence: Mapped[float | None] = mapped_column(Float)
    resume_parser_model: Mapped[str | None] = mapped_column(String(255))
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="profile")


class JobRaw(Base):
    __tablename__ = "jobs_raw"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=gen_uuid
    )
    job_url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    company: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    site: Mapped[str | None] = mapped_column(String(100))
    date_posted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_verified: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    results: Mapped[list["JobResult"]] = relationship(back_populates="job")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=gen_uuid
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    stage: Mapped[str] = mapped_column(String(50), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    job_count: Mapped[int | None] = mapped_column(Integer)
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    user: Mapped["User"] = relationship(back_populates="runs")
    results: Mapped[list["JobResult"]] = relationship(back_populates="run")
    source_telemetry: Mapped[list["RunSourceTelemetry"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "uq_runs_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
    )


class RunSourceTelemetry(Base):
    __tablename__ = "run_source_telemetry"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=gen_uuid
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    query: Mapped[str | None] = mapped_column(String(500))
    location: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    jobs_found: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    jobs_persisted: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    run: Mapped["Run"] = relationship(back_populates="source_telemetry")

    __table_args__ = (Index("ix_run_source_telemetry_run_id", "run_id"),)


class JobResult(Base):
    __tablename__ = "job_results"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=gen_uuid
    )
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs_raw.id"), nullable=False)
    semantic_score: Mapped[float | None] = mapped_column(Float)
    skills_score: Mapped[float | None] = mapped_column(Float)
    company_score: Mapped[float | None] = mapped_column(Float)
    seniority_score: Mapped[float | None] = mapped_column(Float)
    location_score: Mapped[float | None] = mapped_column(Float)
    recency_score: Mapped[float | None] = mapped_column(Float)
    final_score: Mapped[float | None] = mapped_column(Float)
    company_tier: Mapped[str | None] = mapped_column(String(50))
    company_reputation_confidence: Mapped[float | None] = mapped_column(Float)
    company_reputation_rationale: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[dict | None] = mapped_column(JSONB)
    is_contract: Mapped[bool | None] = mapped_column(Boolean)

    run: Mapped["Run"] = relationship(back_populates="results")
    job: Mapped["JobRaw"] = relationship(back_populates="results")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=gen_uuid
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs_raw.id"))
    company: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(100), default="interested")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    recruiter_id: Mapped[str | None] = mapped_column(ForeignKey("recruiters.id"))

    user: Mapped["User"] = relationship(back_populates="applications")

    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_application_user_job"),
    )


class Recruiter(Base):
    __tablename__ = "recruiters"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=gen_uuid
    )
    company: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(255))
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(String(255))
    domain: Mapped[str | None] = mapped_column(String(255))
    found_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "company", "linkedin_url", name="uq_recruiter_company_linkedin"
        ),
    )


class TailoredResume(Base):
    __tablename__ = "tailored_resumes"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=gen_uuid
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs_raw.id"))
    content_json: Mapped[dict | None] = mapped_column(JSONB)
    pdf_path: Mapped[str | None] = mapped_column(String(500))
    template: Mapped[str] = mapped_column(String(50), default="classic")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_tailored_resume_user_job"),
    )


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=gen_uuid
    )
    text_fp: Mapped[str] = mapped_column(String(64), nullable=False)
    cfg_fp: Mapped[str] = mapped_column(String(32), nullable=False)
    vector: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("text_fp", "cfg_fp", name="uq_embedding_text_cfg"),
    )


class LLMCache(Base):
    __tablename__ = "llm_cache"

    prompt_hash: Mapped[str] = mapped_column(String(32), primary_key=True)
    response_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CompanyReputation(Base):
    __tablename__ = "company_reputations"

    canonical_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    reputation_score: Mapped[float | None] = mapped_column(Float)
    reputation_tier: Mapped[str] = mapped_column(
        String(50), nullable=False, default="unknown", server_default="unknown"
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    rationale: Mapped[str | None] = mapped_column(Text)
    assessment_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", server_default="pending"
    )
    model_id: Mapped[str | None] = mapped_column(String(255))
    prompt_hash: Mapped[str | None] = mapped_column(String(64))
    rubric_version: Mapped[str] = mapped_column(
        String(50), nullable=False, default="v1", server_default="v1"
    )
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manual_override: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    __table_args__ = (
        Index("ix_company_reputations_tier", "reputation_tier"),
        Index("ix_company_reputations_status", "assessment_status"),
    )

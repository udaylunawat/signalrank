"""add cached, candidate-independent job enrichment

Revision ID: da3e9f1b7c24
Revises: c62a7a7f4bc1
Create Date: 2026-07-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "da3e9f1b7c24"
down_revision = "c62a7a7f4bc1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_enrichments",
        sa.Column("job_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("role_summary", sa.Text(), nullable=True),
        sa.Column("role_aliases", postgresql.JSONB(), nullable=True),
        sa.Column(
            "seniority_band",
            sa.String(length=32),
            server_default="unknown",
            nullable=False,
        ),
        sa.Column("required_skills", postgresql.JSONB(), nullable=True),
        sa.Column("preferred_skills", postgresql.JSONB(), nullable=True),
        sa.Column("workplace", postgresql.JSONB(), nullable=True),
        sa.Column(
            "coherence_status",
            sa.String(length=32),
            server_default="unassessed",
            nullable=False,
        ),
        sa.Column(
            "coherence_confidence", sa.Float(), server_default="0", nullable=False
        ),
        sa.Column("coherence_reason", sa.String(length=64), nullable=True),
        sa.Column(
            "assessment_status",
            sa.String(length=32),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("model_id", sa.String(length=255), nullable=True),
        sa.Column("prompt_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "rubric_version", sa.String(length=50), server_default="v1", nullable=False
        ),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs_raw.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index(
        "ix_job_enrichments_status", "job_enrichments", ["assessment_status"]
    )
    op.create_index("ix_job_enrichments_expires_at", "job_enrichments", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_job_enrichments_expires_at", table_name="job_enrichments")
    op.drop_index("ix_job_enrichments_status", table_name="job_enrichments")
    op.drop_table("job_enrichments")

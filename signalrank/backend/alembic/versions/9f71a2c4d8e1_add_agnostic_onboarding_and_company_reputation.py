"""add agnostic onboarding state and company reputation

Revision ID: 9f71a2c4d8e1
Revises: 8d4f2c1a7b90
Create Date: 2026-07-15 14:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9f71a2c4d8e1"
down_revision: Union[str, Sequence[str], None] = "8d4f2c1a7b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("onboarding_draft", postgresql.JSONB(), nullable=True))
    op.add_column("profiles", sa.Column("resume_sha256", sa.String(length=64), nullable=True))
    op.add_column("profiles", sa.Column("resume_parse_status", sa.String(length=50), nullable=True))
    op.add_column("profiles", sa.Column("resume_parse_error", sa.Text(), nullable=True))
    op.add_column("profiles", sa.Column("resume_parse_confidence", sa.Float(), nullable=True))
    op.add_column("profiles", sa.Column("resume_parser_model", sa.String(length=255), nullable=True))

    op.add_column("job_results", sa.Column("company_reputation_confidence", sa.Float(), nullable=True))
    op.add_column("job_results", sa.Column("company_reputation_rationale", sa.Text(), nullable=True))
    op.add_column("job_results", sa.Column("explanation", postgresql.JSONB(), nullable=True))

    op.create_table(
        "company_reputations",
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("reputation_score", sa.Float(), nullable=True),
        sa.Column("reputation_tier", sa.String(length=50), server_default="unknown", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("assessment_status", sa.String(length=50), server_default="pending", nullable=False),
        sa.Column("model_id", sa.String(length=255), nullable=True),
        sa.Column("prompt_hash", sa.String(length=64), nullable=True),
        sa.Column("rubric_version", sa.String(length=50), server_default="v1", nullable=False),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("manual_override", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.PrimaryKeyConstraint("canonical_name"),
    )
    op.create_index("ix_company_reputations_tier", "company_reputations", ["reputation_tier"])
    op.create_index("ix_company_reputations_status", "company_reputations", ["assessment_status"])


def downgrade() -> None:
    op.drop_index("ix_company_reputations_status", table_name="company_reputations")
    op.drop_index("ix_company_reputations_tier", table_name="company_reputations")
    op.drop_table("company_reputations")
    op.drop_column("job_results", "explanation")
    op.drop_column("job_results", "company_reputation_rationale")
    op.drop_column("job_results", "company_reputation_confidence")
    op.drop_column("profiles", "resume_parser_model")
    op.drop_column("profiles", "resume_parse_confidence")
    op.drop_column("profiles", "resume_parse_error")
    op.drop_column("profiles", "resume_parse_status")
    op.drop_column("profiles", "resume_sha256")
    op.drop_column("profiles", "onboarding_draft")

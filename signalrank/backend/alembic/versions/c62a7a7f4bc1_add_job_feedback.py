"""add per-user job feedback

Revision ID: c62a7a7f4bc1
Revises: 9f71a2c4d8e1
Create Date: 2026-07-15 18:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c62a7a7f4bc1"
down_revision: Union[str, Sequence[str], None] = "9f71a2c4d8e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_feedback",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("job_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("value", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs_raw.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "job_id", name="uq_job_feedback_user_job"),
    )
    op.create_index(
        "ix_job_feedback_user_value",
        "job_feedback",
        ["user_id", "value"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_job_feedback_user_value", table_name="job_feedback")
    op.drop_table("job_feedback")

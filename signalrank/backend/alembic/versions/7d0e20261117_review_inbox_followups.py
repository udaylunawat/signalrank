"""Durable review inbox and tracker next actions.

Revision ID: 7d0e20261117
Revises: 6c7d8e9f0a1b
"""

from alembic import op
import sqlalchemy as sa

revision = "7d0e20261117"
down_revision = "6c7d8e9f0a1b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_review_states",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.UUID(as_uuid=False), sa.ForeignKey("jobs_raw.id", ondelete="CASCADE"), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("snoozed_until", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "job_id", name="uq_job_review_user_job"),
    )
    op.create_index(
        "ix_job_review_user_state",
        "job_review_states",
        ["user_id", "state", "snoozed_until"],
    )
    op.add_column("applications", sa.Column("next_action", sa.String(255), nullable=True))
    op.add_column("applications", sa.Column("next_action_due_date", sa.Date(), nullable=True))
    op.create_index(
        "ix_applications_user_next_due",
        "applications",
        ["user_id", "next_action_due_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_applications_user_next_due", table_name="applications")
    op.drop_column("applications", "next_action_due_date")
    op.drop_column("applications", "next_action")
    op.drop_index("ix_job_review_user_state", table_name="job_review_states")
    op.drop_table("job_review_states")

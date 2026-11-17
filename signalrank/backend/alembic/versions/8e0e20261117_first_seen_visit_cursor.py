"""Record per-user first match and last inbox visit.

Revision ID: 8e0e20261117
Revises: 7d0e20261117
"""

from alembic import op
import sqlalchemy as sa


revision = "8e0e20261117"
down_revision = "7d0e20261117"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_results",
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Preserve legacy historical ordering as closely as possible. Existing rows
    # have only their latest run_id, so the original first match is not
    # recoverable retroactively; after this migration it is stable.
    op.execute(
        """
        UPDATE job_results jr
        SET first_seen_at = COALESCE(r.started_at, j.ingested_at, now())
        FROM runs r, jobs_raw j
        WHERE jr.run_id = r.id AND jr.job_id = j.id
        """
    )
    op.execute(
        "UPDATE job_results SET first_seen_at = now() WHERE first_seen_at IS NULL"
    )
    op.alter_column("job_results", "first_seen_at", nullable=False)
    op.alter_column(
        "job_results",
        "first_seen_at",
        server_default=sa.text("now()"),
    )
    op.create_index(
        "ix_job_results_user_first_seen",
        "job_results",
        ["user_id", "first_seen_at"],
    )
    op.create_table(
        "user_inbox_visits",
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("previous_visited_at", sa.DateTime(timezone=True)),
        sa.Column("last_visited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_visit_id", sa.String(80), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_inbox_visits")
    op.drop_index("ix_job_results_user_first_seen", table_name="job_results")
    op.drop_column("job_results", "first_seen_at")

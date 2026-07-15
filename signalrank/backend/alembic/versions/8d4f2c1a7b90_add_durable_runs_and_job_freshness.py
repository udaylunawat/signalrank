"""add durable runs, source telemetry, and job freshness

Revision ID: 8d4f2c1a7b90
Revises: 4e689d8074f1
Create Date: 2026-07-15 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8d4f2c1a7b90"
down_revision: Union[str, Sequence[str], None] = "4e689d8074f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs_raw",
        sa.Column(
            "first_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "jobs_raw",
        sa.Column(
            "last_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "jobs_raw",
        sa.Column(
            "last_verified",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "jobs_raw",
        sa.Column(
            "active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
    )

    op.add_column(
        "runs",
        sa.Column(
            "stage", sa.String(length=50), server_default="queued", nullable=False
        ),
    )
    op.add_column(
        "runs",
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("runs", sa.Column("error_summary", sa.Text(), nullable=True))
    op.add_column(
        "runs", sa.Column("lease_owner", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "runs", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "runs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "runs",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )

    op.execute(
        """
        WITH active_runs AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY user_id ORDER BY started_at DESC, id DESC
                   ) AS position
            FROM runs
            WHERE status IN ('pending', 'running')
        )
        UPDATE runs
        SET status = 'failed',
            stage = 'failed',
            progress = 100,
            finished_at = now(),
            error_summary = 'Superseded while enabling durable run execution'
        WHERE id IN (SELECT id FROM active_runs WHERE position > 1)
        """
    )
    op.create_index(
        "uq_runs_one_active_per_user",
        "runs",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )

    op.create_table(
        "run_source_telemetry",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("run_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("query", sa.String(length=500), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("jobs_found", sa.Integer(), server_default="0", nullable=False),
        sa.Column("jobs_persisted", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_run_source_telemetry_run_id",
        "run_source_telemetry",
        ["run_id"],
        unique=False,
    )

    op.execute(
        """
        DELETE FROM applications older
        USING applications newer
        WHERE older.user_id = newer.user_id
          AND older.job_id = newer.job_id
          AND older.job_id IS NOT NULL
          AND older.id < newer.id
        """
    )
    op.create_unique_constraint(
        "uq_application_user_job", "applications", ["user_id", "job_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_application_user_job", "applications", type_="unique")
    op.drop_index("ix_run_source_telemetry_run_id", table_name="run_source_telemetry")
    op.drop_table("run_source_telemetry")
    op.drop_index("uq_runs_one_active_per_user", table_name="runs")
    op.drop_column("runs", "attempt_count")
    op.drop_column("runs", "heartbeat_at")
    op.drop_column("runs", "lease_expires_at")
    op.drop_column("runs", "lease_owner")
    op.drop_column("runs", "error_summary")
    op.drop_column("runs", "progress")
    op.drop_column("runs", "stage")
    op.drop_column("jobs_raw", "active")
    op.drop_column("jobs_raw", "last_verified")
    op.drop_column("jobs_raw", "last_seen")
    op.drop_column("jobs_raw", "first_seen")

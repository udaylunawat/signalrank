"""add indexes for ranking and result queries

Revision ID: f1a2b3c4d5e6
Revises: da3e9f1b7c24
Create Date: 2026-08-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "da3e9f1b7c24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_jobs_raw_active_last_seen",
        "jobs_raw",
        ["active", "last_seen"],
    )
    op.create_index(
        "ix_runs_user_status_finished_at",
        "runs",
        ["user_id", "status", "finished_at"],
    )
    op.create_index(
        "ix_job_results_run_user_score",
        "job_results",
        ["run_id", "user_id", "final_score"],
    )
    op.create_index(
        "ix_job_results_run_user_job",
        "job_results",
        ["run_id", "user_id", "job_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_results_run_user_job", table_name="job_results")
    op.drop_index("ix_job_results_run_user_score", table_name="job_results")
    op.drop_index("ix_runs_user_status_finished_at", table_name="runs")
    op.drop_index("ix_jobs_raw_active_last_seen", table_name="jobs_raw")

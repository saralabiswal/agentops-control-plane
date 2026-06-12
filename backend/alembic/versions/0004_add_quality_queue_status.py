"""Add quality queue status fields."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_add_quality_queue_status"
down_revision: str | None = "0003_add_task_queue_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("quality_status", sa.String(length=20), nullable=True))
    op.add_column("agent_runs", sa.Column("quality_error", sa.Text(), nullable=True))
    op.add_column(
        "agent_runs",
        sa.Column("quality_attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("agent_runs", "quality_attempt_count")
    op.drop_column("agent_runs", "quality_error")
    op.drop_column("agent_runs", "quality_status")

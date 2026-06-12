"""Add task queue metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_task_queue_metadata"
down_revision: str | None = "0002_add_operational_pricing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("model_pricing_id", sa.String(), nullable=True))
    op.add_column("tasks", sa.Column("retry_of_run_id", sa.String(), nullable=True))
    op.add_column(
        "tasks",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("tasks", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("last_error", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_model_pricing_id_model_pricing",
        "tasks",
        "model_pricing",
        ["model_pricing_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_tasks_model_pricing_id_model_pricing", "tasks", type_="foreignkey")
    op.drop_column("tasks", "last_error")
    op.drop_column("tasks", "claimed_at")
    op.drop_column("tasks", "attempt_count")
    op.drop_column("tasks", "retry_of_run_id")
    op.drop_column("tasks", "model_pricing_id")

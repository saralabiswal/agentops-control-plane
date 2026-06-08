"""Add operational pricing components."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_operational_pricing"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "model_pricing",
        sa.Column(
            "api_call_cost_per_1k",
            sa.Float(),
            nullable=False,
            server_default="0.0",
        ),
    )
    op.add_column(
        "model_pricing",
        sa.Column(
            "compute_vcpu_cost_per_second",
            sa.Float(),
            nullable=False,
            server_default="0.0",
        ),
    )
    op.add_column(
        "model_pricing",
        sa.Column(
            "compute_memory_gib_cost_per_second",
            sa.Float(),
            nullable=False,
            server_default="0.0",
        ),
    )


def downgrade() -> None:
    op.drop_column("model_pricing", "compute_memory_gib_cost_per_second")
    op.drop_column("model_pricing", "compute_vcpu_cost_per_second")
    op.drop_column("model_pricing", "api_call_cost_per_1k")

"""Add provider/model pricing lookup index."""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_add_model_pricing_provider_model_index"
down_revision: str | None = "0004_add_quality_queue_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_model_pricing_provider_model_effective",
        "model_pricing",
        ["provider", "model_name", "effective_to"],
    )


def downgrade() -> None:
    op.drop_index("ix_model_pricing_provider_model_effective", table_name="model_pricing")

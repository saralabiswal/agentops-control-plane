from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models.agent_run import AgentRun


class ModelPricing(Base):
    __tablename__ = "model_pricing"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    input_cost_per_1k: Mapped[float] = mapped_column(Float, nullable=False)
    output_cost_per_1k: Mapped[float] = mapped_column(Float, nullable=False)
    api_call_cost_per_1k: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    compute_vcpu_cost_per_second: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    compute_memory_gib_cost_per_second: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    runs: Mapped[list["AgentRun"]] = relationship(back_populates="model_pricing")

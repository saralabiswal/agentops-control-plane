from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import RunStatus
from app.models import Base

if TYPE_CHECKING:
    from app.models.agent_definition import AgentDefinition
    from app.models.business_outcome import BusinessOutcome
    from app.models.metric import Metric
    from app.models.model_pricing import ModelPricing
    from app.models.task import Task


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_task_ran_at", "task_id", "ran_at"),
        Index("ix_agent_runs_quality_score", "quality_score"),
        Index("ix_agent_runs_ran_at", "ran_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(
        ForeignKey("agent_definitions.id"), nullable=False, index=True
    )
    model_pricing_id: Mapped[str] = mapped_column(ForeignKey("model_pricing.id"), nullable=False)
    run_type: Mapped[str] = mapped_column(String(40), nullable=False)
    parent_run_id: Mapped[str | None] = mapped_column(ForeignKey("agent_runs.id"))
    retry_of: Mapped[str | None] = mapped_column(ForeignKey("agent_runs.id"))

    model_used: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=RunStatus.RUNNING, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    raw_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    raw_response: Mapped[str] = mapped_column(Text, default="", nullable=False)
    output_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    quality_score: Mapped[float | None] = mapped_column(Float)
    quality_relevance: Mapped[float | None] = mapped_column(Float)
    quality_faithfulness: Mapped[float | None] = mapped_column(Float)
    quality_completeness: Mapped[float | None] = mapped_column(Float)
    quality_actionability: Mapped[float | None] = mapped_column(Float)
    quality_dimensions: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    ran_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    task: Mapped["Task"] = relationship(back_populates="agent_run")
    agent: Mapped["AgentDefinition"] = relationship(back_populates="runs")
    model_pricing: Mapped["ModelPricing"] = relationship(back_populates="runs")
    metrics: Mapped[list["Metric"]] = relationship(back_populates="agent_run")
    business_outcome: Mapped["BusinessOutcome | None"] = relationship(back_populates="agent_run")
    child_runs: Mapped[list["AgentRun"]] = relationship(
        foreign_keys=[parent_run_id], remote_side=[id], viewonly=True
    )
    retry_runs: Mapped[list["AgentRun"]] = relationship(
        foreign_keys=[retry_of], remote_side=[id], viewonly=True
    )

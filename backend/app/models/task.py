from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import TaskPriority, TaskStatus
from app.models import Base

if TYPE_CHECKING:
    from app.models.agent_definition import AgentDefinition
    from app.models.agent_run import AgentRun
    from app.models.session import Session


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(
        ForeignKey("agent_definitions.id"), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(120), nullable=False)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default=TaskPriority.NORMAL, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.QUEUED, nullable=False)
    model_pricing_id: Mapped[str | None] = mapped_column(ForeignKey("model_pricing.id"))
    retry_of_run_id: Mapped[str | None] = mapped_column(String)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    session: Mapped["Session"] = relationship(back_populates="tasks")
    agent: Mapped["AgentDefinition"] = relationship(back_populates="tasks")
    agent_run: Mapped["AgentRun | None"] = relationship(back_populates="task")

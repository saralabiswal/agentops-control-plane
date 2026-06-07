from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models.agent_run import AgentRun
    from app.models.task import Task


class AgentDefinition(Base):
    __tablename__ = "agent_definitions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    domain: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    agent_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    model_default: Mapped[str] = mapped_column(String(120), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(60), nullable=False)
    quality_rubric: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    tasks: Mapped[list["Task"]] = relationship(back_populates="agent")
    runs: Mapped[list["AgentRun"]] = relationship(back_populates="agent")


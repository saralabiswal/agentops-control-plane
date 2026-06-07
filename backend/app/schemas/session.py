from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SessionCreateRequest(BaseModel):
    name: str = "Demo Session"


class SessionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    total_cost_usd: float
    total_tasks: int
    success_rate: float
    avg_quality_score: float


class SessionDetailSchema(SessionSchema):
    tasks: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []

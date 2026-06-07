from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class MetricSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_run_id: str
    ts: datetime
    metric_name: str
    metric_value: float
    dimensions: dict[str, Any]

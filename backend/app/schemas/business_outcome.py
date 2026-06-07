from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BusinessOutcomeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    agent_run_id: str
    domain: str
    outcome_type: str
    metric_name: str
    metric_value: float
    metric_unit: str
    financial_impact_usd: float
    confidence_score: float
    computed_at: datetime


class SessionOutcomesSchema(BaseModel):
    session_id: str
    total_financial_impact_usd: float
    outcomes: list[BusinessOutcomeSchema]


class OutcomeSummarySchema(BaseModel):
    total_financial_impact_usd: float
    total_cost_usd: float
    roi_multiple: float


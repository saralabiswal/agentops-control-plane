from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AgentDefinitionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    domain: str
    agent_type: str
    description: str
    model_default: str
    execution_mode: str
    quality_rubric: str
    created_at: datetime


class ModelPricingSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    model_name: str
    input_cost_per_1k: float
    output_cost_per_1k: float
    api_call_cost_per_1k: float
    compute_vcpu_cost_per_second: float
    compute_memory_gib_cost_per_second: float
    effective_from: datetime
    effective_to: datetime | None


class AgentRunSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    agent_id: str
    model_pricing_id: str
    run_type: str
    parent_run_id: str | None
    retry_of: str | None
    model_used: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    cost_usd: float
    status: str
    error_message: str | None
    raw_prompt: str
    raw_response: str
    output_payload: dict[str, Any]
    quality_score: float | None
    quality_relevance: float | None
    quality_faithfulness: float | None
    quality_completeness: float | None
    quality_actionability: float | None
    quality_dimensions: dict[str, Any] | None
    ran_at: datetime
    completed_at: datetime | None


class AgentRunDetailSchema(AgentRunSchema):
    child_runs: list[dict[str, Any]] = []


class QualityDetailSchema(BaseModel):
    run_id: str
    quality_score: float | None
    quality_relevance: float | None
    quality_faithfulness: float | None
    quality_completeness: float | None
    quality_actionability: float | None
    quality_dimensions: dict[str, Any] | None

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.enums import RunStatus, RunType


@dataclass
class RunContext:
    run_id: str
    task_id: str
    agent_id: str
    session_id: str
    started_at: datetime
    model_used: str
    model_pricing_id: str
    run_type: RunType
    parent_run_id: str | None = None
    retry_of: str | None = None

    raw_prompt: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw_response: str = ""
    output_payload: dict[str, Any] = field(default_factory=dict)

    status: RunStatus = RunStatus.RUNNING
    latency_ms: int = 0
    cost_usd: float = 0.0
    total_tokens: int = 0
    completed_at: datetime | None = None
    error_message: str | None = None

    quality_score: float | None = None
    quality_relevance: float | None = None
    quality_faithfulness: float | None = None
    quality_completeness: float | None = None
    quality_actionability: float | None = None
    quality_dimensions: dict[str, Any] | None = None

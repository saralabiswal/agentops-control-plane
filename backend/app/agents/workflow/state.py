from typing import Any, TypedDict


class TeamMember(TypedDict):
    name: str
    role: str
    skills: list[str]
    load_pct: int


class Epic(TypedDict):
    id: str
    name: str
    description: str
    owner: str
    weeks: str
    stories: list[dict[str, Any]]


class RiskItem(TypedDict):
    title: str
    severity: str
    likelihood: float
    mitigation: str


class ProjectPlanState(TypedDict):
    instruction: str
    team_members: list[TeamMember]
    timeline_weeks: int
    committed_revenue_usd: float
    task_id: str
    session_id: str
    parent_run_id: str
    work_breakdown: list[Epic] | None
    capacity_assessment: dict[str, Any] | None
    risk_register: list[RiskItem] | None
    assigned_plan: list[dict[str, Any]] | None
    final_plan: dict[str, Any] | None
    confidence_score: float | None
    node_traces: list[dict[str, Any]]

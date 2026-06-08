from typing import Any

from app.agents.base import BaseAgent
from app.agents.parsing import JSON_ONLY, parse_json_object


class DeliveryForecastAgent(BaseAgent):
    QUALITY_RUBRIC = """
Relevance: Forecast the specific milestone and revenue figure provided.
Faithfulness: Use the provided historical velocity and blockers.
Completeness: Include confidence, date variance, pipeline at risk, and escalations.
Actionability: Escalations specify who escalates what to whom by when.
"""

    def build_prompt(self, payload: dict[str, Any]) -> str:
        return f"""You are a delivery forecasting agent for enterprise software milestones.

Milestone: {payload['milestone_name']}
Committed revenue tied to delivery: ${payload['committed_revenue_usd']:,}
Target delivery date: {payload['target_date']}
Current date: {payload['current_date']}
Backlog items remaining: {payload['backlog_count']}
Historical sprint velocity: {payload['avg_velocity']} items/sprint
Sprint length: {payload['sprint_length_days']} days
Known blockers: {payload.get('blockers', [])}
Team capacity changes: {payload.get('capacity_changes', 'None')}

Return one JSON object with these fields:
- confidence_score: number from 0 to 1
- forecast_delivery_date: YYYY-MM-DD string
- days_variance: integer days versus target date
- pipeline_at_risk_usd: number
- risk_factors: array of strings
- red_flags: array of strings
- recommended_escalations: array of strings
- assumptions: array of strings, not an object
- summary: string
{JSON_ONLY}"""

    def parse_output(self, raw_response: str) -> dict[str, Any]:
        return parse_json_object(raw_response, ["confidence_score", "risk_factors", "summary"])

from typing import Any

from app.agents.base import BaseAgent
from app.agents.parsing import JSON_ONLY, parse_json_object


class SprintRiskAgent(BaseAgent):
    QUALITY_RUBRIC = """
Relevance: Output must address sprint velocity, task list, team size, and days remaining.
Faithfulness: All risk factors must be traceable to the input payload.
Completeness: Must identify at least 3 risk factors and include delivery confidence.
Actionability: Each mitigation must name who should do what by when.
"""

    def build_prompt(self, payload: dict[str, Any]) -> str:
        return f"""You are a sprint delivery risk assessor for enterprise software teams.

Sprint: {payload['sprint_name']}
Team size: {payload['team_size']} engineers
Days remaining: {payload['days_remaining']}
Total tasks: {payload['total_tasks']}
Completed tasks: {payload['completed_tasks']}
Velocity (last 3 sprints): {payload['velocity_history']} tasks/sprint
Remaining engineering hours: {payload.get('remaining_engineering_hours', 'Unknown')}
Available engineering hours: {payload.get('available_engineering_hours', 'Unknown')}
Remaining story points: {payload.get('remaining_story_points', 'Unknown')}
External dependencies: {payload.get('external_dependencies', [])}
Team capacity notes: {payload.get('capacity_notes', 'None')}

Assess delivery risk and return this shape:
{{
  "risk_score": 0.0,
  "delivery_confidence_score": 0.0,
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "risk_factors": [
    {{"factor": "", "severity": "LOW|MEDIUM|HIGH", "likelihood": 0.0, "mitigation": ""}}
  ],
  "recommended_actions": [""],
  "assumptions": [""],
  "summary": ""
}}
{JSON_ONLY}"""

    def parse_output(self, raw_response: str) -> dict[str, Any]:
        return parse_json_object(
            raw_response,
            ["risk_score", "delivery_confidence_score", "risk_factors", "summary"],
        )

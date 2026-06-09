from typing import Any

from app.agents.base import BaseAgent
from app.agents.parsing import JSON_ONLY, parse_json_object


class ResourceAllocationAgent(BaseAgent):
    QUALITY_RUBRIC = """
Relevance: Assign the specific tasks to the specific team members provided.
Faithfulness: Respect skill profiles and load percentages.
Completeness: Every task must be assigned; overloaded and underutilized members flagged.
Actionability: Each assignment includes reasoning and an efficiency gain estimate.
"""

    def build_prompt(self, payload: dict[str, Any]) -> str:
        return f"""You are a resource allocation optimizer for software engineering teams.

Tasks to assign: {payload['tasks']}
Team members and availability: {payload['team_members']}
Sprint duration: {payload['sprint_weeks']} weeks
Remaining engineering hours: {payload.get('remaining_engineering_hours', 'Unknown')}
Available engineering hours: {payload.get('available_engineering_hours', 'Unknown')}

Assign each task by skill match, capacity, risk, and learning opportunities.
Return JSON with assignments, overloaded_members, underutilized_members,
efficiency_gain_pct, hours_saved_estimate, confidence_score, and summary.
{JSON_ONLY}"""

    def parse_output(self, raw_response: str) -> dict[str, Any]:
        return parse_json_object(
            raw_response,
            ["assignments", "efficiency_gain_pct", "hours_saved_estimate", "summary"],
        )

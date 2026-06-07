from typing import Any

from app.agents.base import BaseAgent
from app.agents.parsing import JSON_ONLY, parse_json_object


class ChurnSignalAgent(BaseAgent):
    QUALITY_RUBRIC = """
Relevance: Reference the behavioral data in the payload.
Faithfulness: Do not invent signals.
Completeness: Identify top signals, days to act, value, and urgency.
Actionability: Recommended play has a concrete owner and timeline.
"""

    def build_prompt(self, payload: dict[str, Any]) -> str:
        return f"""You are an early churn signal detector for enterprise SaaS accounts.

Account: {payload['account_name']}
ARR: ${payload['account_arr']:,}
Contract end date: {payload['contract_end_date']}
Days to renewal: {payload['days_to_renewal']}
Login frequency trend: {payload['login_trend']}
Feature adoption trend: {payload['adoption_trend']}
Support ticket sentiment: {payload.get('ticket_sentiment', 'neutral')}
Executive sponsor engagement: {payload.get('exec_engagement', 'unknown')}
Competitor mentions in tickets: {payload.get('competitor_mentions', 0)}
Contract download events: {payload.get('contract_downloads', 0)}

Return JSON with churn_probability, signal_strength, days_to_act,
early_intervention_value_usd, top_signals, recommended_play, urgency, and summary.
{JSON_ONLY}"""

    def parse_output(self, raw_response: str) -> dict[str, Any]:
        return parse_json_object(raw_response, ["churn_probability", "top_signals", "summary"])

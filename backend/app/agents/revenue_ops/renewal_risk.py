from typing import Any

from app.agents.base import BaseAgent
from app.agents.parsing import JSON_ONLY, parse_json_object


class RenewalRiskAgent(BaseAgent):
    QUALITY_RUBRIC = """
Relevance: Risk score reflects the specific account signals provided.
Faithfulness: Risk factors cite provided data points only.
Completeness: Include risk score, pipeline protection, and recommended actions.
Actionability: Each action specifies owner, urgency, and expected impact.
"""

    def build_prompt(self, payload: dict[str, Any]) -> str:
        return f"""You are a renewal risk assessor for enterprise SaaS accounts.

Account: {payload['account_name']}
ARR: ${payload['account_arr']:,}
Renewal ARR: ${payload.get('renewal_arr_usd', payload['account_arr']):,}
Expansion ARR: ${payload.get('expansion_arr_usd', 0):,}
Contract end date: {payload['contract_end_date']}
Days to renewal: {payload['days_to_renewal']}
Login frequency (last 30 days): {payload['login_frequency_30d']} sessions
Feature adoption score: {payload['feature_adoption_score']} / 10
Support tickets (last 90 days): {payload['support_tickets_90d']}
NPS score: {payload.get('nps_score', 'Unknown')}
Last CSM touchpoint: {payload.get('last_csm_touchpoint', 'Unknown')}
Upsell conversations: {payload.get('upsell_conversations', 0)}
Account owner: {payload.get('account_owner', 'Unknown')}
CSM owner: {payload.get('csm_owner', 'Unknown')}
Executive sponsor: {payload.get('exec_sponsor', 'Unknown')}

Return JSON with risk_score, risk_level, pipeline_protected_usd, risk_factors,
recommended_actions, confidence_score, and summary.
{JSON_ONLY}"""

    def parse_output(self, raw_response: str) -> dict[str, Any]:
        return parse_json_object(raw_response, ["risk_score", "risk_factors", "summary"])

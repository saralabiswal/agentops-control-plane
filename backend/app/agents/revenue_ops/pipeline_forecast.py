from typing import Any

from app.agents.base import BaseAgent
from app.agents.parsing import JSON_ONLY, parse_json_object


class PipelineForecastAgent(BaseAgent):
    QUALITY_RUBRIC = """
Relevance: Forecast applies judgment to the specific deals provided.
Faithfulness: Time analysis uses provided days and cycle length.
Completeness: Include attainment forecast, focus accounts, and excluded accounts.
Actionability: Each focus account has a specific next step.
"""

    def build_prompt(self, payload: dict[str, Any]) -> str:
        return f"""You are a pipeline forecast agent for enterprise sales teams.

Sales rep: {payload['rep_name']}
Quota target: ${payload['quota_target']:,}
Closed to date: ${payload.get('closed_to_date_usd', 0):,}
Commit pipeline: ${payload.get('commit_pipeline_usd', 0):,}
Best-case pipeline: ${payload.get('best_case_pipeline_usd', 0):,}
Quarter close date: {payload['quarter_close_date']}
Days remaining in quarter: {payload['days_remaining']}
Historical close rate: {payload['historical_close_rate']}
Average sales cycle days: {payload['avg_sales_cycle_days']}
Current pipeline: {payload['pipeline_deals']}

Return JSON with attainment_forecast, weighted_pipeline_usd, realistic_pipeline_usd,
quota_gap_usd, recoverable_gap_usd, focus_accounts, excluded_accounts,
confidence_score, and summary.
{JSON_ONLY}"""

    def parse_output(self, raw_response: str) -> dict[str, Any]:
        return parse_json_object(
            raw_response,
            ["attainment_forecast", "recoverable_gap_usd", "focus_accounts", "summary"],
        )

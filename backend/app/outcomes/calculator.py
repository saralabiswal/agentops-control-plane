from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agentops.context import RunContext
from app.models.agent_definition import AgentDefinition
from app.models.business_outcome import BusinessOutcome
from app.models.task import Task


@dataclass(frozen=True)
class OutcomeResult:
    outcome_type: str
    metric_name: str
    metric_value: float
    metric_unit: str
    financial_impact_usd: float
    confidence_score: float


class BusinessOutcomeCalculator:
    async def write_for_run(self, db: AsyncSession, ctx: RunContext) -> BusinessOutcome | None:
        task = await db.get(Task, ctx.task_id)
        agent = await db.get(AgentDefinition, ctx.agent_id)
        if task is None or agent is None:
            return None
        result = self.calculate(agent.name, task.input_payload, ctx.output_payload)
        if result is None:
            return None
        outcome = BusinessOutcome(
            task_id=ctx.task_id,
            agent_run_id=ctx.run_id,
            domain=task.domain,
            outcome_type=result.outcome_type,
            metric_name=result.metric_name,
            metric_value=result.metric_value,
            metric_unit=result.metric_unit,
            financial_impact_usd=result.financial_impact_usd,
            confidence_score=result.confidence_score,
            computed_at=datetime.now(UTC),
        )
        db.add(outcome)
        return outcome

    def calculate(
        self,
        agent_name: str,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any],
    ) -> OutcomeResult | None:
        confidence = float(
            output_payload.get(
                "confidence_score",
                output_payload.get(
                    "delivery_confidence_score",
                    output_payload.get("delivery_confidence", 0.7),
                ),
            )
        )
        if agent_name == "SprintRiskAgent":
            value = float(output_payload.get("risk_score", 0)) * float(
                input_payload.get("delay_cost_per_week_usd", 50000)
            )
            return self._usd("risk_mitigation", "delivery_risk_mitigated_usd", value, confidence)
        if agent_name == "ResourceAllocationAgent":
            tasks = len(input_payload.get("tasks", []))
            value = (
                tasks
                * float(input_payload.get("avg_task_hours", 8))
                * float(output_payload.get("efficiency_gain_pct", 0))
                * float(input_payload.get("hourly_rate", 125))
            )
            return self._usd(
                "engineering_efficiency",
                "engineering_hours_saved_usd",
                value,
                confidence,
            )
        if agent_name == "DeliveryForecastAgent":
            value = float(input_payload.get("committed_revenue_usd", 0)) * (1 - confidence)
            return self._usd("delivery_forecast", "pipeline_confidence_gap_usd", value, confidence)
        if agent_name == "RenewalRiskAgent":
            value = (
                float(input_payload.get("account_arr", 0))
                * float(output_payload.get("risk_score", 0))
                * float(input_payload.get("historical_save_rate", 0.35))
            )
            return self._usd(
                "pipeline_protection",
                "renewal_pipeline_protected_usd",
                value,
                confidence,
            )
        if agent_name == "ChurnSignalAgent":
            value = (
                float(input_payload.get("account_arr", 0))
                * float(output_payload.get("churn_probability", 0))
                * float(input_payload.get("early_intervention_value", 0.4))
            )
            return self._usd("churn_prevention", "churn_early_flag_value_usd", value, confidence)
        if agent_name == "PipelineForecastAgent":
            value = float(output_payload.get("recoverable_gap_usd", 0))
            return self._usd("quota_recovery", "recoverable_quota_gap_usd", value, confidence)
        if agent_name == "ProjectPlanningAgent":
            value = float(input_payload.get("committed_revenue_usd", 0)) * (1 - confidence)
            return self._usd("project_plan", "pipeline_confidence_gap_usd", value, confidence)
        return None

    def _usd(
        self, outcome_type: str, metric_name: str, value: float, confidence: float
    ) -> OutcomeResult:
        return OutcomeResult(outcome_type, metric_name, value, "usd", value, confidence)

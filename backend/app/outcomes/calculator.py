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
        confidence = self._rate(
            output_payload.get(
                "confidence_score",
                output_payload.get(
                    "delivery_confidence_score",
                    output_payload.get("delivery_confidence", 0.7),
                ),
            ),
            default=0.7,
        )
        if agent_name == "SprintRiskAgent":
            value = self._rate(output_payload.get("risk_score", 0)) * self._number(
                input_payload.get("delay_cost_per_week_usd", 50000)
            )
            return self._usd("risk_mitigation", "delivery_risk_mitigated_usd", value, confidence)
        if agent_name == "ResourceAllocationAgent":
            tasks = len(input_payload.get("tasks", []))
            value = (
                tasks
                * self._number(input_payload.get("avg_task_hours", 8))
                * self._rate(output_payload.get("efficiency_gain_pct", 0))
                * self._number(input_payload.get("hourly_rate", 125))
            )
            return self._usd(
                "engineering_efficiency",
                "engineering_hours_saved_usd",
                value,
                confidence,
            )
        if agent_name == "DeliveryForecastAgent":
            value = self._number(input_payload.get("committed_revenue_usd", 0)) * (
                1 - confidence
            )
            return self._usd("delivery_forecast", "pipeline_confidence_gap_usd", value, confidence)
        if agent_name == "RenewalRiskAgent":
            value = (
                self._number(input_payload.get("account_arr", 0))
                * self._rate(output_payload.get("risk_score", 0))
                * self._rate(input_payload.get("historical_save_rate", 0.35))
            )
            return self._usd(
                "pipeline_protection",
                "renewal_pipeline_protected_usd",
                value,
                confidence,
            )
        if agent_name == "ChurnSignalAgent":
            value = (
                self._number(input_payload.get("account_arr", 0))
                * self._rate(output_payload.get("churn_probability", 0))
                * self._rate(input_payload.get("early_intervention_value", 0.4))
            )
            return self._usd("churn_prevention", "churn_early_flag_value_usd", value, confidence)
        if agent_name == "PipelineForecastAgent":
            value = self._number(output_payload.get("recoverable_gap_usd", 0))
            return self._usd("quota_recovery", "recoverable_quota_gap_usd", value, confidence)
        if agent_name == "ProjectPlanningAgent":
            value = self._number(input_payload.get("committed_revenue_usd", 0)) * (
                1 - confidence
            )
            return self._usd("project_plan", "pipeline_confidence_gap_usd", value, confidence)
        return None

    def _number(self, value: Any, default: float = 0.0) -> float:
        """Coerce model-returned numeric fields, including nested JSON objects, into floats."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            normalized = value.replace("$", "").replace(",", "").strip()
            if not normalized:
                return default
            return float(normalized)
        if isinstance(value, dict):
            for key in (
                "recoverable_gap_amount_usd",
                "quota_gap_amount_usd",
                "value",
                "amount",
                "amount_usd",
                "usd",
                "total",
                "estimate",
                "recoverable_gap_usd",
            ):
                if key in value:
                    return self._number(value[key], default)
            for nested in value.values():
                try:
                    return self._number(nested, default)
                except (TypeError, ValueError):
                    continue
        raise TypeError(f"Expected numeric value, got {type(value).__name__}")

    def _rate(self, value: Any, default: float = 0.0) -> float:
        """Normalize model-returned scores to a bounded 0..1 rate."""
        rate = self._number(value, default)
        if rate > 1:
            rate = rate / 100
        return min(max(rate, 0.0), 1.0)

    def _usd(
        self, outcome_type: str, metric_name: str, value: float, confidence: float
    ) -> OutcomeResult:
        return OutcomeResult(outcome_type, metric_name, value, "usd", value, confidence)

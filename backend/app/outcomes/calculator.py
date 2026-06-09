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
        confidence = self._confidence_for(agent_name, input_payload, output_payload)
        if agent_name == "SprintRiskAgent":
            value = self._rate(output_payload.get("risk_score", 0)) * self._number(
                input_payload.get("delay_cost_per_week_usd", 50000)
            )
            return self._usd("risk_mitigation", "delivery_risk_mitigated_usd", value, confidence)
        if agent_name == "ResourceAllocationAgent":
            scoped_hours = self._number(input_payload.get("remaining_engineering_hours", 0))
            if scoped_hours <= 0:
                scoped_hours = len(input_payload.get("tasks", [])) * self._number(
                    input_payload.get("avg_task_hours", 8)
                )
            value = (
                scoped_hours
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

    def _confidence_for(
        self,
        agent_name: str,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any],
    ) -> float:
        """Resolve outcome confidence from model output, then deterministic evidence quality."""
        explicit = self._explicit_confidence(output_payload)
        if explicit is not None:
            return explicit
        if agent_name == "ResourceAllocationAgent":
            return self._resource_allocation_confidence(input_payload, output_payload)
        if agent_name == "RenewalRiskAgent":
            return self._renewal_confidence(input_payload, output_payload)
        if agent_name == "ChurnSignalAgent":
            return self._churn_confidence(input_payload, output_payload)
        if agent_name == "PipelineForecastAgent":
            return self._pipeline_confidence(input_payload, output_payload)
        return 0.7

    def _explicit_confidence(self, output_payload: dict[str, Any]) -> float | None:
        for key in ("confidence_score", "delivery_confidence_score", "delivery_confidence"):
            value = output_payload.get(key)
            if value is None:
                continue
            try:
                return self._rate(value)
            except (TypeError, ValueError):
                continue
        return None

    def _resource_allocation_confidence(
        self,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any],
    ) -> float:
        tasks = input_payload.get("tasks", [])
        assignments = output_payload.get("assignments", [])
        task_count = len(tasks) if isinstance(tasks, list) else 0
        assignment_count = len(assignments) if isinstance(assignments, list) else 0
        coverage = assignment_count / task_count if task_count else 0.5
        remaining_hours = self._safe_number(input_payload.get("remaining_engineering_hours"))
        available_hours = self._safe_number(input_payload.get("available_engineering_hours"))
        if remaining_hours > 0 and available_hours > 0:
            capacity_fit = min(available_hours / remaining_hours, 1.0)
        else:
            capacity_fit = 0.7
        efficiency_present = (
            1.0 if self._safe_number(output_payload.get("efficiency_gain_pct")) > 0 else 0.4
        )
        return round(
            self._weighted_average(
                (coverage, 0.45),
                (capacity_fit, 0.35),
                (efficiency_present, 0.2),
            ),
            3,
        )

    def _renewal_confidence(
        self,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any],
    ) -> float:
        signal_keys = (
            "account_arr",
            "days_to_renewal",
            "login_frequency_30d",
            "feature_adoption_score",
            "support_tickets_90d",
            "nps_score",
            "last_csm_touchpoint",
            "historical_save_rate",
        )
        input_coverage = self._field_coverage(input_payload, signal_keys)
        risk_factors = output_payload.get("risk_factors", [])
        actions = output_payload.get("recommended_actions", [])
        evidence_depth = min(len(risk_factors) / 3, 1.0) if isinstance(risk_factors, list) else 0.0
        action_depth = min(len(actions) / 2, 1.0) if isinstance(actions, list) else 0.0
        return round(
            self._weighted_average(
                (input_coverage, 0.55),
                (evidence_depth, 0.25),
                (action_depth, 0.2),
            ),
            3,
        )

    def _churn_confidence(
        self,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any],
    ) -> float:
        signal_keys = (
            "account_arr",
            "days_to_renewal",
            "login_trend",
            "adoption_trend",
            "ticket_sentiment",
            "exec_engagement",
            "competitor_mentions",
            "contract_downloads",
        )
        input_coverage = self._field_coverage(input_payload, signal_keys)
        top_signals = output_payload.get("top_signals", [])
        signal_depth = min(len(top_signals) / 3, 1.0) if isinstance(top_signals, list) else 0.0
        play_present = 1.0 if output_payload.get("recommended_play") else 0.4
        return round(
            self._weighted_average(
                (input_coverage, 0.5),
                (signal_depth, 0.3),
                (play_present, 0.2),
            ),
            3,
        )

    def _pipeline_confidence(
        self,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any],
    ) -> float:
        pipeline_deals = input_payload.get("pipeline_deals", [])
        deal_count = len(pipeline_deals) if isinstance(pipeline_deals, list) else 0
        deal_depth = min(deal_count / 4, 1.0)
        forecast_fields = self._field_coverage(
            output_payload,
            (
                "attainment_forecast",
                "weighted_pipeline_usd",
                "realistic_pipeline_usd",
                "quota_gap_usd",
                "recoverable_gap_usd",
            ),
        )
        focus_accounts = output_payload.get("focus_accounts", [])
        focus_depth = min(len(focus_accounts) / 2, 1.0) if isinstance(focus_accounts, list) else 0.0
        time_pressure = self._pipeline_time_pressure(input_payload)
        return round(
            self._weighted_average(
                (deal_depth, 0.25),
                (forecast_fields, 0.35),
                (focus_depth, 0.25),
                (time_pressure, 0.15),
            ),
            3,
        )

    def _pipeline_time_pressure(self, input_payload: dict[str, Any]) -> float:
        days_remaining = self._safe_number(input_payload.get("days_remaining"))
        avg_sales_cycle = self._safe_number(input_payload.get("avg_sales_cycle_days"))
        if days_remaining <= 0 or avg_sales_cycle <= 0:
            return 0.6
        return min(max(days_remaining / avg_sales_cycle, 0.25), 1.0)

    def _field_coverage(self, payload: dict[str, Any], keys: tuple[str, ...]) -> float:
        present = 0
        for key in keys:
            value = payload.get(key)
            if value not in (None, "", [], {}):
                present += 1
        return present / len(keys)

    def _safe_number(self, value: Any, default: float = 0.0) -> float:
        try:
            return self._number(value, default)
        except (TypeError, ValueError):
            return default

    def _weighted_average(self, *weighted_values: tuple[float, float]) -> float:
        total_weight = sum(weight for _, weight in weighted_values)
        if total_weight <= 0:
            return 0.0
        value = sum(min(max(score, 0.0), 1.0) * weight for score, weight in weighted_values)
        return min(max(value / total_weight, 0.0), 1.0)

    def _usd(
        self, outcome_type: str, metric_name: str, value: float, confidence: float
    ) -> OutcomeResult:
        return OutcomeResult(outcome_type, metric_name, value, "usd", value, confidence)

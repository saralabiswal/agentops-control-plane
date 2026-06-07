import pytest

from app.outcomes.calculator import BusinessOutcomeCalculator


@pytest.mark.parametrize(
    ("agent", "payload", "output", "metric", "value"),
    [
        (
            "SprintRiskAgent",
            {"delay_cost_per_week_usd": 100000},
            {"risk_score": 0.5, "delivery_confidence_score": 0.7},
            "delivery_risk_mitigated_usd",
            50000,
        ),
        (
            "ResourceAllocationAgent",
            {"tasks": [1, 2], "avg_task_hours": 10, "hourly_rate": 100},
            {"efficiency_gain_pct": 0.2, "confidence_score": 0.8},
            "engineering_hours_saved_usd",
            400,
        ),
        (
            "DeliveryForecastAgent",
            {"committed_revenue_usd": 100000},
            {"confidence_score": 0.75},
            "pipeline_confidence_gap_usd",
            25000,
        ),
        (
            "RenewalRiskAgent",
            {"account_arr": 100000, "historical_save_rate": 0.25},
            {"risk_score": 0.4},
            "renewal_pipeline_protected_usd",
            10000,
        ),
        (
            "ChurnSignalAgent",
            {"account_arr": 100000, "early_intervention_value": 0.5},
            {"churn_probability": 0.4},
            "churn_early_flag_value_usd",
            20000,
        ),
        (
            "PipelineForecastAgent",
            {},
            {"recoverable_gap_usd": 33000},
            "recoverable_quota_gap_usd",
            33000,
        ),
        (
            "ProjectPlanningAgent",
            {"committed_revenue_usd": 100000},
            {"delivery_confidence": 0.6},
            "pipeline_confidence_gap_usd",
            40000,
        ),
    ],
)
def test_business_outcome_formulas(agent, payload, output, metric, value) -> None:
    result = BusinessOutcomeCalculator().calculate(agent, payload, output)

    assert result is not None
    assert result.metric_name == metric
    assert result.financial_impact_usd == pytest.approx(value)


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


def test_pipeline_outcome_accepts_nested_recoverable_gap() -> None:
    result = BusinessOutcomeCalculator().calculate(
        "PipelineForecastAgent",
        {},
        {"recoverable_gap_usd": {"amount_usd": "$33,000", "reason": "late-stage deals"}},
    )

    assert result is not None
    assert result.metric_name == "recoverable_quota_gap_usd"
    assert result.financial_impact_usd == pytest.approx(33000)


def test_pipeline_outcome_prefers_recoverable_gap_amount() -> None:
    result = BusinessOutcomeCalculator().calculate(
        "PipelineForecastAgent",
        {},
        {
            "recoverable_gap_usd": {
                "recovered_pipeline_value_usd": 1500000,
                "recoverable_gap_amount_usd": 68000,
            }
        },
    )

    assert result is not None
    assert result.financial_impact_usd == pytest.approx(68000)


def test_project_planning_normalizes_percent_confidence() -> None:
    result = BusinessOutcomeCalculator().calculate(
        "ProjectPlanningAgent",
        {"committed_revenue_usd": 1250000},
        {"delivery_confidence": 60},
    )

    assert result is not None
    assert result.confidence_score == pytest.approx(0.6)
    assert result.financial_impact_usd == pytest.approx(500000)


def test_risk_scores_are_normalized_when_model_returns_percent() -> None:
    result = BusinessOutcomeCalculator().calculate(
        "SprintRiskAgent",
        {"delay_cost_per_week_usd": 185000},
        {"risk_score": 45, "delivery_confidence_score": 55},
    )

    assert result is not None
    assert result.confidence_score == pytest.approx(0.55)
    assert result.financial_impact_usd == pytest.approx(83250)

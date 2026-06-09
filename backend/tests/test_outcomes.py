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


def test_resource_allocation_uses_remaining_engineering_hours_when_available() -> None:
    result = BusinessOutcomeCalculator().calculate(
        "ResourceAllocationAgent",
        {
            "tasks": [1, 2],
            "avg_task_hours": 10,
            "remaining_engineering_hours": 500,
            "hourly_rate": 150,
        },
        {"efficiency_gain_pct": 0.1, "confidence_score": 0.8},
    )

    assert result is not None
    assert result.metric_name == "engineering_hours_saved_usd"
    assert result.financial_impact_usd == pytest.approx(7500)


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


def test_resource_allocation_derives_confidence_when_model_omits_it() -> None:
    result = BusinessOutcomeCalculator().calculate(
        "ResourceAllocationAgent",
        {
            "tasks": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
            "remaining_engineering_hours": 100,
            "available_engineering_hours": 50,
            "hourly_rate": 100,
        },
        {
            "assignments": [{"task_id": "A"}, {"task_id": "B"}],
            "efficiency_gain_pct": 0.1,
        },
    )

    assert result is not None
    assert result.confidence_score == pytest.approx(0.675)


def test_revenue_agents_derive_confidence_from_evidence_depth() -> None:
    calculator = BusinessOutcomeCalculator()

    renewal = calculator.calculate(
        "RenewalRiskAgent",
        {
            "account_arr": 100000,
            "days_to_renewal": 90,
            "login_frequency_30d": 24,
            "feature_adoption_score": 6.5,
            "support_tickets_90d": 4,
            "nps_score": 32,
            "last_csm_touchpoint": "2026-05-01",
            "historical_save_rate": 0.4,
        },
        {
            "risk_score": 0.3,
            "risk_factors": ["usage decline", "sponsor gap"],
            "recommended_actions": ["CSM follow-up"],
        },
    )
    churn = calculator.calculate(
        "ChurnSignalAgent",
        {
            "account_arr": 100000,
            "days_to_renewal": 80,
            "login_trend": "down",
            "adoption_trend": "flat",
            "ticket_sentiment": "negative",
            "exec_engagement": "missing",
            "competitor_mentions": 2,
            "contract_downloads": 1,
            "early_intervention_value": 0.5,
        },
        {
            "churn_probability": 0.4,
            "top_signals": ["usage", "sponsor"],
            "recommended_play": "Executive save play",
        },
    )

    assert renewal is not None
    assert churn is not None
    assert renewal.confidence_score == pytest.approx(0.817)
    assert churn.confidence_score == pytest.approx(0.9)


def test_pipeline_forecast_derives_confidence_from_deal_and_forecast_depth() -> None:
    result = BusinessOutcomeCalculator().calculate(
        "PipelineForecastAgent",
        {
            "days_remaining": 21,
            "avg_sales_cycle_days": 42,
            "pipeline_deals": [{"account": "A"}, {"account": "B"}, {"account": "C"}],
        },
        {
            "attainment_forecast": 0.7,
            "weighted_pipeline_usd": 500000,
            "realistic_pipeline_usd": 420000,
            "quota_gap_usd": 100000,
            "recoverable_gap_usd": 50000,
            "focus_accounts": [{"account": "A"}],
        },
    )

    assert result is not None
    assert result.confidence_score == pytest.approx(0.737, abs=0.001)

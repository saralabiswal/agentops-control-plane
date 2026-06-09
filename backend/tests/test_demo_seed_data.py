from app.seed.project_delivery import PROJECT_DELIVERY_FIXTURES
from app.seed.revenue_ops import REVENUE_OPS_FIXTURES


def test_project_delivery_seed_data_is_presentation_ready() -> None:
    assert len(PROJECT_DELIVERY_FIXTURES) >= 3

    for fixture in PROJECT_DELIVERY_FIXTURES:
        assert fixture["scenario_name"]
        assert fixture["milestone_name"]
        assert fixture["business_context"]
        assert fixture["executive_owner"]
        assert fixture["customer"]
        assert fixture["committed_revenue_usd"] >= 500000
        assert 50000 <= fixture["delay_cost_per_week_usd"] <= 500000
        assert 1 <= fixture["days_remaining"] <= 30
        assert fixture["completed_tasks"] < fixture["total_tasks"]
        assert fixture["remaining_engineering_hours"] > 0
        assert fixture["available_engineering_hours"] > 0
        assert fixture["remaining_story_points"] > 0
        assert len(fixture["velocity_history"]) >= 3
        assert len(fixture["external_dependencies"]) >= 2
        assert len(fixture["blockers"]) >= 2
        assert len(fixture["tasks"]) >= 8
        assert len(fixture["team_members"]) == fixture["team_size"]
        assert sum(task["estimate_hours"] for task in fixture["tasks"]) <= fixture[
            "remaining_engineering_hours"
        ]
        capacity_ceiling = fixture["available_engineering_hours"] * 1.5
        assert fixture["remaining_engineering_hours"] <= capacity_ceiling
        assert fixture["timeline_weeks"] >= 4
        assert "owner" in fixture["instruction"].lower()
        assert "executive" in fixture["instruction"].lower()

        for task in fixture["tasks"]:
            assert task["id"]
            assert task["skill"]
            assert task["estimate_hours"] > 0
            assert task["priority"] in {"NORMAL", "HIGH"}

        for member in fixture["team_members"]:
            assert member["name"]
            assert member["role"]
            assert member["skills"]
            assert 0 <= member["load_pct"] <= 100
            assert 0 <= member["availability_pct"] <= 100


def test_revenue_ops_seed_data_is_presentation_ready() -> None:
    assert len(REVENUE_OPS_FIXTURES) >= 3

    for fixture in REVENUE_OPS_FIXTURES:
        assert fixture["scenario_name"]
        assert fixture["business_context"]
        assert fixture["executive_owner"]
        assert fixture["account_name"]
        assert fixture["segment"]
        assert fixture["account_arr"] >= 300000
        assert fixture["renewal_arr_usd"] >= fixture["account_arr"] * 0.8
        assert fixture["churn_account_arr"] >= 300000
        assert 1 <= fixture["days_to_renewal"] <= 180
        assert 0 <= fixture["feature_adoption_score"] <= 10
        assert 0 <= fixture["historical_save_rate"] <= 1
        assert 0 <= fixture["early_intervention_value"] <= 1
        assert fixture["account_owner"]
        assert fixture["csm_owner"]
        assert fixture["exec_sponsor"]
        assert fixture["rep_name"]
        assert fixture["quota_target"] >= 1000000
        assert fixture["closed_to_date_usd"] >= 0
        assert fixture["commit_pipeline_usd"] >= 0
        assert fixture["best_case_pipeline_usd"] >= fixture["commit_pipeline_usd"]
        assert 1 <= fixture["days_remaining"] <= 31
        assert 0 < fixture["historical_close_rate"] <= 1
        assert len(fixture["pipeline_deals"]) >= 3
        weighted_pipeline = sum(
            deal["arr"] * deal["crm_probability"] for deal in fixture["pipeline_deals"]
        )
        assert weighted_pipeline > 0
        assert fixture["closed_to_date_usd"] + weighted_pipeline <= (
            fixture["quota_target"] + fixture["best_case_pipeline_usd"]
        )

        for deal in fixture["pipeline_deals"]:
            assert deal["account"]
            assert deal["arr"] > 0
            assert 0 < deal["crm_probability"] <= 1
            assert deal["stage"]
            assert deal["close_plan"]
            assert deal["risk"]
            assert deal["next_step"]

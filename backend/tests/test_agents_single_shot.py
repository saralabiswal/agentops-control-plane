import pytest
from sqlalchemy import select

from app.agents.project_delivery.delivery_forecast import DeliveryForecastAgent
from app.agents.project_delivery.resource_allocation import ResourceAllocationAgent
from app.agents.project_delivery.sprint_risk import SprintRiskAgent
from app.agents.revenue_ops.churn_signal import ChurnSignalAgent
from app.agents.revenue_ops.pipeline_forecast import PipelineForecastAgent
from app.agents.revenue_ops.renewal_risk import RenewalRiskAgent
from app.core.database import AsyncSessionLocal
from app.models.agent_run import AgentRun
from tests.conftest import FakeLLM, llm_response


class Dummy:
    pass


def make_agent(cls):
    return cls(Dummy(), Dummy())


@pytest.mark.parametrize(
    ("agent_cls", "payload", "valid_json", "required_text"),
    [
        (
            SprintRiskAgent,
            {
                "sprint_name": "Orion",
                "team_size": 4,
                "days_remaining": 5,
                "total_tasks": 10,
                "completed_tasks": 4,
                "velocity_history": [8, 9, 7],
            },
            '{"risk_score":0.7,"delivery_confidence_score":0.3,"risk_factors":[],"summary":"x"}',
            "Orion",
        ),
        (
            ResourceAllocationAgent,
            {"tasks": [{"id": "T1"}], "team_members": [{"name": "A"}], "sprint_weeks": 2},
            '{"assignments":[],"efficiency_gain_pct":0.2,"hours_saved_estimate":4,"summary":"x"}',
            "T1",
        ),
        (
            DeliveryForecastAgent,
            {
                "milestone_name": "Q3",
                "committed_revenue_usd": 100000,
                "target_date": "2026-09-30",
                "current_date": "2026-06-05",
                "backlog_count": 10,
                "avg_velocity": 5,
                "sprint_length_days": 14,
            },
            '{"confidence_score":0.8,"risk_factors":[],"summary":"x"}',
            "Q3",
        ),
        (
            RenewalRiskAgent,
            {
                "account_name": "Acme",
                "account_arr": 100000,
                "contract_end_date": "2026-09-30",
                "days_to_renewal": 90,
                "login_frequency_30d": 10,
                "feature_adoption_score": 5,
                "support_tickets_90d": 2,
            },
            '{"risk_score":0.4,"risk_factors":[],"summary":"x"}',
            "Acme",
        ),
        (
            ChurnSignalAgent,
            {
                "account_name": "Acme",
                "account_arr": 100000,
                "contract_end_date": "2026-09-30",
                "days_to_renewal": 90,
                "login_trend": "down",
                "adoption_trend": "flat",
            },
            '{"churn_probability":0.4,"top_signals":[],"summary":"x"}',
            "down",
        ),
        (
            PipelineForecastAgent,
            {
                "rep_name": "Sarah",
                "quota_target": 500000,
                "quarter_close_date": "2026-06-30",
                "days_remaining": 20,
                "historical_close_rate": 0.5,
                "avg_sales_cycle_days": 45,
                "pipeline_deals": [{"account": "Acme"}],
            },
            '{"attainment_forecast":0.8,"recoverable_gap_usd":50000,"focus_accounts":[],"summary":"x"}',
            "Sarah",
        ),
    ],
)
def test_single_shot_agents_build_prompt_and_parse(
    agent_cls, payload, valid_json, required_text
) -> None:
    agent = make_agent(agent_cls)

    prompt = agent.build_prompt(payload)
    parsed = agent.parse_output(valid_json)

    assert required_text in prompt
    assert "Respond ONLY with valid JSON" in prompt
    assert parsed["summary"] == "x"
    assert agent.QUALITY_RUBRIC


def test_single_shot_parse_rejects_bad_json() -> None:
    agent = make_agent(SprintRiskAgent)

    with pytest.raises(ValueError):
        agent.parse_output('{"risk_score":0.7}')


@pytest.mark.asyncio
async def test_base_agent_run_uses_agentops_contract(agentops, session_task) -> None:
    _session, task, _agent, pricing = session_task
    llm = FakeLLM(
        [
            llm_response(
                '{"risk_score":0.7,"delivery_confidence_score":0.3,'
                '"risk_factors":[],"summary":"Risky"}',
                model="llama3.2:latest",
            )
        ]
    )
    agent = SprintRiskAgent(llm, agentops)

    await agent.run(task, pricing.id)

    async with AsyncSessionLocal() as db:
        run = await db.scalar(select(AgentRun).where(AgentRun.task_id == task.id))

    assert run is not None
    assert run.status == "COMPLETE"
    assert run.model_used == "llama3.2:latest"
    assert run.output_payload["summary"] == "Risky"

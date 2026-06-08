import pytest
from sqlalchemy import select

from app.agentops.cost_calculator import CostCalculator
from app.agentops.manager import AgentOpsManager
from app.agentops.quality_queue import QualityQueue
from app.agentops.sse_emitter import SSEEmitter
from app.agents.project_delivery.delivery_forecast import DeliveryForecastAgent
from app.agents.project_delivery.resource_allocation import ResourceAllocationAgent
from app.agents.project_delivery.sprint_risk import SprintRiskAgent
from app.agents.revenue_ops.churn_signal import ChurnSignalAgent
from app.agents.revenue_ops.pipeline_forecast import PipelineForecastAgent
from app.agents.revenue_ops.renewal_risk import RenewalRiskAgent
from app.agents.workflow.project_planning import ProjectPlanningAgent
from app.core.database import AsyncSessionLocal
from app.core.enums import Domain, RunStatus
from app.models.agent_definition import AgentDefinition
from app.models.agent_run import AgentRun
from app.models.business_outcome import BusinessOutcome
from app.models.model_pricing import ModelPricing
from app.models.session import Session
from app.models.task import Task
from app.seed.project_delivery import PROJECT_DELIVERY_FIXTURES
from app.seed.revenue_ops import REVENUE_OPS_FIXTURES
from tests.conftest import FakeLLM, llm_response

__author__ = "Sarala Biswal"

pytestmark = pytest.mark.asyncio


async def _create_task(session: Session, agent_id: str, payload: dict) -> Task:
    async with AsyncSessionLocal() as db:
        agent = await db.get(AgentDefinition, agent_id)
        assert agent is not None
        task = Task(
            session_id=session.id,
            agent_id=agent.id,
            domain=agent.domain,
            task_type=agent.agent_type,
            input_payload=payload,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task


async def _pricing_id() -> str:
    async with AsyncSessionLocal() as db:
        pricing = await db.get(ModelPricing, "price-ollama-llama32-3b")
        assert pricing is not None
        return pricing.id


def _project_payloads(fixture: dict) -> list[tuple[str, dict]]:
    return [
        (
            "agent-sprint-risk",
            {
                key: fixture[key]
                for key in [
                    "sprint_name",
                    "team_size",
                    "days_remaining",
                    "total_tasks",
                    "completed_tasks",
                    "velocity_history",
                    "external_dependencies",
                    "capacity_notes",
                    "delay_cost_per_week_usd",
                ]
            },
        ),
        (
            "agent-resource-alloc",
            {
                key: fixture[key]
                for key in [
                    "tasks",
                    "team_members",
                    "sprint_weeks",
                    "avg_task_hours",
                    "hourly_rate",
                ]
            },
        ),
        (
            "agent-delivery-forecast",
            {
                key: fixture[key]
                for key in [
                    "milestone_name",
                    "committed_revenue_usd",
                    "target_date",
                    "current_date",
                    "backlog_count",
                    "avg_velocity",
                    "sprint_length_days",
                    "blockers",
                    "capacity_changes",
                ]
            },
        ),
        (
            "agent-project-planning",
            {
                key: fixture[key]
                for key in [
                    "instruction",
                    "team_members",
                    "timeline_weeks",
                    "committed_revenue_usd",
                ]
            },
        ),
    ]


def _revenue_payloads(fixture: dict) -> list[tuple[str, dict]]:
    return [
        (
            "agent-renewal-risk",
            {
                key: fixture[key]
                for key in [
                    "account_name",
                    "account_arr",
                    "contract_end_date",
                    "days_to_renewal",
                    "login_frequency_30d",
                    "feature_adoption_score",
                    "support_tickets_90d",
                    "nps_score",
                    "last_csm_touchpoint",
                    "upsell_conversations",
                    "historical_save_rate",
                ]
            },
        ),
        (
            "agent-churn-signal",
            {
                key: fixture[key]
                for key in [
                    "account_name",
                    "account_arr",
                    "contract_end_date",
                    "days_to_renewal",
                    "login_trend",
                    "adoption_trend",
                    "ticket_sentiment",
                    "exec_engagement",
                    "competitor_mentions",
                    "contract_downloads",
                    "early_intervention_value",
                ]
            },
        ),
        (
            "agent-pipeline-forecast",
            {
                key: fixture[key]
                for key in [
                    "rep_name",
                    "quota_target",
                    "quarter_close_date",
                    "days_remaining",
                    "historical_close_rate",
                    "avg_sales_cycle_days",
                    "pipeline_deals",
                ]
            },
        ),
    ]


def _project_management_llm_responses() -> list:
    return [
        llm_response(
            '{"risk_score":0.46,"delivery_confidence_score":0.62,'
            '"risk_level":"HIGH","risk_factors":[{"factor":"SOC2 evidence gap"}],'
            '"recommended_actions":["Asha owns evidence package by Friday"],'
            '"summary":"Launch has manageable but material delivery risk."}'
        ),
        llm_response(
            '{"assignments":[{"task_id":"OIDC-214","assigned_to":"Asha Rao"}],'
            '"overloaded_members":["Asha Rao"],"underutilized_members":["Devon Shah"],'
            '"efficiency_gain_pct":0.18,"hours_saved_estimate":22,'
            '"summary":"Rebalancing protects launch-critical work."}'
        ),
        llm_response(
            '{"confidence_score":0.72,"forecast_delivery_date":"2026-08-15",'
            '"days_variance":29,"pipeline_at_risk_usd":350000,'
            '"risk_factors":["Fraud-service test and SOC2 evidence block release"],'
            '"red_flags":["SOC2 controls incomplete"],'
            '"recommended_escalations":["VP Engineering clears Sev-2 support load"],'
            '"assumptions":["Velocity remains near recent trend"],'
            '"summary":"Milestone needs executive capacity intervention."}'
        ),
        llm_response(
            '{"epics":[{"id":"E-01","name":"Launch Recovery",'
            '"description":"Stabilize launch path","owner":"Asha Rao","weeks":"1-2",'
            '"stories":[{"id":"S-1","name":"SOC2 evidence closeout",'
            '"effort_points":5,"required_skills":["security"]}]}],'
            '"total_story_points":5,"critical_path":["S-1"]}'
        ),
        llm_response(
            '{"team_capacity":{"total_capacity":340,"available_capacity":250},'
            '"overloaded_members":[{"name":"Asha Rao","load_pct":82}],'
            '"skill_gaps":[{"name":"Devon Shah","missing_skills":["security"]}],'
            '"capacity_risk_level":"Moderate",'
            '"capacity_notes":"Launch-critical security work needs rebalancing."}'
        ),
        llm_response(
            '{"risk_register":[{"id":"R-1","title":"SOC2 evidence gap",'
            '"description":"Controls remain open","severity":"HIGH","likelihood":0.6,'
            '"impact":"Release delay","mitigation":"Daily evidence review",'
            '"owner":"Asha Rao","deadline":"Week 1"}],'
            '"overall_risk_level":"HIGH","delivery_confidence":0.64}'
        ),
        llm_response(
            '{"assignments":[{"story_id":"S-1","story_name":"SOC2 evidence closeout",'
            '"assigned_to":"Asha Rao","reasoning":"Security owner","epic_id":"E-01"}],'
            '"assignment_summary":"Owners aligned to the critical path."}'
        ),
        llm_response(
            '{"project_title":"Orion v4.2 Launch Recovery",'
            '"executive_summary":"Recovery plan protects committed bank launch revenue.",'
            '"delivery_confidence":0.64,"revenue_at_risk_usd":450000,'
            '"epics_with_assignments":[{"epic":"Launch Recovery"}],'
            '"top_risks":["SOC2 evidence gap"],'
            '"key_recommendations":["Clear production support load this week"],'
            '"timeline_weeks":6}'
        ),
    ]


def _revenue_ops_llm_responses() -> list:
    return [
        llm_response(
            '{"risk_score":0.58,"risk_level":"HIGH",'
            '"pipeline_protected_usd":219240,'
            '"risk_factors":["Low adoption and negative ticket sentiment"],'
            '"recommended_actions":["CRO sponsor call within 5 business days"],'
            '"summary":"Renewal needs executive save motion."}'
        ),
        llm_response(
            '{"churn_probability":0.41,"signal_strength":"HIGH","days_to_act":21,'
            '"early_intervention_value_usd":166050,'
            '"top_signals":["Login decline","Competitor mentions"],'
            '"recommended_play":"CSM and AE run adoption recovery workshop",'
            '"urgency":"High","summary":"Early churn indicators require action."}'
        ),
        llm_response(
            '{"attainment_forecast":0.76,"weighted_pipeline_usd":920000,'
            '"realistic_pipeline_usd":780000,"quota_gap_usd":240000,'
            '"recoverable_gap_usd":{"recoverable_gap_amount_usd":68000},'
            '"focus_accounts":[{"account":"Helio Manufacturing","next_step":"VP Sales call"}],'
            '"excluded_accounts":[{"account":"Koru Energy","reason":"budget moved"}],'
            '"summary":"Focused late-stage recovery can reduce the quota gap."}'
        ),
    ]


async def _run_domain_harness(
    *,
    session_name: str,
    payloads: list[tuple[str, dict]],
    agents: dict[str, object],
    expected_domain: Domain,
) -> None:
    pricing_id = await _pricing_id()
    async with AsyncSessionLocal() as db:
        session = Session(name=session_name)
        db.add(session)
        await db.commit()
        await db.refresh(session)

    tasks = [await _create_task(session, agent_id, payload) for agent_id, payload in payloads]
    for task in tasks:
        await agents[task.agent_id].run(task, pricing_id)

    async with AsyncSessionLocal() as db:
        task_ids = [task.id for task in tasks]
        runs = list(await db.scalars(select(AgentRun).where(AgentRun.task_id.in_(task_ids))))
        outcomes = list(
            await db.scalars(select(BusinessOutcome).where(BusinessOutcome.task_id.in_(task_ids)))
        )

    assert runs
    assert all(run.status == RunStatus.COMPLETE for run in runs)
    assert len(outcomes) == len(payloads)
    assert {outcome.domain for outcome in outcomes} == {expected_domain}
    assert all(outcome.financial_impact_usd >= 0 for outcome in outcomes)


async def test_project_management_demo_flow_completes_with_seed_payloads() -> None:
    llm = FakeLLM(_project_management_llm_responses())
    agentops = AgentOpsManager(SSEEmitter(), QualityQueue(SSEEmitter()), CostCalculator())
    agents = {
        "agent-sprint-risk": SprintRiskAgent(llm, agentops),
        "agent-resource-alloc": ResourceAllocationAgent(llm, agentops),
        "agent-delivery-forecast": DeliveryForecastAgent(llm, agentops),
        "agent-project-planning": ProjectPlanningAgent(llm, agentops),
    }

    await _run_domain_harness(
        session_name="Project Management Demo Harness",
        payloads=_project_payloads(PROJECT_DELIVERY_FIXTURES[0]),
        agents=agents,
        expected_domain=Domain.PROJECT_DELIVERY,
    )


async def test_revenue_ops_demo_flow_completes_with_seed_payloads() -> None:
    llm = FakeLLM(_revenue_ops_llm_responses())
    agentops = AgentOpsManager(SSEEmitter(), QualityQueue(SSEEmitter()), CostCalculator())
    agents = {
        "agent-renewal-risk": RenewalRiskAgent(llm, agentops),
        "agent-churn-signal": ChurnSignalAgent(llm, agentops),
        "agent-pipeline-forecast": PipelineForecastAgent(llm, agentops),
    }

    await _run_domain_harness(
        session_name="Revenue Ops Demo Harness",
        payloads=_revenue_payloads(REVENUE_OPS_FIXTURES[0]),
        agents=agents,
        expected_domain=Domain.REVENUE_OPS,
    )

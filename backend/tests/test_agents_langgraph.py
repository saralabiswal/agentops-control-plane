import json

import pytest
from sqlalchemy import select

from app.agentops.cost_calculator import CostCalculator
from app.agentops.manager import AgentOpsManager
from app.agentops.quality_queue import QualityQueue
from app.agentops.sse_emitter import SSEEmitter
from app.agents.workflow.project_planning import ProjectPlanningAgent
from app.core.database import AsyncSessionLocal
from app.models.agent_definition import AgentDefinition
from app.models.agent_run import AgentRun
from app.models.model_pricing import ModelPricing
from app.models.session import Session
from app.models.task import Task
from tests.conftest import FakeLLM, llm_response


def workflow_responses():
    return [
        llm_response(
            '{"epics":[{"id":"E-01","name":"Foundation","description":"Build",'
            '"owner":"Tom","weeks":"1-2","stories":[{"id":"S-1","name":"API",'
            '"effort_points":5,"required_skills":["backend"]}]}],'
            '"total_story_points":5,"critical_path":["E-01"]}'
        ),
        llm_response(
            '{"team_capacity":[{"name":"Tom","current_load_pct":50,'
            '"available_capacity_pct":50,"relevant_skills":["backend"],'
            '"recommended_stories":["S-1"]}],"overloaded_members":[],'
            '"skill_gaps":[],"capacity_risk_level":"LOW","capacity_notes":"OK"}'
        ),
        llm_response(
            '{"risk_register":[{"id":"R-1","title":"Dependency","description":"Risk",'
            '"severity":"LOW","likelihood":0.2,"impact":"Delay","mitigation":"Owner acts",'
            '"owner":"Tom","deadline":"Week 1"}],"overall_risk_level":"LOW",'
            '"delivery_confidence":0.8}'
        ),
        llm_response(
            '{"assignments":[{"story_id":"S-1","story_name":"API","assigned_to":"Tom",'
            '"reasoning":"Skill match","epic_id":"E-01"}],"assignment_summary":"OK"}'
        ),
        llm_response(
            '{"project_title":"Billing Migration","executive_summary":"Ready.",'
            '"delivery_confidence":0.8,"revenue_at_risk_usd":20000,'
            '"epics_with_assignments":[],"top_risks":["Dependency"],'
            '"key_recommendations":["Start now"],"timeline_weeks":8}'
        ),
    ]


def workflow_responses_without_stories():
    return [
        llm_response(
            '{"epics":[{"id":"E-01","name":"Foundation","description":"Build",'
            '"owner":"Tom","weeks":"1-2"}],"total_story_points":0,'
            '"critical_path":["E-01"]}'
        ),
        llm_response(
            '{"team_capacity":[{"name":"Tom","current_load_pct":50,'
            '"available_capacity_pct":50,"relevant_skills":["backend"],'
            '"recommended_stories":[]}],"overloaded_members":[],'
            '"skill_gaps":[],"capacity_risk_level":"LOW","capacity_notes":"OK"}'
        ),
        llm_response(
            '{"risk_register":[{"id":"R-1","title":"Dependency","description":"Risk",'
            '"severity":"LOW","likelihood":0.2,"impact":"Delay","mitigation":"Owner acts",'
            '"owner":"Tom","deadline":"Week 1"}],"overall_risk_level":"LOW",'
            '"delivery_confidence":0.8}'
        ),
        llm_response('{"assignments":[],"assignment_summary":"No stories to assign"}'),
        llm_response(
            '{"project_title":"Billing Migration","executive_summary":"Ready.",'
            '"delivery_confidence":0.8,"revenue_at_risk_usd":20000,'
            '"epics_with_assignments":[],"top_risks":["Dependency"],'
            '"key_recommendations":["Start now"],"timeline_weeks":8}'
        ),
    ]


def workflow_responses_with_task_epics_and_nested_assignment_results():
    assignment_results = json.dumps(
        {
            "Engineer 1": [
                "Integrate payload",
                "Perform propulsion system testing",
            ],
            "Engineer 2": ["Integrate propulsion system"],
            "Engineer 3": ["Validate payload performance"],
        }
    )
    return [
        llm_response(
            json.dumps(
                {
                    "epics": [
                        {
                            "name": "System Integration",
                            "description": "Integrate components",
                            "owners": ["Engineer 1", "Engineer 2"],
                            "tasks": [
                                {
                                    "name": "Integrate payload",
                                    "description": "Integrate payload",
                                    "story_points": 5,
                                },
                                {
                                    "name": "Integrate propulsion system",
                                    "description": "Integrate propulsion",
                                    "story_points": 6,
                                },
                            ],
                        },
                        {
                            "name": "Testing and Validation",
                            "description": "Validate components",
                            "owners": ["Engineer 1", "Engineer 3"],
                            "tasks": [
                                {
                                    "name": "Perform propulsion system testing",
                                    "description": "Test propulsion",
                                    "story_points": 10,
                                },
                                {
                                    "name": "Validate payload performance",
                                    "description": "Validate payload",
                                    "story_points": 8,
                                },
                            ],
                        },
                    ],
                    "total_story_points": 29,
                    "critical_path": ["Integrate payload"],
                }
            )
        ),
        llm_response(
            '{"team_capacity":80,"overloaded_members":["Mateo"],"skill_gaps":["data"],'
            '"capacity_risk_level":2,"capacity_notes":["Mateo is overloaded"]}'
        ),
        llm_response(
            '{"risk_register":[{"severity":8,"likelihood":6,'
            '"mitigation":"Add testing protocols","owner":"Engineer 1",'
            '"deadline":"End of week 2"}],"overall_risk_level":7.1,'
            '"delivery_confidence":75}'
        ),
        llm_response(
            json.dumps(
                {
                    "stories": ["Integrate payload", "Perform propulsion system testing"],
                    "assignment_summary": {
                        "team_capacity": 80,
                        "assignment_results": assignment_results,
                    },
                }
            )
        ),
        llm_response(
            '{"project_title":"Orion Recovery","executive_summary":"Ready.",'
            '"delivery_confidence":0.75,"revenue_at_risk_usd":20000,'
            '"epics_with_assignments":[],"top_risks":["Testing"],'
            '"key_recommendations":["Start now"],"timeline_weeks":6}'
        ),
    ]


def workflow_responses_with_repaired_risk_json():
    responses = workflow_responses()
    responses[2] = llm_response(
        '{"risk_register":[{"id":"R-1","title":"Security evidence",'
        '"description":"Risk","severity":8,"likelihood":6,'
        '"mitigation":"Use existing evidence package","owner":"Asha Rao",'
        '"deadline":"Week 2"}],"overall_risk_level":4,"delivery_confidence":70'
    )
    return responses


def workflow_responses_with_repaired_capacity_json():
    responses = workflow_responses()
    responses[1] = llm_response(
        '{'
        '"team_capacity":{"total_capacity":340,"available_capacity":250},'
        '"overloaded_members":[{"name":"Mateo Cruz","load":29}],'
        '"skill_gaps":['
        '{"name":"Asha Rao",["identity","release"]},'
        '{"name":"Devon Shah",["security"]}'
        '],'
        '"capacity_risk_level":"Moderate",'
        '"capacity_notes":"Mateo Cruz is overloaded."'
        '}'
    )
    return responses


@pytest.mark.asyncio
async def test_project_planning_workflow_creates_parent_and_child_runs() -> None:
    llm = FakeLLM(workflow_responses())
    sse = SSEEmitter()
    manager = AgentOpsManager(sse, QualityQueue(sse), CostCalculator())
    planning_agent = ProjectPlanningAgent(llm, manager)

    async with AsyncSessionLocal() as db:
        session = Session(name="Workflow Test")
        agent = await db.get(AgentDefinition, "agent-project-planning")
        pricing = await db.get(ModelPricing, "price-ollama-llama32-3b")
        assert agent is not None
        assert pricing is not None
        task = Task(
            session=session,
            agent_id=agent.id,
            domain=agent.domain,
            task_type=agent.agent_type,
            input_payload={
                "instruction": "Plan billing migration",
                "team_members": [
                    {
                        "name": "Tom",
                        "role": "Tech Lead",
                        "skills": ["backend"],
                        "load_pct": 50,
                    }
                ],
                "timeline_weeks": 8,
                "committed_revenue_usd": 100000,
            },
        )
        db.add_all([session, task])
        await db.commit()
        await db.refresh(task)

    await planning_agent.run(task, pricing.id)

    async with AsyncSessionLocal() as db:
        runs = list(await db.scalars(select(AgentRun).where(AgentRun.task_id == task.id)))

    parent = [run for run in runs if run.run_type == "WORKFLOW_PARENT"]
    children = [run for run in runs if run.run_type == "WORKFLOW_NODE"]
    assert len(parent) == 1
    assert len(children) == 5
    assert all(child.parent_run_id == parent[0].id for child in children)
    assert parent[0].output_payload["project_title"] == "Billing Migration"
    assert parent[0].total_tokens == 75


@pytest.mark.asyncio
async def test_project_planning_workflow_defaults_missing_stories_to_empty_list() -> None:
    llm = FakeLLM(workflow_responses_without_stories())
    sse = SSEEmitter()
    manager = AgentOpsManager(sse, QualityQueue(sse), CostCalculator())
    planning_agent = ProjectPlanningAgent(llm, manager)

    async with AsyncSessionLocal() as db:
        session = Session(name="Workflow Missing Stories Test")
        agent = await db.get(AgentDefinition, "agent-project-planning")
        pricing = await db.get(ModelPricing, "price-ollama-llama32-3b")
        assert agent is not None
        assert pricing is not None
        task = Task(
            session=session,
            agent_id=agent.id,
            domain=agent.domain,
            task_type=agent.agent_type,
            input_payload={
                "instruction": "Plan billing migration",
                "team_members": [
                    {
                        "name": "Tom",
                        "role": "Tech Lead",
                        "skills": ["backend"],
                        "load_pct": 50,
                    }
                ],
                "timeline_weeks": 8,
                "committed_revenue_usd": 100000,
            },
        )
        db.add_all([session, task])
        await db.commit()
        await db.refresh(task)

    await planning_agent.run(task, pricing.id)

    async with AsyncSessionLocal() as db:
        runs = list(await db.scalars(select(AgentRun).where(AgentRun.task_id == task.id)))

    parent = [run for run in runs if run.run_type == "WORKFLOW_PARENT"]
    children = [run for run in runs if run.run_type == "WORKFLOW_NODE"]
    assert len(parent) == 1
    assert len(children) == 5
    assert parent[0].status == "COMPLETE"
    assert parent[0].output_payload["project_title"] == "Billing Migration"
    assert "Stories to assign: []" in llm.prompts[3]


@pytest.mark.asyncio
async def test_project_planning_workflow_accepts_tasks_and_nested_assignment_results() -> None:
    llm = FakeLLM(workflow_responses_with_task_epics_and_nested_assignment_results())
    sse = SSEEmitter()
    manager = AgentOpsManager(sse, QualityQueue(sse), CostCalculator())
    planning_agent = ProjectPlanningAgent(llm, manager)

    async with AsyncSessionLocal() as db:
        session = Session(name="Workflow Ollama Shape Test")
        agent = await db.get(AgentDefinition, "agent-project-planning")
        pricing = await db.get(ModelPricing, "price-ollama-llama32-3b")
        assert agent is not None
        assert pricing is not None
        task = Task(
            session=session,
            agent_id=agent.id,
            domain=agent.domain,
            task_type=agent.agent_type,
            input_payload={
                "instruction": "Plan Orion recovery",
                "team_members": [
                    {
                        "name": "Asha",
                        "role": "Tech Lead",
                        "skills": ["backend"],
                        "load_pct": 50,
                    }
                ],
                "timeline_weeks": 6,
                "committed_revenue_usd": 620000,
            },
        )
        db.add_all([session, task])
        await db.commit()
        await db.refresh(task)

    await planning_agent.run(task, pricing.id)

    async with AsyncSessionLocal() as db:
        runs = list(await db.scalars(select(AgentRun).where(AgentRun.task_id == task.id)))

    parent = [run for run in runs if run.run_type == "WORKFLOW_PARENT"]
    children = [run for run in runs if run.run_type == "WORKFLOW_NODE"]
    assert len(parent) == 1
    assert len(children) == 5
    assert parent[0].status == "COMPLETE"
    assert parent[0].output_payload["project_title"] == "Orion Recovery"
    assert "Integrate payload" in llm.prompts[3]
    assert "Stories to assign: []" not in llm.prompts[3]


@pytest.mark.asyncio
async def test_project_planning_workflow_repairs_risk_node_json() -> None:
    llm = FakeLLM(workflow_responses_with_repaired_risk_json())
    sse = SSEEmitter()
    manager = AgentOpsManager(sse, QualityQueue(sse), CostCalculator())
    planning_agent = ProjectPlanningAgent(llm, manager)

    async with AsyncSessionLocal() as db:
        session = Session(name="Workflow Repaired Risk JSON Test")
        agent = await db.get(AgentDefinition, "agent-project-planning")
        pricing = await db.get(ModelPricing, "price-ollama-llama32-3b")
        assert agent is not None
        assert pricing is not None
        task = Task(
            session=session,
            agent_id=agent.id,
            domain=agent.domain,
            task_type=agent.agent_type,
            input_payload={
                "instruction": "Plan Orion recovery",
                "team_members": [
                    {
                        "name": "Asha Rao",
                        "role": "Tech Lead",
                        "skills": ["identity", "backend", "security"],
                        "load_pct": 70,
                    }
                ],
                "timeline_weeks": 6,
                "committed_revenue_usd": 1250000,
            },
        )
        db.add_all([session, task])
        await db.commit()
        await db.refresh(task)

    await planning_agent.run(task, pricing.id)

    async with AsyncSessionLocal() as db:
        runs = list(await db.scalars(select(AgentRun).where(AgentRun.task_id == task.id)))

    parent = [run for run in runs if run.run_type == "WORKFLOW_PARENT"]
    risk_node = [run for run in runs if run.agent_id == "node_risk_assess"]
    assert len(parent) == 1
    assert len(risk_node) == 1
    assert parent[0].status == "COMPLETE"
    assert risk_node[0].status == "COMPLETE"


@pytest.mark.asyncio
async def test_project_planning_workflow_repairs_capacity_keyless_skill_arrays() -> None:
    llm = FakeLLM(workflow_responses_with_repaired_capacity_json())
    sse = SSEEmitter()
    manager = AgentOpsManager(sse, QualityQueue(sse), CostCalculator())
    planning_agent = ProjectPlanningAgent(llm, manager)

    async with AsyncSessionLocal() as db:
        session = Session(name="Workflow Repaired Capacity JSON Test")
        agent = await db.get(AgentDefinition, "agent-project-planning")
        pricing = await db.get(ModelPricing, "price-ollama-llama32-3b")
        assert agent is not None
        assert pricing is not None
        task = Task(
            session=session,
            agent_id=agent.id,
            domain=agent.domain,
            task_type=agent.agent_type,
            input_payload={
                "instruction": "Plan Orion recovery",
                "team_members": [
                    {
                        "name": "Asha Rao",
                        "role": "Tech Lead",
                        "skills": ["identity", "backend", "security"],
                        "load_pct": 70,
                    }
                ],
                "timeline_weeks": 6,
                "committed_revenue_usd": 1250000,
            },
        )
        db.add_all([session, task])
        await db.commit()
        await db.refresh(task)

    await planning_agent.run(task, pricing.id)

    async with AsyncSessionLocal() as db:
        runs = list(await db.scalars(select(AgentRun).where(AgentRun.task_id == task.id)))

    parent = [run for run in runs if run.run_type == "WORKFLOW_PARENT"]
    capacity_node = [run for run in runs if run.agent_id == "node_capacity_check"]
    assert len(parent) == 1
    assert len(capacity_node) == 1
    assert parent[0].status == "COMPLETE"
    assert capacity_node[0].status == "COMPLETE"
    assert capacity_node[0].output_payload["skill_gaps"][0]["missing_skills"] == [
        "identity",
        "release",
    ]


@pytest.mark.asyncio
async def test_project_planning_workflow_records_parent_and_failed_node() -> None:
    llm = FakeLLM([llm_response("not-json")])
    sse = SSEEmitter()
    manager = AgentOpsManager(sse, QualityQueue(sse), CostCalculator())
    planning_agent = ProjectPlanningAgent(llm, manager)

    async with AsyncSessionLocal() as db:
        session = Session(name="Workflow Failure Test")
        agent = await db.get(AgentDefinition, "agent-project-planning")
        pricing = await db.get(ModelPricing, "price-ollama-llama32-3b")
        assert agent is not None
        assert pricing is not None
        task = Task(
            session=session,
            agent_id=agent.id,
            domain=agent.domain,
            task_type=agent.agent_type,
            input_payload={
                "instruction": "Plan billing migration",
                "team_members": [
                    {
                        "name": "Tom",
                        "role": "Tech Lead",
                        "skills": ["backend"],
                        "load_pct": 50,
                    }
                ],
                "timeline_weeks": 8,
                "committed_revenue_usd": 100000,
            },
        )
        db.add_all([session, task])
        await db.commit()
        await db.refresh(task)

    with pytest.raises(RuntimeError, match="Output parse failed"):
        await planning_agent.run(task, pricing.id)

    async with AsyncSessionLocal() as db:
        runs = list(await db.scalars(select(AgentRun).where(AgentRun.task_id == task.id)))

    parent = [run for run in runs if run.run_type == "WORKFLOW_PARENT"]
    children = [run for run in runs if run.run_type == "WORKFLOW_NODE"]
    assert len(parent) == 1
    assert len(children) == 1
    assert parent[0].status == "FAILED"
    assert "Output parse failed" in (parent[0].error_message or "")
    assert children[0].agent_id == "node_decompose"
    assert children[0].status == "FAILED"
    assert children[0].parent_run_id == parent[0].id

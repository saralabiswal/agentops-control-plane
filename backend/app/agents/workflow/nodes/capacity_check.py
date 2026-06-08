from typing import Any

from app.agentops.context import RunContext
from app.agents.parsing import JSON_ONLY, parse_json_object
from app.agents.workflow.state import ProjectPlanState


async def run(state: ProjectPlanState, ctx: RunContext, llm: Any) -> ProjectPlanState:
    prompt = f"""You are a capacity planning analyst.

Work breakdown: {state['work_breakdown']}
Timeline: {state['timeline_weeks']} weeks
Team members and current load: {state['team_members']}

Assess capacity, overloaded members, skill gaps, and capacity risks.
Return one JSON object with these fields:
- team_capacity: object or array summarizing current and available capacity
- overloaded_members: array of objects with name and load_pct
- skill_gaps: array of objects with name and missing_skills array
- capacity_risk_level: string or number
- capacity_notes: string or array of strings
{JSON_ONLY}"""
    response = await llm.complete(prompt)
    ctx.raw_prompt = prompt
    ctx.model_used = response.model
    ctx.raw_response = response.text
    ctx.prompt_tokens = response.usage.prompt_tokens
    ctx.completion_tokens = response.usage.completion_tokens
    data = parse_json_object(
        response.text,
        required=[
            "team_capacity",
            "overloaded_members",
            "skill_gaps",
            "capacity_risk_level",
            "capacity_notes",
        ],
        keyless_array_property="missing_skills",
    )
    state["node_traces"].append(
        {
            "node": "capacity_check",
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "latency_ms": response.latency_ms,
            "model": response.model,
        }
    )
    return {**state, "capacity_assessment": data}

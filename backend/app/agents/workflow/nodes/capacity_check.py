import json
from typing import Any

from app.agentops.context import RunContext
from app.agents.parsing import JSON_ONLY
from app.agents.workflow.state import ProjectPlanState


async def run(state: ProjectPlanState, ctx: RunContext, llm: Any) -> ProjectPlanState:
    prompt = f"""You are a capacity planning analyst.

Work breakdown: {state['work_breakdown']}
Timeline: {state['timeline_weeks']} weeks
Team members and current load: {state['team_members']}

Assess capacity, overloaded members, skill gaps, and capacity risks.
Return JSON with team_capacity, overloaded_members, skill_gaps,
capacity_risk_level, and capacity_notes.
{JSON_ONLY}"""
    response = await llm.complete(prompt)
    ctx.raw_prompt = prompt
    ctx.model_used = response.model
    ctx.raw_response = response.text
    ctx.prompt_tokens = response.usage.prompt_tokens
    ctx.completion_tokens = response.usage.completion_tokens
    data = json.loads(response.text.strip())
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

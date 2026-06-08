from typing import Any

from app.agentops.context import RunContext
from app.agents.parsing import JSON_ONLY, parse_json_object
from app.agents.workflow.state import ProjectPlanState


async def run(state: ProjectPlanState, ctx: RunContext, llm: Any) -> ProjectPlanState:
    prompt = f"""You are a project risk assessor.

Project plan: {state['work_breakdown']}
Capacity assessment: {state['capacity_assessment']}
Timeline: {state['timeline_weeks']} weeks
Committed revenue: ${state['committed_revenue_usd']:,}

Identify top delivery risks with severity, likelihood, mitigation, owner, and deadline.
Return JSON with risk_register, overall_risk_level, and delivery_confidence.
{JSON_ONLY}"""
    response = await llm.complete(prompt)
    ctx.raw_prompt = prompt
    ctx.model_used = response.model
    ctx.raw_response = response.text
    ctx.prompt_tokens = response.usage.prompt_tokens
    ctx.completion_tokens = response.usage.completion_tokens
    data = parse_json_object(
        response.text,
        required=["risk_register", "overall_risk_level", "delivery_confidence"],
    )
    state["node_traces"].append(
        {
            "node": "risk_assess",
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "latency_ms": response.latency_ms,
            "model": response.model,
        }
    )
    return {
        **state,
        "risk_register": data["risk_register"],
        "confidence_score": data.get("delivery_confidence"),
    }

from typing import Any

from app.agentops.context import RunContext
from app.agents.parsing import JSON_ONLY, parse_json_object
from app.agents.workflow.state import ProjectPlanState


async def run(state: ProjectPlanState, ctx: RunContext, llm: Any) -> ProjectPlanState:
    prompt = f"""You are a project plan synthesizer.

Instruction: {state['instruction']}
Work breakdown: {state['work_breakdown']}
Assignments: {state['assigned_plan']}
Risk register: {state['risk_register']}
Delivery confidence: {state['confidence_score']}
Committed revenue: ${state['committed_revenue_usd']:,}

Synthesize a final project plan readable by a VP in 30 seconds.
Return JSON with project_title, executive_summary, delivery_confidence,
revenue_at_risk_usd, epics_with_assignments, top_risks, key_recommendations,
and timeline_weeks.
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
            "project_title",
            "executive_summary",
            "delivery_confidence",
            "epics_with_assignments",
            "top_risks",
            "key_recommendations",
            "timeline_weeks",
        ],
    )
    state["node_traces"].append(
        {
            "node": "synthesize",
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "latency_ms": response.latency_ms,
            "model": response.model,
        }
    )
    return {**state, "final_plan": data, "confidence_score": data.get("delivery_confidence")}

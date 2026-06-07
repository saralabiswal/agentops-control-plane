from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.graph import END, StateGraph

from app.agentops.context import RunContext
from app.agentops.manager import AgentOpsManager
from app.agents.workflow.nodes import assign, capacity_check, decompose, risk_assess, synthesize
from app.agents.workflow.state import ProjectPlanState
from app.core.enums import RunType
from app.llm.client import LLMClient
from app.models.task import Task

NodeFn = Callable[[ProjectPlanState, RunContext, Any], Awaitable[ProjectPlanState]]


class ProjectPlanningAgent:
    def __init__(self, llm: LLMClient, agentops: AgentOpsManager) -> None:
        self.llm = llm
        self.agentops = agentops
        self._model_pricing_id = ""
        self.graph: Any
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        graph: Any = StateGraph(ProjectPlanState)
        graph.add_node("decompose", self._wrap_node("node_decompose", decompose.run))
        graph.add_node("capacity_check", self._wrap_node("node_capacity_check", capacity_check.run))
        graph.add_node("risk_assess", self._wrap_node("node_risk_assess", risk_assess.run))
        graph.add_node("assign", self._wrap_node("node_assign", assign.run))
        graph.add_node("synthesize", self._wrap_node("node_synthesize", synthesize.run))
        graph.set_entry_point("decompose")
        graph.add_edge("decompose", "capacity_check")
        graph.add_edge("capacity_check", "risk_assess")
        graph.add_edge("risk_assess", "assign")
        graph.add_edge("assign", "synthesize")
        graph.add_edge("synthesize", END)
        return graph.compile()

    def _wrap_node(
        self, node_agent_id: str, node_fn: NodeFn
    ) -> Callable[[ProjectPlanState], Awaitable[ProjectPlanState]]:
        async def wrapped(state: ProjectPlanState) -> ProjectPlanState:
            updated_state = state
            async with self.agentops.run_context(
                task_id=state["task_id"],
                agent_id=node_agent_id,
                session_id=state["session_id"],
                model_used=self.llm.active_model(),
                model_pricing_id=self._model_pricing_id,
                run_type=RunType.WORKFLOW_NODE,
                parent_run_id=state["parent_run_id"],
            ) as ctx:
                updated_state = await node_fn(state, ctx, self.llm)
                ctx.output_payload = {
                    "node": node_agent_id.removeprefix("node_"),
                    "status": "complete",
                }
            if ctx.error_message:
                raise RuntimeError(ctx.error_message)
            return updated_state

        return wrapped

    async def run(self, task: Task, model_pricing_id: str, retry_of: str | None = None) -> None:
        self._model_pricing_id = model_pricing_id
        async with self.agentops.run_context(
            task_id=task.id,
            agent_id=task.agent_id,
            session_id=task.session_id,
            model_used=self.llm.active_model(),
            model_pricing_id=model_pricing_id,
            run_type=RunType.WORKFLOW_PARENT,
            retry_of=retry_of,
        ) as ctx:
            ctx.raw_prompt = task.input_payload["instruction"]
            initial_state: ProjectPlanState = {
                "instruction": task.input_payload["instruction"],
                "team_members": task.input_payload["team_members"],
                "timeline_weeks": task.input_payload["timeline_weeks"],
                "committed_revenue_usd": task.input_payload["committed_revenue_usd"],
                "task_id": task.id,
                "session_id": task.session_id,
                "parent_run_id": ctx.run_id,
                "work_breakdown": None,
                "capacity_assessment": None,
                "risk_register": None,
                "assigned_plan": None,
                "final_plan": None,
                "confidence_score": None,
                "node_traces": [],
            }
            final_state = await self.graph.ainvoke(initial_state)
            ctx.prompt_tokens = sum(t.get("prompt_tokens", 0) for t in final_state["node_traces"])
            ctx.completion_tokens = sum(
                t.get("completion_tokens", 0) for t in final_state["node_traces"]
            )
            resolved_models = [
                str(t["model"]) for t in final_state["node_traces"] if t.get("model")
            ]
            if resolved_models:
                ctx.model_used = resolved_models[-1]
            ctx.output_payload = final_state.get("final_plan") or {}

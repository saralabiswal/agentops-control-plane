from app.agentops.manager import AgentOpsManager
from app.agents.base import BaseAgent
from app.agents.project_delivery.delivery_forecast import DeliveryForecastAgent
from app.agents.project_delivery.resource_allocation import ResourceAllocationAgent
from app.agents.project_delivery.sprint_risk import SprintRiskAgent
from app.agents.revenue_ops.churn_signal import ChurnSignalAgent
from app.agents.revenue_ops.pipeline_forecast import PipelineForecastAgent
from app.agents.revenue_ops.renewal_risk import RenewalRiskAgent
from app.agents.workflow.project_planning import ProjectPlanningAgent
from app.llm.client import LLMClient

__author__ = "Sarala Biswal"


class AgentRegistry:
    def __init__(self, llm: LLMClient, agentops: AgentOpsManager) -> None:
        """Build the in-process catalog from persisted agent IDs to executable classes."""
        self._agents: dict[str, BaseAgent | ProjectPlanningAgent] = {
            "agent-sprint-risk": SprintRiskAgent(llm, agentops),
            "agent-resource-alloc": ResourceAllocationAgent(llm, agentops),
            "agent-delivery-forecast": DeliveryForecastAgent(llm, agentops),
            "agent-renewal-risk": RenewalRiskAgent(llm, agentops),
            "agent-churn-signal": ChurnSignalAgent(llm, agentops),
            "agent-pipeline-forecast": PipelineForecastAgent(llm, agentops),
            "agent-project-planning": ProjectPlanningAgent(llm, agentops),
        }

    def get(self, agent_id: str) -> BaseAgent | ProjectPlanningAgent:
        """Return the executable agent bound to the requested catalog ID."""
        try:
            return self._agents[agent_id]
        except KeyError as exc:
            raise ValueError(f"Unknown agent_id: {agent_id}") from exc

from abc import ABC, abstractmethod
from typing import Any

from app.agentops.manager import AgentOpsManager
from app.core.enums import RunType
from app.llm.client import LLMClient
from app.models.task import Task


class BaseAgent(ABC):
    QUALITY_RUBRIC = ""

    def __init__(self, llm: LLMClient, agentops: AgentOpsManager) -> None:
        self.llm = llm
        self.agentops = agentops

    async def run(self, task: Task, model_pricing_id: str, retry_of: str | None = None) -> None:
        async with self.agentops.run_context(
            task_id=task.id,
            agent_id=task.agent_id,
            session_id=task.session_id,
            model_used=self.llm.active_model(),
            model_pricing_id=model_pricing_id,
            run_type=RunType.SINGLE_SHOT,
            retry_of=retry_of,
        ) as ctx:
            prompt = self.build_prompt(task.input_payload)
            ctx.raw_prompt = prompt
            response = await self.llm.complete(prompt)
            ctx.model_used = response.model
            ctx.raw_response = response.text
            ctx.prompt_tokens = response.usage.prompt_tokens
            ctx.completion_tokens = response.usage.completion_tokens
            ctx.output_payload = self.parse_output(response.text)

    @abstractmethod
    def build_prompt(self, input_payload: dict[str, Any]) -> str:
        ...

    @abstractmethod
    def parse_output(self, raw_response: str) -> dict[str, Any]:
        ...

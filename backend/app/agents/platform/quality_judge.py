import json
from typing import Any

from sqlalchemy import select

from app.agentops.context import RunContext
from app.core.database import AsyncSessionLocal
from app.llm.client import LLMClient
from app.models.agent_definition import AgentDefinition


class QualityJudgeAgent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def score(self, ctx: RunContext) -> dict[str, Any]:
        rubric = await self._rubric_for(ctx.agent_id)
        prompt = f"""You are an objective quality evaluator for AI agent outputs.

ORIGINAL TASK INPUT:
{ctx.raw_prompt}

AGENT OUTPUT:
{ctx.raw_response}

EVALUATION RUBRIC:
{rubric}

Score relevance, faithfulness, completeness, and actionability from 0.0 to 1.0.
Respond ONLY with valid JSON containing relevance, faithfulness, completeness,
actionability, composite, and reasoning_trace.
"""
        try:
            response = await self.llm.complete(prompt, model=self.llm.settings.quality_judge_model)
            scores = json.loads(response.text.strip())
        except Exception as exc:
            return {
                "quality_score": 0.0,
                "quality_relevance": 0.0,
                "quality_faithfulness": 0.0,
                "quality_completeness": 0.0,
                "quality_actionability": 0.0,
                "quality_dimensions": {
                    "reasoning_trace": f"Judge failed: {type(exc).__name__}: {exc}"
                },
            }
        relevance = self._dimension_score(scores.get("relevance"))
        faithfulness = self._dimension_score(scores.get("faithfulness"))
        completeness = self._dimension_score(scores.get("completeness"))
        actionability = self._dimension_score(scores.get("actionability"))
        composite = round(
            (relevance + faithfulness + completeness + actionability) / 4,
            3,
        )
        return {
            "quality_score": composite,
            "quality_relevance": relevance,
            "quality_faithfulness": faithfulness,
            "quality_completeness": completeness,
            "quality_actionability": actionability,
            "quality_dimensions": {
                "reasoning_trace": self._reasoning_trace(scores.get("reasoning_trace"))
            },
        }

    async def _rubric_for(self, agent_id: str) -> str:
        async with AsyncSessionLocal() as db:
            result = await db.scalar(
                select(AgentDefinition.quality_rubric).where(AgentDefinition.id == agent_id)
            )
        return result or "Evaluate relevance, faithfulness, completeness, and actionability."

    def _dimension_score(self, value: Any) -> float:
        if isinstance(value, (int, float)):
            return self._rate(float(value))
        if isinstance(value, str):
            normalized = value.replace("%", "").strip()
            if not normalized:
                return 0.0
            try:
                return self._rate(float(normalized))
            except ValueError:
                return 0.0
        if isinstance(value, dict):
            for key in ("score", "value", "rating", "confidence"):
                if key in value:
                    return self._dimension_score(value[key])
            for nested in value.values():
                score = self._dimension_score(nested)
                if score > 0:
                    return score
        if isinstance(value, list):
            for nested in value:
                score = self._dimension_score(nested)
                if score > 0:
                    return score
        return 0.0

    def _rate(self, value: float) -> float:
        if value > 1:
            value = value / 100
        return min(max(value, 0.0), 1.0)

    def _reasoning_trace(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if value is None:
            return ""
        return json.dumps(value, sort_keys=True)

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
        composite = round(
            (
                float(scores.get("relevance", 0))
                + float(scores.get("faithfulness", 0))
                + float(scores.get("completeness", 0))
                + float(scores.get("actionability", 0))
            )
            / 4,
            3,
        )
        return {
            "quality_score": composite,
            "quality_relevance": float(scores.get("relevance", 0)),
            "quality_faithfulness": float(scores.get("faithfulness", 0)),
            "quality_completeness": float(scores.get("completeness", 0)),
            "quality_actionability": float(scores.get("actionability", 0)),
            "quality_dimensions": {"reasoning_trace": scores.get("reasoning_trace", "")},
        }

    async def _rubric_for(self, agent_id: str) -> str:
        async with AsyncSessionLocal() as db:
            result = await db.scalar(
                select(AgentDefinition.quality_rubric).where(AgentDefinition.id == agent_id)
            )
        return result or "Evaluate relevance, faithfulness, completeness, and actionability."

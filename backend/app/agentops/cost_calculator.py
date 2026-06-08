from sqlalchemy.ext.asyncio import AsyncSession

from app.agentops.context import RunContext
from app.models.model_pricing import ModelPricing

__author__ = "Sarala Biswal"

API_CALLS_PER_AGENT_RUN = 4
COMPUTE_VCPU_PER_AGENT_RUN = 1.0
COMPUTE_MEMORY_GIB_PER_AGENT_RUN = 0.5


class CostCalculator:
    async def calculate(self, db: AsyncSession, ctx: RunContext) -> float:
        """Calculate total run cost across LLM tokens, API calls, and compute time."""
        pricing = await db.get(ModelPricing, ctx.model_pricing_id)
        if pricing is None:
            return 0.0
        token_cost = (
            (ctx.prompt_tokens / 1000) * pricing.input_cost_per_1k
            + (ctx.completion_tokens / 1000) * pricing.output_cost_per_1k
        )
        api_call_cost = (API_CALLS_PER_AGENT_RUN / 1000) * pricing.api_call_cost_per_1k
        compute_seconds = max(ctx.latency_ms / 1000, 0.0)
        compute_cost = compute_seconds * (
            COMPUTE_VCPU_PER_AGENT_RUN * pricing.compute_vcpu_cost_per_second
            + COMPUTE_MEMORY_GIB_PER_AGENT_RUN * pricing.compute_memory_gib_cost_per_second
        )
        return float(token_cost + api_call_cost + compute_cost)

    async def calculate_token_only(self, db: AsyncSession, ctx: RunContext) -> float:
        """Calculate only the LLM token component for tests and cost breakdowns."""
        pricing = await db.get(ModelPricing, ctx.model_pricing_id)
        if pricing is None:
            return 0.0
        return float(
            (ctx.prompt_tokens / 1000) * pricing.input_cost_per_1k
            + (ctx.completion_tokens / 1000) * pricing.output_cost_per_1k
        )

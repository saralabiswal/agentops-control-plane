from sqlalchemy.ext.asyncio import AsyncSession

from app.agentops.context import RunContext
from app.models.model_pricing import ModelPricing

__author__ = "Sarala Biswal"


class CostCalculator:
    async def calculate(self, db: AsyncSession, ctx: RunContext) -> float:
        """Convert prompt/completion tokens into USD using the seeded pricing table."""
        pricing = await db.get(ModelPricing, ctx.model_pricing_id)
        if pricing is None:
            return 0.0
        return float(
            (ctx.prompt_tokens / 1000) * pricing.input_cost_per_1k
            + (ctx.completion_tokens / 1000) * pricing.output_cost_per_1k
        )

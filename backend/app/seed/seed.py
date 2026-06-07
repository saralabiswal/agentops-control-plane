import asyncio
from typing import Any

from sqlalchemy.dialects.sqlite import insert

from app.core.database import AsyncSessionLocal
from app.models.agent_definition import AgentDefinition
from app.models.model_pricing import ModelPricing
from app.seed.agents import AGENT_DEFINITIONS, WORKFLOW_NODE_DEFINITIONS
from app.seed.pricing import MODEL_PRICING


async def run_seed() -> None:
    async with AsyncSessionLocal() as db:
        agent_records: list[dict[str, Any]] = [*AGENT_DEFINITIONS, *WORKFLOW_NODE_DEFINITIONS]
        pricing_records: list[dict[str, Any]] = MODEL_PRICING
        for record in agent_records:
            stmt = insert(AgentDefinition).values(record).prefix_with("OR IGNORE")
            await db.execute(stmt)
        for record in pricing_records:
            stmt = insert(ModelPricing).values(record)
            stmt = stmt.on_conflict_do_update(
                index_elements=[ModelPricing.id],
                set_={
                    "provider": stmt.excluded.provider,
                    "model_name": stmt.excluded.model_name,
                    "input_cost_per_1k": stmt.excluded.input_cost_per_1k,
                    "output_cost_per_1k": stmt.excluded.output_cost_per_1k,
                    "effective_to": stmt.excluded.effective_to,
                },
            )
            await db.execute(stmt)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(run_seed())

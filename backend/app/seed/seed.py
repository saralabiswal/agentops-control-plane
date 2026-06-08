import asyncio
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.dialects.sqlite import insert

from app.core.database import AsyncSessionLocal, engine
from app.models.agent_definition import AgentDefinition
from app.models.model_pricing import ModelPricing
from app.seed.agents import AGENT_DEFINITIONS, WORKFLOW_NODE_DEFINITIONS
from app.seed.pricing import MODEL_PRICING

PRICING_COLUMN_DEFAULTS = {
    "api_call_cost_per_1k": 0.0,
    "compute_vcpu_cost_per_second": 0.0,
    "compute_memory_gib_cost_per_second": 0.0,
}


async def ensure_pricing_schema() -> None:
    async with engine.begin() as conn:
        def missing_columns(sync_conn: Any) -> list[tuple[str, float]]:
            inspector = inspect(sync_conn)
            if "model_pricing" not in inspector.get_table_names():
                return []
            existing = {column["name"] for column in inspector.get_columns("model_pricing")}
            return [
                (name, default)
                for name, default in PRICING_COLUMN_DEFAULTS.items()
                if name not in existing
            ]

        for name, default in await conn.run_sync(missing_columns):
            await conn.execute(
                text(
                    "ALTER TABLE model_pricing "
                    f"ADD COLUMN {name} FLOAT NOT NULL DEFAULT {default}"
                )
            )


async def run_seed() -> None:
    await ensure_pricing_schema()
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
                    "api_call_cost_per_1k": stmt.excluded.api_call_cost_per_1k,
                    "compute_vcpu_cost_per_second": (
                        stmt.excluded.compute_vcpu_cost_per_second
                    ),
                    "compute_memory_gib_cost_per_second": (
                        stmt.excluded.compute_memory_gib_cost_per_second
                    ),
                    "effective_to": stmt.excluded.effective_to,
                },
            )
            await db.execute(stmt)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(run_seed())

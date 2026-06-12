import asyncio
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, inspect, select, text
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine
from app.models.agent_definition import AgentDefinition
from app.models.agent_run import AgentRun
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
            await _upsert_pricing_record(db, record)
        await db.commit()


async def _upsert_pricing_record(db: AsyncSession, record: dict[str, Any]) -> None:
    existing = await db.get(ModelPricing, record["id"])
    if existing is None:
        db.add(ModelPricing(**record))
        return
    if not _pricing_differs(existing, record):
        return

    reference_count = await db.scalar(
        select(func.count(AgentRun.id)).where(AgentRun.model_pricing_id == existing.id)
    )
    if not reference_count:
        _apply_pricing_values(existing, record)
        return

    now = datetime.now(UTC)
    existing.effective_to = existing.effective_to or now
    replacement = dict(record)
    replacement["id"] = f"{record['id']}-{int(now.timestamp())}"
    replacement["effective_from"] = now
    db.add(ModelPricing(**replacement))


def _pricing_differs(pricing: ModelPricing, record: dict[str, Any]) -> bool:
    return any(
        getattr(pricing, field) != record[field]
        for field in (
            "provider",
            "model_name",
            "input_cost_per_1k",
            "output_cost_per_1k",
            "api_call_cost_per_1k",
            "compute_vcpu_cost_per_second",
            "compute_memory_gib_cost_per_second",
            "effective_to",
        )
    )


def _apply_pricing_values(pricing: ModelPricing, record: dict[str, Any]) -> None:
    for field in (
        "provider",
        "model_name",
        "input_cost_per_1k",
        "output_cost_per_1k",
        "api_call_cost_per_1k",
        "compute_vcpu_cost_per_second",
        "compute_memory_gib_cost_per_second",
        "effective_to",
    ):
        setattr(pricing, field, record[field])


if __name__ == "__main__":
    asyncio.run(run_seed())

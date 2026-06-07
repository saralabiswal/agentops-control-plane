import pytest
from sqlalchemy import update

from app.core.database import AsyncSessionLocal
from app.models.model_pricing import ModelPricing
from app.seed.pricing import (
    GCP_INPUT_COST_PER_1K,
    GCP_OUTPUT_COST_PER_1K,
    LOCAL_DEMO_INPUT_COST_PER_1K,
    LOCAL_DEMO_OUTPUT_COST_PER_1K,
    MODEL_PRICING,
)
from app.seed.seed import run_seed


def _pricing_by_id(pricing_id: str) -> dict[str, object]:
    return next(record for record in MODEL_PRICING if record["id"] == pricing_id)


def test_local_ollama_pricing_uses_elevated_demo_price() -> None:
    gemini = _pricing_by_id("price-gemini-20-flash")
    assert gemini["input_cost_per_1k"] == GCP_INPUT_COST_PER_1K
    assert gemini["output_cost_per_1k"] == GCP_OUTPUT_COST_PER_1K

    for pricing_id in (
        "price-ollama-llama32-3b",
        "price-ollama-llama32-latest",
        "price-ollama-llama31-8b",
        "price-ollama-llama31-latest",
    ):
        local = _pricing_by_id(pricing_id)
        assert local["input_cost_per_1k"] == LOCAL_DEMO_INPUT_COST_PER_1K
        assert local["output_cost_per_1k"] == LOCAL_DEMO_OUTPUT_COST_PER_1K
        assert local["input_cost_per_1k"] > gemini["input_cost_per_1k"]
        assert local["output_cost_per_1k"] > gemini["output_cost_per_1k"]


@pytest.mark.asyncio
async def test_seed_updates_existing_pricing_rows() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(ModelPricing)
            .where(ModelPricing.id == "price-ollama-llama32-3b")
            .values(input_cost_per_1k=0.0, output_cost_per_1k=0.0)
        )
        await db.commit()

    await run_seed()

    async with AsyncSessionLocal() as db:
        pricing = await db.get(ModelPricing, "price-ollama-llama32-3b")

    assert pricing is not None
    assert pricing.input_cost_per_1k == LOCAL_DEMO_INPUT_COST_PER_1K
    assert pricing.output_cost_per_1k == LOCAL_DEMO_OUTPUT_COST_PER_1K

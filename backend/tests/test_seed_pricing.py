import pytest
from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.models.agent_run import AgentRun
from app.models.model_pricing import ModelPricing
from app.models.session import Session
from app.models.task import Task
from app.seed.pricing import (
    DEMO_COST_ELEVATION_MULTIPLIER,
    GCP_API_CALL_COST_PER_1K,
    GCP_COMPUTE_MEMORY_GIB_COST_PER_SECOND,
    GCP_COMPUTE_VCPU_COST_PER_SECOND,
    GCP_INPUT_COST_PER_1K,
    GCP_OUTPUT_COST_PER_1K,
    LOCAL_DEMO_API_CALL_COST_PER_1K,
    LOCAL_DEMO_COMPUTE_MEMORY_GIB_COST_PER_SECOND,
    LOCAL_DEMO_COMPUTE_VCPU_COST_PER_SECOND,
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
    assert gemini["api_call_cost_per_1k"] == GCP_API_CALL_COST_PER_1K
    assert gemini["compute_vcpu_cost_per_second"] == GCP_COMPUTE_VCPU_COST_PER_SECOND
    assert (
        gemini["compute_memory_gib_cost_per_second"]
        == GCP_COMPUTE_MEMORY_GIB_COST_PER_SECOND
    )

    for pricing_id in (
        "price-ollama-llama32-3b",
        "price-ollama-llama32-latest",
        "price-ollama-llama31-8b",
        "price-ollama-llama31-latest",
    ):
        local = _pricing_by_id(pricing_id)
        assert local["input_cost_per_1k"] == LOCAL_DEMO_INPUT_COST_PER_1K
        assert local["output_cost_per_1k"] == LOCAL_DEMO_OUTPUT_COST_PER_1K
        assert local["api_call_cost_per_1k"] == LOCAL_DEMO_API_CALL_COST_PER_1K
        assert (
            local["compute_vcpu_cost_per_second"]
            == LOCAL_DEMO_COMPUTE_VCPU_COST_PER_SECOND
        )
        assert (
            local["compute_memory_gib_cost_per_second"]
            == LOCAL_DEMO_COMPUTE_MEMORY_GIB_COST_PER_SECOND
        )
        assert local["input_cost_per_1k"] == pytest.approx(
            gemini["input_cost_per_1k"] * DEMO_COST_ELEVATION_MULTIPLIER
        )
        assert local["output_cost_per_1k"] == pytest.approx(
            gemini["output_cost_per_1k"] * DEMO_COST_ELEVATION_MULTIPLIER
        )
        assert local["input_cost_per_1k"] > gemini["input_cost_per_1k"]
        assert local["output_cost_per_1k"] > gemini["output_cost_per_1k"]


@pytest.mark.asyncio
async def test_seed_updates_existing_pricing_rows() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(ModelPricing)
            .where(ModelPricing.id == "price-ollama-llama32-3b")
            .values(
                input_cost_per_1k=0.0,
                output_cost_per_1k=0.0,
                api_call_cost_per_1k=0.0,
                compute_vcpu_cost_per_second=0.0,
                compute_memory_gib_cost_per_second=0.0,
            )
        )
        await db.commit()

    await run_seed()

    async with AsyncSessionLocal() as db:
        pricing = await db.get(ModelPricing, "price-ollama-llama32-3b")

    assert pricing is not None
    assert pricing.input_cost_per_1k == LOCAL_DEMO_INPUT_COST_PER_1K
    assert pricing.output_cost_per_1k == LOCAL_DEMO_OUTPUT_COST_PER_1K
    assert pricing.api_call_cost_per_1k == LOCAL_DEMO_API_CALL_COST_PER_1K
    assert pricing.compute_vcpu_cost_per_second == LOCAL_DEMO_COMPUTE_VCPU_COST_PER_SECOND
    assert (
        pricing.compute_memory_gib_cost_per_second
        == LOCAL_DEMO_COMPUTE_MEMORY_GIB_COST_PER_SECOND
    )


@pytest.mark.asyncio
async def test_seed_expires_referenced_pricing_instead_of_mutating_it() -> None:
    async with AsyncSessionLocal() as db:
        session = Session(name="Historical Pricing")
        db.add(session)
        await db.flush()
        task = Task(
            session_id=session.id,
            agent_id="agent-sprint-risk",
            domain="PROJECT_DELIVERY",
            task_type="sprint_risk_assessment",
            input_payload={},
        )
        db.add(task)
        await db.flush()
        db.add(
            AgentRun(
                id="historical-pricing-run",
                task_id=task.id,
                agent_id="agent-sprint-risk",
                model_pricing_id="price-ollama-llama32-3b",
                run_type="SINGLE_SHOT",
                model_used="llama3.2:3b",
                status="COMPLETE",
                raw_prompt="prompt",
                raw_response="{}",
                output_payload={},
            )
        )
        await db.execute(
            update(ModelPricing)
            .where(ModelPricing.id == "price-ollama-llama32-3b")
            .values(input_cost_per_1k=0.0, output_cost_per_1k=0.0)
        )
        await db.commit()

    await run_seed()

    async with AsyncSessionLocal() as db:
        historical = await db.get(ModelPricing, "price-ollama-llama32-3b")
        active_rows = list(
            await db.scalars(
                select(ModelPricing).where(
                    ModelPricing.provider == "ollama",
                    ModelPricing.model_name == "llama3.2:3b",
                    ModelPricing.effective_to.is_(None),
                )
            )
        )

    assert historical is not None
    assert historical.input_cost_per_1k == 0.0
    assert historical.output_cost_per_1k == 0.0
    assert historical.effective_to is not None
    assert len(active_rows) == 1
    assert active_rows[0].id != historical.id
    assert active_rows[0].input_cost_per_1k == LOCAL_DEMO_INPUT_COST_PER_1K

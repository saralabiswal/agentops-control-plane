from typing import cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.agent_definition import AgentDefinition
from app.models.model_pricing import ModelPricing
from app.schemas.agent_run import AgentDefinitionSchema, ModelPricingSchema

router = APIRouter()


@router.get("/agents", response_model=list[AgentDefinitionSchema])
async def list_agents(db: AsyncSession = Depends(get_db)) -> list[AgentDefinition]:
    result = await db.scalars(
        select(AgentDefinition).where(~AgentDefinition.id.startswith("node_"))
    )
    return list(result)


@router.get("/agents/{agent_id}", response_model=AgentDefinitionSchema)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)) -> AgentDefinition:
    agent = await db.get(AgentDefinition, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return cast(AgentDefinition, agent)


@router.get("/pricing", response_model=list[ModelPricingSchema])
async def list_pricing(db: AsyncSession = Depends(get_db)) -> list[ModelPricing]:
    result = await db.scalars(select(ModelPricing))
    return list(result)

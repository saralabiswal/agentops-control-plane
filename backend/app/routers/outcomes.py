from typing import cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.agent_run import AgentRun
from app.models.business_outcome import BusinessOutcome
from app.models.task import Task
from app.schemas.business_outcome import (
    BusinessOutcomeSchema,
    OutcomeSummarySchema,
    SessionOutcomesSchema,
)

router = APIRouter()


@router.get("/outcomes/session/{session_id}", response_model=SessionOutcomesSchema)
async def get_session_outcomes(
    session_id: str, db: AsyncSession = Depends(get_db)
) -> SessionOutcomesSchema:
    outcomes = list(
        await db.scalars(select(BusinessOutcome).join(Task).where(Task.session_id == session_id))
    )
    total = sum(outcome.financial_impact_usd for outcome in outcomes)
    return SessionOutcomesSchema(
        session_id=session_id,
        total_financial_impact_usd=total,
        outcomes=[BusinessOutcomeSchema.model_validate(outcome) for outcome in outcomes],
    )


@router.get("/outcomes/summary", response_model=OutcomeSummarySchema)
async def get_outcome_summary(db: AsyncSession = Depends(get_db)) -> OutcomeSummarySchema:
    impact = float(
        await db.scalar(select(func.coalesce(func.sum(BusinessOutcome.financial_impact_usd), 0.0)))
        or 0
    )
    cost = float(await db.scalar(select(func.coalesce(func.sum(AgentRun.cost_usd), 0.0))) or 0)
    return OutcomeSummarySchema(
        total_financial_impact_usd=impact,
        total_cost_usd=cost,
        roi_multiple=impact / cost if cost else 0.0,
    )


@router.get("/outcomes/{run_id}", response_model=BusinessOutcomeSchema)
async def get_outcome(run_id: str, db: AsyncSession = Depends(get_db)) -> BusinessOutcome:
    outcome = await db.scalar(select(BusinessOutcome).where(BusinessOutcome.agent_run_id == run_id))
    if outcome is None:
        raise HTTPException(status_code=404, detail="Outcome not found")
    return cast(BusinessOutcome, outcome)

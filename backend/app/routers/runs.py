from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.agent_run import AgentRun
from app.models.task import Task
from app.schemas.agent_run import AgentRunDetailSchema, AgentRunSchema, QualityDetailSchema

router = APIRouter()


@router.get("/runs", response_model=list[AgentRunSchema])
async def list_runs(
    session_id: str | None = None,
    agent_id: str | None = None,
    domain: str | None = None,
    status: str | None = None,
    from_ts: datetime | None = Query(default=None, alias="from"),
    to_ts: datetime | None = Query(default=None, alias="to"),
    db: AsyncSession = Depends(get_db),
) -> list[AgentRun]:
    stmt = select(AgentRun)
    if domain or session_id:
        stmt = stmt.join(Task)
    if session_id:
        stmt = stmt.where(Task.session_id == session_id)
    if domain:
        stmt = stmt.where(Task.domain == domain)
    if agent_id:
        stmt = stmt.where(AgentRun.agent_id == agent_id)
    if status:
        stmt = stmt.where(AgentRun.status == status)
    if from_ts:
        stmt = stmt.where(AgentRun.ran_at >= from_ts)
    if to_ts:
        stmt = stmt.where(AgentRun.ran_at <= to_ts)
    result = await db.scalars(stmt.order_by(AgentRun.ran_at.desc()))
    return list(result)


@router.get("/runs/{run_id}", response_model=AgentRunDetailSchema)
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    run = await db.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    children = await db.scalars(select(AgentRun).where(AgentRun.parent_run_id == run_id))
    data = AgentRunSchema.model_validate(run).model_dump()
    data["child_runs"] = [_run_dict(child) for child in children]
    return data


@router.get("/runs/{run_id}/quality", response_model=QualityDetailSchema)
async def get_run_quality(
    run_id: str, db: AsyncSession = Depends(get_db)
) -> QualityDetailSchema:
    run = await db.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return QualityDetailSchema(
        run_id=run.id,
        quality_score=run.quality_score,
        quality_relevance=run.quality_relevance,
        quality_faithfulness=run.quality_faithfulness,
        quality_completeness=run.quality_completeness,
        quality_actionability=run.quality_actionability,
        quality_dimensions=run.quality_dimensions,
    )


@router.get("/runs/{run_id}/retries", response_model=list[AgentRunSchema])
async def get_retries(run_id: str, db: AsyncSession = Depends(get_db)) -> list[AgentRun]:
    result = await db.scalars(select(AgentRun).where(AgentRun.retry_of == run_id))
    return list(result)


def _run_dict(run: AgentRun) -> dict[str, Any]:
    return {key: value for key, value in run.__dict__.items() if not key.startswith("_")}

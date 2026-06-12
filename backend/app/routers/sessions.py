from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.enums import RunStatus
from app.models.agent_run import AgentRun
from app.models.business_outcome import BusinessOutcome
from app.models.session import Session
from app.models.task import Task
from app.schemas.session import SessionCreateRequest, SessionDetailSchema, SessionSchema

router = APIRouter()


@router.post("/sessions", response_model=SessionSchema)
async def create_session(
    payload: SessionCreateRequest, db: AsyncSession = Depends(get_db)
) -> Session:
    session = Session(name=payload.name)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions", response_model=list[SessionSchema])
async def list_sessions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[Session]:
    result = await db.scalars(
        select(Session).order_by(Session.started_at.desc()).offset(offset).limit(limit)
    )
    return list(result)


@router.get("/sessions/{session_id}", response_model=SessionDetailSchema)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    session: Session | None = await db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    tasks = await db.scalars(select(Task).where(Task.session_id == session_id))
    outcomes = await db.scalars(
        select(BusinessOutcome).join(Task).where(Task.session_id == session_id)
    )
    data = SessionSchema.model_validate(session).model_dump()
    data["tasks"] = [task.__dict__ for task in tasks]
    data["outcomes"] = [outcome.__dict__ for outcome in outcomes]
    return data


@router.post("/sessions/{session_id}/close", response_model=SessionSchema)
async def close_session(session_id: str, db: AsyncSession = Depends(get_db)) -> Session:
    session = await db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    total_tasks = await db.scalar(select(func.count(Task.id)).where(Task.session_id == session_id))
    successful = await db.scalar(
        select(func.count(AgentRun.id))
        .join(Task)
        .where(Task.session_id == session_id, AgentRun.status == RunStatus.COMPLETE)
    )
    total_cost = await db.scalar(
        select(func.coalesce(func.sum(AgentRun.cost_usd), 0.0))
        .join(Task)
        .where(Task.session_id == session_id)
    )
    avg_quality = await db.scalar(
        select(func.coalesce(func.avg(AgentRun.quality_score), 0.0))
        .join(Task)
        .where(Task.session_id == session_id)
    )
    session.status = "CLOSED"
    session.ended_at = datetime.now(UTC)
    session.total_tasks = int(total_tasks or 0)
    session.total_cost_usd = float(total_cost or 0)
    session.success_rate = float(successful or 0) / max(session.total_tasks, 1)
    session.avg_quality_score = float(avg_quality or 0)
    await db.commit()
    refreshed_session: Session | None = await db.get(Session, session_id)
    if refreshed_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return refreshed_session

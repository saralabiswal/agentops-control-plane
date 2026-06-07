from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.agent_run import AgentRun
from app.models.metric import Metric

router = APIRouter()


@router.get("/metrics/cost")
async def cost_metrics(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    rows = await db.execute(
        select(Metric.metric_name, func.sum(Metric.metric_value))
        .where(Metric.metric_name == "cost_usd")
        .group_by(Metric.metric_name)
    )
    return [{"metric_name": name, "value": value} for name, value in rows]


@router.get("/metrics/quality")
async def quality_metrics(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    rows = await db.execute(
        select(AgentRun.agent_id, func.avg(AgentRun.quality_score))
        .where(AgentRun.quality_score.is_not(None))
        .group_by(AgentRun.agent_id)
    )
    return [{"agent_id": agent_id, "avg_quality_score": value} for agent_id, value in rows]


@router.get("/metrics/latency")
async def latency_metrics(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    rows = await db.execute(
        select(
            AgentRun.agent_id,
            func.avg(AgentRun.latency_ms),
            func.max(AgentRun.latency_ms),
        ).group_by(AgentRun.agent_id)
    )
    return [
        {"agent_id": agent_id, "avg_latency_ms": avg, "max_latency_ms": max_}
        for agent_id, avg, max_ in rows
    ]


@router.get("/metrics/throughput")
async def throughput_metrics(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    total = await db.scalar(select(func.count(AgentRun.id)))
    complete = await db.scalar(select(func.count(AgentRun.id)).where(AgentRun.status == "COMPLETE"))
    failed = await db.scalar(select(func.count(AgentRun.id)).where(AgentRun.status == "FAILED"))
    return {"total_runs": total or 0, "complete_runs": complete or 0, "failed_runs": failed or 0}

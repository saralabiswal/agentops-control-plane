from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.agent_run import AgentRun
from app.models.metric import Metric

router = APIRouter()


def _time_window(
    from_ts: datetime | None,
    to_ts: datetime | None,
    window_days: int,
) -> tuple[datetime, datetime]:
    end = to_ts or datetime.now(UTC)
    start = from_ts or end - timedelta(days=window_days)
    return start, end


@router.get("/metrics/cost")
async def cost_metrics(
    from_ts: datetime | None = Query(default=None, alias="from"),
    to_ts: datetime | None = Query(default=None, alias="to"),
    window_days: int = Query(default=7, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    start, end = _time_window(from_ts, to_ts, window_days)
    rows = await db.execute(
        select(Metric.metric_name, func.sum(Metric.metric_value))
        .where(Metric.metric_name == "cost_usd")
        .where(Metric.ts >= start, Metric.ts <= end)
        .group_by(Metric.metric_name)
    )
    return [{"metric_name": name, "value": value} for name, value in rows]


@router.get("/metrics/quality")
async def quality_metrics(
    from_ts: datetime | None = Query(default=None, alias="from"),
    to_ts: datetime | None = Query(default=None, alias="to"),
    window_days: int = Query(default=7, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    start, end = _time_window(from_ts, to_ts, window_days)
    rows = await db.execute(
        select(AgentRun.agent_id, func.avg(AgentRun.quality_score))
        .where(AgentRun.quality_score.is_not(None))
        .where(AgentRun.ran_at >= start, AgentRun.ran_at <= end)
        .group_by(AgentRun.agent_id)
    )
    return [{"agent_id": agent_id, "avg_quality_score": value} for agent_id, value in rows]


@router.get("/metrics/latency")
async def latency_metrics(
    from_ts: datetime | None = Query(default=None, alias="from"),
    to_ts: datetime | None = Query(default=None, alias="to"),
    window_days: int = Query(default=7, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    start, end = _time_window(from_ts, to_ts, window_days)
    rows = await db.execute(
        select(
            AgentRun.agent_id,
            func.avg(AgentRun.latency_ms),
            func.max(AgentRun.latency_ms),
        )
        .where(AgentRun.ran_at >= start, AgentRun.ran_at <= end)
        .group_by(AgentRun.agent_id)
    )
    return [
        {"agent_id": agent_id, "avg_latency_ms": avg, "max_latency_ms": max_}
        for agent_id, avg, max_ in rows
    ]


@router.get("/metrics/throughput")
async def throughput_metrics(
    from_ts: datetime | None = Query(default=None, alias="from"),
    to_ts: datetime | None = Query(default=None, alias="to"),
    window_days: int = Query(default=7, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    start, end = _time_window(from_ts, to_ts, window_days)
    window_filter = (AgentRun.ran_at >= start, AgentRun.ran_at <= end)
    total = await db.scalar(select(func.count(AgentRun.id)).where(*window_filter))
    complete = await db.scalar(
        select(func.count(AgentRun.id)).where(*window_filter, AgentRun.status == "COMPLETE")
    )
    failed = await db.scalar(
        select(func.count(AgentRun.id)).where(*window_filter, AgentRun.status == "FAILED")
    )
    return {"total_runs": total or 0, "complete_runs": complete or 0, "failed_runs": failed or 0}

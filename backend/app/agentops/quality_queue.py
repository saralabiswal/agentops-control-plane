import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import update

from app.agentops.context import RunContext
from app.agentops.sse_emitter import SSEEmitter
from app.core.database import AsyncSessionLocal
from app.core.enums import QualityStatus
from app.models.agent_run import AgentRun
from app.models.metric import Metric


class QualityQueue:
    def __init__(
        self,
        sse: SSEEmitter | None = None,
        *,
        max_attempts: int = 2,
        retry_delay_seconds: float = 0.05,
    ) -> None:
        self.queue: asyncio.Queue[RunContext] = asyncio.Queue()
        self.sse = sse
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds

    async def enqueue(self, ctx: RunContext) -> None:
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(AgentRun)
                .where(AgentRun.id == ctx.run_id)
                .values(
                    quality_status=QualityStatus.PENDING,
                    quality_error=None,
                )
            )
            await db.commit()
        await self.queue.put(ctx)

    async def worker(
        self,
        judge: object,
        stop_when_empty: bool = False,
    ) -> None:
        score: Callable[[RunContext], Awaitable[dict[str, Any]]] = judge.score  # type: ignore[attr-defined]
        while True:
            try:
                timeout = 0.2 if stop_when_empty else None
                ctx = await asyncio.wait_for(self.queue.get(), timeout=timeout)
            except TimeoutError:
                if stop_when_empty:
                    return
                continue
            try:
                scores = await score(ctx)
                ctx.quality_score = scores.get("quality_score")
                ctx.quality_relevance = scores.get("quality_relevance")
                ctx.quality_faithfulness = scores.get("quality_faithfulness")
                ctx.quality_completeness = scores.get("quality_completeness")
                ctx.quality_actionability = scores.get("quality_actionability")
                ctx.quality_dimensions = scores.get("quality_dimensions")
                await self._record_success(ctx)
                if self.sse is not None:
                    await self.sse.emit_quality_scored(ctx)
            except Exception as exc:
                attempts = await self._record_failure(ctx, exc)
                if attempts < self.max_attempts:
                    await asyncio.sleep(self.retry_delay_seconds)
                    await self.queue.put(ctx)
            finally:
                self.queue.task_done()

    async def _record_success(self, ctx: RunContext) -> None:
        async with AsyncSessionLocal() as db:
            run = await db.get(AgentRun, ctx.run_id)
            attempts = 1 if run is None else run.quality_attempt_count + 1
            await db.execute(
                update(AgentRun)
                .where(AgentRun.id == ctx.run_id)
                .values(
                    quality_score=ctx.quality_score,
                    quality_relevance=ctx.quality_relevance,
                    quality_faithfulness=ctx.quality_faithfulness,
                    quality_completeness=ctx.quality_completeness,
                    quality_actionability=ctx.quality_actionability,
                    quality_dimensions=ctx.quality_dimensions,
                    quality_status=QualityStatus.SCORED,
                    quality_error=None,
                    quality_attempt_count=attempts,
                )
            )
            if ctx.quality_score is not None:
                db.add(
                    Metric(
                        agent_run_id=ctx.run_id,
                        metric_name="quality_score",
                        metric_value=ctx.quality_score,
                        dimensions={
                            "agent_id": ctx.agent_id,
                            "session_id": ctx.session_id,
                            "model": ctx.model_used,
                        },
                    )
                )
            await db.commit()

    async def _record_failure(self, ctx: RunContext, exc: Exception) -> int:
        async with AsyncSessionLocal() as db:
            run = await db.get(AgentRun, ctx.run_id)
            attempts = 1 if run is None else run.quality_attempt_count + 1
            await db.execute(
                update(AgentRun)
                .where(AgentRun.id == ctx.run_id)
                .values(
                    quality_status=QualityStatus.FAILED,
                    quality_error=f"{type(exc).__name__}: {exc}",
                    quality_attempt_count=attempts,
                )
            )
            await db.commit()
            return attempts

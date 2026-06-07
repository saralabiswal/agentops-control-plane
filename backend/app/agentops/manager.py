from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentops.context import RunContext
from app.agentops.cost_calculator import CostCalculator
from app.agentops.quality_queue import QualityQueue
from app.agentops.sse_emitter import SSEEmitter
from app.core.database import AsyncSessionLocal
from app.core.enums import RunStatus, RunType, TaskStatus
from app.llm.base import LLMConfigurationError
from app.models.agent_definition import AgentDefinition
from app.models.agent_run import AgentRun
from app.models.metric import Metric
from app.models.task import Task
from app.outcomes.calculator import BusinessOutcomeCalculator

__author__ = "Sarala Biswal"


class AgentOpsManager:
    def __init__(
        self,
        sse_emitter: SSEEmitter,
        quality_queue: QualityQueue,
        cost_calculator: CostCalculator,
        outcome_calculator: BusinessOutcomeCalculator | None = None,
    ) -> None:
        self.sse = sse_emitter
        self.quality = quality_queue
        self.cost = cost_calculator
        self.outcomes = outcome_calculator or BusinessOutcomeCalculator()

    @asynccontextmanager
    async def run_context(
        self,
        task_id: str,
        agent_id: str,
        session_id: str,
        model_used: str,
        model_pricing_id: str,
        run_type: RunType = RunType.SINGLE_SHOT,
        parent_run_id: str | None = None,
        retry_of: str | None = None,
        run_id: str | None = None,
    ) -> AsyncIterator[RunContext]:
        """Wrap every agent execution with trace, metrics, cost, outcome, and quality writes."""
        ctx = RunContext(
            run_id=run_id or str(uuid4()),
            task_id=task_id,
            agent_id=agent_id,
            session_id=session_id,
            started_at=datetime.now(UTC),
            model_used=model_used,
            model_pricing_id=model_pricing_id,
            run_type=run_type,
            parent_run_id=parent_run_id,
            retry_of=retry_of,
        )
        async with AsyncSessionLocal() as db:
            await self._write_run(db, ctx)
            await db.execute(
                update(Task)
                .where(Task.id == ctx.task_id)
                .values(status=TaskStatus.RUNNING, started_at=ctx.started_at)
            )
            await db.commit()

        await self.sse.emit_run_started(ctx)
        should_reraise = False
        try:
            yield ctx
            ctx.status = RunStatus.COMPLETE
        except (
            LLMConfigurationError,
            httpx.TimeoutException,
            httpx.HTTPStatusError,
            httpx.RequestError,
            ValueError,
        ) as exc:
            ctx.status = RunStatus.FAILED
            ctx.error_message = self._known_error_message(exc)
        except Exception as exc:
            ctx.status = RunStatus.FAILED
            ctx.error_message = f"Unexpected error: {type(exc).__name__}: {exc}"
            should_reraise = True
        finally:
            ctx.completed_at = datetime.now(UTC)
            ctx.latency_ms = int((ctx.completed_at - ctx.started_at).total_seconds() * 1000)
            ctx.total_tokens = ctx.prompt_tokens + ctx.completion_tokens
            async with AsyncSessionLocal() as db:
                # This is the single persistence boundary for successful and failed runs.
                ctx.cost_usd = await self.cost.calculate(db, ctx)
                await self._update_run(db, ctx)
                await self._write_metrics(db, ctx)
                if ctx.status == RunStatus.COMPLETE and ctx.output_payload:
                    await self.outcomes.write_for_run(db, ctx)
                await db.execute(
                    update(Task)
                    .where(Task.id == ctx.task_id)
                    .values(
                        status=TaskStatus.COMPLETE
                        if ctx.status == RunStatus.COMPLETE
                        else TaskStatus.FAILED,
                        completed_at=ctx.completed_at,
                    )
                )
                await db.commit()
            await self.sse.emit_run_completed(ctx)
            if ctx.status == RunStatus.COMPLETE and ctx.output_payload:
                await self.quality.enqueue(ctx)
        if should_reraise:
            raise RuntimeError(ctx.error_message)

    async def _write_run(self, db: AsyncSession, ctx: RunContext) -> None:
        db.add(
            AgentRun(
                id=ctx.run_id,
                task_id=ctx.task_id,
                agent_id=ctx.agent_id,
                model_pricing_id=ctx.model_pricing_id,
                run_type=ctx.run_type,
                parent_run_id=ctx.parent_run_id,
                retry_of=ctx.retry_of,
                model_used=ctx.model_used,
                status=ctx.status,
                raw_prompt="",
                raw_response="",
                output_payload={},
                ran_at=ctx.started_at,
            )
        )

    async def _update_run(self, db: AsyncSession, ctx: RunContext) -> None:
        await db.execute(
            update(AgentRun)
            .where(AgentRun.id == ctx.run_id)
            .values(
                prompt_tokens=ctx.prompt_tokens,
                completion_tokens=ctx.completion_tokens,
                total_tokens=ctx.total_tokens,
                latency_ms=ctx.latency_ms,
                cost_usd=ctx.cost_usd,
                status=ctx.status,
                error_message=ctx.error_message,
                model_used=ctx.model_used,
                raw_prompt=ctx.raw_prompt,
                raw_response=ctx.raw_response,
                output_payload=ctx.output_payload,
                completed_at=ctx.completed_at,
            )
        )

    async def _write_metrics(self, db: AsyncSession, ctx: RunContext) -> None:
        """Persist time-series style operational metrics for dashboards and drift views."""
        domain = await self._resolve_domain(db, ctx.agent_id)
        dimensions = {
            "agent_id": ctx.agent_id,
            "domain": domain,
            "session_id": ctx.session_id,
            "model": ctx.model_used,
        }
        metrics = [
            ("latency_ms", float(ctx.latency_ms)),
            ("cost_usd", ctx.cost_usd),
            ("prompt_tokens", float(ctx.prompt_tokens)),
            ("completion_tokens", float(ctx.completion_tokens)),
        ]
        for metric_name, metric_value in metrics:
            db.add(
                Metric(
                    agent_run_id=ctx.run_id,
                    metric_name=metric_name,
                    metric_value=metric_value,
                    dimensions=dimensions,
                )
            )

    async def _resolve_domain(self, db: AsyncSession, agent_id: str) -> str:
        agent = await db.get(AgentDefinition, agent_id)
        return str(agent.domain) if agent is not None else "PLATFORM"

    def _known_error_message(self, exc: Exception) -> str:
        if isinstance(exc, LLMConfigurationError):
            return f"LLM configuration error: {exc}"
        if isinstance(exc, httpx.TimeoutException):
            return f"LLM timeout after {exc}"
        if isinstance(exc, httpx.HTTPStatusError):
            return f"LLM provider error {exc.response.status_code}: {exc.response.text[:200]}"
        if isinstance(exc, httpx.RequestError):
            return f"LLM provider request failed: {exc}"
        return f"Output parse failed: {exc}"


async def recover_stale_runs() -> None:
    """Mark interrupted RUNNING records as failed so restarts do not leave ghost work."""
    async with AsyncSessionLocal() as db:
        stale = await db.scalars(select(AgentRun).where(AgentRun.status == RunStatus.RUNNING))
        now = datetime.now(UTC)
        for run in stale:
            run.status = RunStatus.FAILED
            run.error_message = "Recovered stale RUNNING record on startup"
            run.completed_at = now
        await db.commit()

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update

from app.agents.registry import AgentRegistry
from app.core.database import AsyncSessionLocal
from app.core.enums import TaskStatus
from app.models.agent_run import AgentRun
from app.models.task import Task

logger = logging.getLogger(__name__)


class TaskWorker:
    """Poll the persisted task queue and execute claimed work in bounded batches."""

    def __init__(
        self,
        registry_provider: Callable[[], AgentRegistry],
        *,
        poll_interval_seconds: float = 0.25,
        max_concurrent_tasks: int = 6,
    ) -> None:
        self._registry_provider = registry_provider
        self._poll_interval_seconds = poll_interval_seconds
        self._max_concurrent_tasks = max_concurrent_tasks
        self._stop = asyncio.Event()
        self._runner: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._runner is None or self._runner.done():
            self._stop.clear()
            self._runner = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._runner is None:
            return
        self._runner.cancel()
        try:
            await self._runner
        except asyncio.CancelledError:
            pass

    async def run_until_idle(self, *, max_rounds: int = 50) -> int:
        """Process queued work synchronously until no immediately available jobs remain."""
        total = 0
        for _ in range(max_rounds):
            processed = await self.process_once()
            total += processed
            if processed == 0:
                return total
        raise RuntimeError("Task queue did not become idle within max_rounds")

    async def process_once(self) -> int:
        jobs = await self._claim_queued_tasks()
        if not jobs:
            return 0
        await execute_tasks_concurrently(
            [
                (task_id, self._registry_provider(), model_pricing_id, retry_of_run_id)
                for task_id, model_pricing_id, retry_of_run_id in jobs
            ]
        )
        return len(jobs)

    async def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                processed = await self.process_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Task worker polling failed")
                processed = 0
            if processed == 0:
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self._poll_interval_seconds
                    )
                except TimeoutError:
                    pass

    async def _claim_queued_tasks(self) -> list[tuple[str, str, str | None]]:
        async with AsyncSessionLocal() as db:
            tasks = list(
                await db.scalars(
                    select(Task)
                    .where(
                        Task.status == TaskStatus.QUEUED,
                        Task.model_pricing_id.is_not(None),
                    )
                    .order_by(Task.submitted_at)
                    .limit(self._max_concurrent_tasks)
                )
            )
            now = datetime.now(UTC)
            jobs: list[tuple[str, str, str | None]] = []
            for task in tasks:
                if task.model_pricing_id is None:
                    continue
                task.status = TaskStatus.RUNNING
                task.started_at = task.started_at or now
                task.claimed_at = now
                task.attempt_count += 1
                task.last_error = None
                jobs.append((task.id, task.model_pricing_id, task.retry_of_run_id))
            await db.commit()
            return jobs


async def recover_stale_tasks() -> None:
    """Return interrupted RUNNING tasks to a recoverable terminal or queued state."""
    async with AsyncSessionLocal() as db:
        running_tasks = list(
            await db.scalars(select(Task).where(Task.status == TaskStatus.RUNNING))
        )
        for task in running_tasks:
            completed_count = await db.scalar(
                select(func.count(AgentRun.id)).where(
                    AgentRun.task_id == task.id,
                    AgentRun.status == "COMPLETE",
                )
            )
            if completed_count:
                task.status = TaskStatus.COMPLETE
                continue
            failed_count = await db.scalar(
                select(func.count(AgentRun.id)).where(
                    AgentRun.task_id == task.id,
                    AgentRun.status == "FAILED",
                )
            )
            if failed_count:
                task.status = TaskStatus.FAILED
                task.completed_at = task.completed_at or datetime.now(UTC)
                continue
            task.status = TaskStatus.QUEUED
            task.started_at = None
            task.claimed_at = None
            task.last_error = "Recovered interrupted task claim on startup"
        await db.commit()


async def execute_task(
    task_id: str,
    registry: AgentRegistry,
    model_pricing_id: str | None = None,
    retry_of: str | None = None,
) -> None:
    """Load a queued task and hand it to the registered agent."""
    try:
        async with AsyncSessionLocal() as db:
            task = await db.get(Task, task_id)
            if task is None:
                return
            resolved_pricing_id = model_pricing_id or task.model_pricing_id
            resolved_retry_of = retry_of if retry_of is not None else task.retry_of_run_id
            if resolved_pricing_id is None:
                raise ValueError(f"Task {task_id} has no model pricing id")
            await registry.get(task.agent_id).run(
                task,
                resolved_pricing_id,
                retry_of=resolved_retry_of,
            )
    except Exception as exc:
        logger.exception("Task execution failed for task %s", task_id)
        await _mark_task_failed_if_unfinished(task_id, exc)


async def execute_tasks_concurrently(
    jobs: list[tuple[str, AgentRegistry, str, str | None]],
) -> None:
    """Run claimed tasks concurrently while containing individual worker failures."""
    results = await asyncio.gather(
        *(
            execute_task(task_id, registry, model_pricing_id, retry_of)
            for task_id, registry, model_pricing_id, retry_of in jobs
        ),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, Exception):
            logger.error(
                "Task worker escaped its execution guard",
                exc_info=(type(result), result, result.__traceback__),
            )


async def _mark_task_failed_if_unfinished(task_id: str, exc: Exception | None = None) -> None:
    async with AsyncSessionLocal() as db:
        values: dict[str, Any] = {"status": TaskStatus.FAILED}
        if exc is not None:
            values["last_error"] = f"{type(exc).__name__}: {exc}"
        await db.execute(
            update(Task)
            .where(Task.id == task_id, Task.status.not_in([TaskStatus.COMPLETE, TaskStatus.FAILED]))
            .values(**values)
        )
        await db.commit()

import asyncio
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.registry import AgentRegistry
from app.core.database import get_db
from app.llm.client import LLMClient
from app.models.agent_definition import AgentDefinition
from app.models.agent_run import AgentRun
from app.models.model_pricing import ModelPricing
from app.models.task import Task
from app.routers.deps import get_llm, get_registry
from app.schemas.task import (
    TaskBatchRequest,
    TaskDetailSchema,
    TaskSchema,
    TaskStatusSchema,
    TaskSubmitRequest,
)

__author__ = "Sarala Biswal"

router = APIRouter()


async def _pricing_id(db: AsyncSession, agent: AgentDefinition, model_name: str) -> str:
    """Resolve pricing for the active model, falling back to the seeded agent default."""
    pricing = await db.scalar(
        select(ModelPricing).where(
            ModelPricing.model_name == model_name,
            ModelPricing.effective_to.is_(None),
        )
    )
    if pricing is None:
        pricing = await db.scalar(
            select(ModelPricing).where(
                ModelPricing.model_name == agent.model_default,
                ModelPricing.effective_to.is_(None),
            )
        )
    if pricing is None:
        raise HTTPException(status_code=400, detail=f"No pricing for model {model_name}")
    return str(pricing.id)


async def execute_task(task_id: str, registry: AgentRegistry, model_pricing_id: str) -> None:
    """Load the queued task in a background worker and hand it to the registered agent."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        task = await db.get(Task, task_id)
        if task is None:
            return
        await registry.get(task.agent_id).run(task, model_pricing_id)


async def execute_tasks_concurrently(
    jobs: list[tuple[str, AgentRegistry, str]],
) -> None:
    """Run a submitted scope as independent task executions under one API request."""
    await asyncio.gather(
        *(
            execute_task(task_id, registry, model_pricing_id)
            for task_id, registry, model_pricing_id in jobs
        )
    )


@router.post("/tasks", response_model=TaskSchema)
async def submit_task(
    payload: TaskSubmitRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    registry: AgentRegistry = Depends(get_registry),
    llm: LLMClient = Depends(get_llm),
) -> Task:
    """Submit one agent task and schedule it for background execution."""
    agent = await db.get(AgentDefinition, payload.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    pricing_id = await _pricing_id(db, agent, llm.active_model())
    task = Task(
        session_id=payload.session_id,
        agent_id=payload.agent_id,
        domain=agent.domain,
        task_type=agent.agent_type,
        input_payload=payload.input_payload,
        priority=payload.priority,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    background_tasks.add_task(execute_task, task.id, registry, pricing_id)
    return task


@router.post("/tasks/batch", response_model=list[TaskSchema])
async def submit_batch(
    payload: TaskBatchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    registry: AgentRegistry = Depends(get_registry),
    llm: LLMClient = Depends(get_llm),
) -> list[Task]:
    """Submit a domain/platform run as multiple tasks and start them concurrently."""
    tasks: list[Task] = []
    jobs: list[tuple[str, AgentRegistry, str]] = []
    for item in payload.tasks:
        agent = await db.get(AgentDefinition, item.agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail=f"Agent not found: {item.agent_id}")
        pricing_id = await _pricing_id(db, agent, llm.active_model())
        task = Task(
            session_id=item.session_id,
            agent_id=item.agent_id,
            domain=agent.domain,
            task_type=agent.agent_type,
            input_payload=item.input_payload,
            priority=item.priority,
        )
        db.add(task)
        tasks.append(task)
        await db.flush()
        jobs.append((task.id, registry, pricing_id))
    await db.commit()
    for task in tasks:
        await db.refresh(task)
    background_tasks.add_task(execute_tasks_concurrently, jobs)
    return tasks


@router.get("/tasks/{task_id}", response_model=TaskDetailSchema)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    run = await db.scalar(select(AgentRun).where(AgentRun.task_id == task_id))
    data = TaskSchema.model_validate(task).model_dump()
    data["run"] = None if run is None else _run_dict(run)
    return data


@router.get("/tasks/{task_id}/status", response_model=TaskStatusSchema)
async def get_task_status(
    task_id: str, db: AsyncSession = Depends(get_db)
) -> TaskStatusSchema:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatusSchema(id=task.id, status=task.status)


@router.post("/tasks/{task_id}/retry", response_model=TaskSchema)
async def retry_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    registry: AgentRegistry = Depends(get_registry),
    llm: LLMClient = Depends(get_llm),
) -> Task:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    agent = await db.get(AgentDefinition, task.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    prior_run = await db.scalar(select(AgentRun).where(AgentRun.task_id == task_id))
    pricing_id = await _pricing_id(db, agent, llm.active_model())
    retry = Task(
        session_id=task.session_id,
        agent_id=task.agent_id,
        domain=task.domain,
        task_type=task.task_type,
        input_payload=task.input_payload,
        priority=task.priority,
    )
    db.add(retry)
    await db.commit()
    await db.refresh(retry)

    async def run_retry() -> None:
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as retry_db:
            retry_task_obj = await retry_db.get(Task, retry.id)
            if retry_task_obj is not None:
                await registry.get(retry_task_obj.agent_id).run(
                    retry_task_obj, pricing_id, retry_of=prior_run.id if prior_run else None
                )

    background_tasks.add_task(run_retry)
    return retry


def _run_dict(run: AgentRun) -> dict[str, Any]:
    return {key: value for key, value in run.__dict__.items() if not key.startswith("_")}

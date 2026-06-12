from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentops.task_queue import (
    execute_task as execute_task,
)
from app.agentops.task_queue import (
    execute_tasks_concurrently as execute_tasks_concurrently,
)
from app.agents.registry import AgentRegistry
from app.core.database import get_db
from app.llm.client import LLMClient
from app.models.agent_definition import AgentDefinition
from app.models.agent_run import AgentRun
from app.models.model_pricing import ModelPricing
from app.models.task import Task
from app.routers.deps import get_llm, get_registry
from app.schemas.agent_run import AgentRunSchema
from app.schemas.task import (
    TaskBatchRequest,
    TaskDetailSchema,
    TaskSchema,
    TaskStatusSchema,
    TaskSubmitRequest,
)

__author__ = "Sarala Biswal"

router = APIRouter()


async def _active_pricing(
    db: AsyncSession,
    provider: str,
    model_name: str,
) -> ModelPricing | None:
    rows = list(
        await db.scalars(
            select(ModelPricing).where(
                ModelPricing.provider == provider,
                ModelPricing.model_name == model_name,
                ModelPricing.effective_to.is_(None),
            )
        )
    )
    if len(rows) > 1:
        raise HTTPException(
            status_code=400,
            detail=f"Multiple active pricing rows for {provider}:{model_name}",
        )
    return rows[0] if rows else None


async def _pricing_id(
    db: AsyncSession,
    agent: AgentDefinition,
    provider: str,
    model_name: str,
) -> str:
    """Resolve pricing for the active model, falling back to the seeded agent default."""
    pricing = await _active_pricing(db, provider, model_name)
    if pricing is None:
        pricing = await _active_pricing(db, provider, agent.model_default)
    if pricing is None:
        raise HTTPException(status_code=400, detail=f"No pricing for {provider}:{model_name}")
    return str(pricing.id)


@router.post("/tasks", response_model=TaskSchema)
async def submit_task(
    payload: TaskSubmitRequest,
    db: AsyncSession = Depends(get_db),
    registry: AgentRegistry = Depends(get_registry),
    llm: LLMClient = Depends(get_llm),
) -> Task:
    """Submit one agent task and schedule it for background execution."""
    agent = await db.get(AgentDefinition, payload.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    pricing_id = await _pricing_id(db, agent, llm.active_provider(), llm.active_model())
    task = Task(
        session_id=payload.session_id,
        agent_id=payload.agent_id,
        domain=agent.domain,
        task_type=agent.agent_type,
        input_payload=payload.input_payload,
        priority=payload.priority,
        model_pricing_id=pricing_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.post("/tasks/batch", response_model=list[TaskSchema])
async def submit_batch(
    payload: TaskBatchRequest,
    db: AsyncSession = Depends(get_db),
    registry: AgentRegistry = Depends(get_registry),
    llm: LLMClient = Depends(get_llm),
) -> list[Task]:
    """Submit a domain/platform run as multiple tasks and start them concurrently."""
    tasks: list[Task] = []
    for item in payload.tasks:
        agent = await db.get(AgentDefinition, item.agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail=f"Agent not found: {item.agent_id}")
        pricing_id = await _pricing_id(db, agent, llm.active_provider(), llm.active_model())
        task = Task(
            session_id=item.session_id,
            agent_id=item.agent_id,
            domain=agent.domain,
            task_type=agent.agent_type,
            input_payload=item.input_payload,
            priority=item.priority,
            model_pricing_id=pricing_id,
        )
        db.add(task)
        tasks.append(task)
        await db.flush()
    await db.commit()
    for task in tasks:
        await db.refresh(task)
    return tasks


@router.get("/tasks/{task_id}", response_model=TaskDetailSchema)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    run = await db.scalar(select(AgentRun).where(AgentRun.task_id == task_id))
    data = TaskSchema.model_validate(task).model_dump()
    data["run"] = None if run is None else AgentRunSchema.model_validate(run).model_dump()
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
    pricing_id = await _pricing_id(db, agent, llm.active_provider(), llm.active_model())
    retry = Task(
        session_id=task.session_id,
        agent_id=task.agent_id,
        domain=task.domain,
        task_type=task.task_type,
        input_payload=task.input_payload,
        priority=task.priority,
        model_pricing_id=pricing_id,
        retry_of_run_id=prior_run.id if prior_run else None,
    )
    db.add(retry)
    await db.commit()
    await db.refresh(retry)
    return retry

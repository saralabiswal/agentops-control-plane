from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.core.enums import TaskPriority


class TaskSubmitRequest(BaseModel):
    agent_id: str
    session_id: str
    input_payload: dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL


class TaskBatchRequest(BaseModel):
    tasks: list[TaskSubmitRequest]


class TaskSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    agent_id: str
    domain: str
    task_type: str
    input_payload: dict[str, Any]
    priority: str
    status: str
    submitted_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class TaskStatusSchema(BaseModel):
    id: str
    status: str


class TaskDetailSchema(TaskSchema):
    run: dict[str, Any] | None = None

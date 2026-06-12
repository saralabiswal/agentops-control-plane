from enum import StrEnum


class RunType(StrEnum):
    SINGLE_SHOT = "SINGLE_SHOT"
    WORKFLOW_PARENT = "WORKFLOW_PARENT"
    WORKFLOW_NODE = "WORKFLOW_NODE"


class RunStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class QualityStatus(StrEnum):
    PENDING = "PENDING"
    SCORED = "SCORED"
    FAILED = "FAILED"


class Domain(StrEnum):
    PROJECT_DELIVERY = "PROJECT_DELIVERY"
    REVENUE_OPS = "REVENUE_OPS"
    PLATFORM = "PLATFORM"


class AgentExecutionMode(StrEnum):
    SINGLE_SHOT = "SINGLE_SHOT"
    LANGGRAPH_WORKFLOW = "LANGGRAPH_WORKFLOW"


class TaskStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class TaskPriority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"

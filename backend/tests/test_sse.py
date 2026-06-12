from datetime import UTC, datetime

import pytest

from app.agentops.context import RunContext
from app.agentops.sse_emitter import SSEEmitter, format_sse_message
from app.core.enums import RunType


@pytest.mark.asyncio
async def test_sse_emitter_publishes_to_subscriber() -> None:
    emitter = SSEEmitter()
    queue = emitter.subscribe("sub")
    ctx = RunContext(
        run_id="run-1",
        task_id="task-1",
        agent_id="agent-sprint-risk",
        session_id="session-1",
        started_at=datetime.now(UTC),
        model_used="llama3.2:3b",
        model_pricing_id="price-ollama-llama32-3b",
        run_type=RunType.SINGLE_SHOT,
    )

    await emitter.emit_run_started(ctx)

    message = await queue.get()
    event = format_sse_message(message)
    assert message.payload["event"] == "run_started"
    assert message.payload["run_id"] == "run-1"
    assert "id: 1" in event
    assert "data:" in event
    assert "run_started" in event


def test_sse_emitter_unsubscribes() -> None:
    emitter = SSEEmitter()
    emitter.subscribe("sub")
    emitter.unsubscribe("sub")

    assert "sub" not in emitter._subscribers


@pytest.mark.asyncio
async def test_sse_emitter_removes_full_subscriber_queue() -> None:
    emitter = SSEEmitter()
    queue = emitter.subscribe("stalled-sub")
    ctx = RunContext(
        run_id="run-1",
        task_id="task-1",
        agent_id="agent-sprint-risk",
        session_id="session-1",
        started_at=datetime.now(UTC),
        model_used="llama3.2:3b",
        model_pricing_id="price-ollama-llama32-3b",
        run_type=RunType.SINGLE_SHOT,
    )
    for _ in range(queue.maxsize):
        queue.put_nowait("stale")

    await emitter.emit_run_completed(ctx)

    assert "stalled-sub" not in emitter._subscribers

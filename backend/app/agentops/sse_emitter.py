import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.agentops.context import RunContext


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    return str(value)


class SSEEmitter:
    def __init__(self) -> None:
        self._subscribers: dict[str, asyncio.Queue[SSEMessage]] = {}
        self._event_id = 0

    def subscribe(self, subscriber_id: str) -> asyncio.Queue["SSEMessage"]:
        queue: asyncio.Queue[SSEMessage] = asyncio.Queue(maxsize=100)
        self._subscribers[subscriber_id] = queue
        return queue

    def unsubscribe(self, subscriber_id: str) -> None:
        self._subscribers.pop(subscriber_id, None)

    async def emit_run_started(self, ctx: RunContext) -> None:
        await self._publish("run_started", ctx)

    async def emit_run_completed(self, ctx: RunContext) -> None:
        await self._publish("run_completed", ctx)

    async def emit_quality_scored(self, ctx: RunContext) -> None:
        await self._publish("quality_scored", ctx)

    async def _publish(self, event: str, ctx: RunContext) -> None:
        payload = {"event": event, **asdict(ctx)}
        self._event_id += 1
        message = SSEMessage(event_id=str(self._event_id), payload=payload)
        dead: list[str] = []
        for subscriber_id, queue in self._subscribers.items():
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                dead.append(subscriber_id)
        for subscriber_id in dead:
            self.unsubscribe(subscriber_id)


@dataclass(frozen=True)
class SSEMessage:
    event_id: str
    payload: dict[str, Any]


def format_sse_message(message: SSEMessage) -> str:
    data = json.dumps(message.payload, default=_json_default)
    return f"id: {message.event_id}\ndata: {data}\n\n"

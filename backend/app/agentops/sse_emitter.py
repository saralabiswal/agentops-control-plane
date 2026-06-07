import asyncio
import json
from dataclasses import asdict
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
        self._subscribers: dict[str, asyncio.Queue[str]] = {}

    def subscribe(self, subscriber_id: str) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
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
        data = f"data: {json.dumps(payload, default=_json_default)}\n\n"
        dead: list[str] = []
        for subscriber_id, queue in self._subscribers.items():
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                dead.append(subscriber_id)
        for subscriber_id in dead:
            self.unsubscribe(subscriber_id)


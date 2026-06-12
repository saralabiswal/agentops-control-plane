import asyncio
from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.agentops.sse_emitter import format_sse_message

router = APIRouter()


@router.get("/stream/runs")
async def stream_runs(request: Request) -> StreamingResponse:
    return _stream(request)


@router.get("/stream/session/{session_id}")
async def stream_session(session_id: str, request: Request) -> StreamingResponse:
    return _stream(request, session_id=session_id)


@router.get("/stream/metrics")
async def stream_metrics(request: Request) -> StreamingResponse:
    return _stream(request)


def _stream(request: Request, session_id: str | None = None) -> StreamingResponse:
    subscriber_id = str(uuid4())
    queue = request.app.state.sse.subscribe(subscriber_id)

    async def event_generator() -> AsyncIterator[str]:
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=15.0)
                    if session_id is None or message.payload.get("session_id") == session_id:
                        yield format_sse_message(message)
                except TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            request.app.state.sse.unsubscribe(subscriber_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

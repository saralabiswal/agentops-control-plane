import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agentops.cost_calculator import CostCalculator
from app.agentops.manager import AgentOpsManager, recover_stale_runs
from app.agentops.quality_queue import QualityQueue
from app.agentops.sse_emitter import SSEEmitter
from app.agents.platform.quality_judge import QualityJudgeAgent
from app.agents.registry import AgentRegistry
from app.core.config import Settings
from app.core.database import engine
from app.llm.client import LLMClient
from app.models import Base
from app.routers import catalog, metrics, outcomes, runs, sessions, settings, stream, tasks
from app.seed.seed import run_seed

__author__ = "Sarala Biswal"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create the runtime graph shared by all API routers for this process."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await run_seed()

    settings = Settings()
    llm = LLMClient(settings)
    sse = SSEEmitter()
    quality_q = QualityQueue(sse)
    agentops = AgentOpsManager(sse, quality_q, CostCalculator())
    judge = QualityJudgeAgent(llm)
    registry = AgentRegistry(llm, agentops)

    app.state.settings = settings
    app.state.llm = llm
    app.state.sse = sse
    app.state.agentops = agentops
    app.state.registry = registry

    quality_worker = asyncio.create_task(quality_q.worker(judge))
    await recover_stale_runs()
    yield
    quality_worker.cancel()


app = FastAPI(title="AgentOps Control Plane", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(runs.router, prefix="/api/v1")
app.include_router(outcomes.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")
app.include_router(stream.router, prefix="/api/v1")

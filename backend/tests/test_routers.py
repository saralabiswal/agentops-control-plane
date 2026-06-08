import asyncio
import time

import pytest

from app.core.database import AsyncSessionLocal
from app.models.agent_run import AgentRun
from app.models.business_outcome import BusinessOutcome
from app.models.model_pricing import ModelPricing
from app.models.task import Task
from app.routers import tasks as task_router


def test_catalog_and_session_endpoints(client) -> None:
    agents = client.get("/api/v1/agents")
    assert agents.status_code == 200
    assert len(agents.json()) == 8

    created = client.post("/api/v1/sessions", json={"name": "Router Test"})
    assert created.status_code == 200
    session_id = created.json()["id"]

    listed = client.get("/api/v1/sessions")
    assert listed.status_code == 200
    assert any(session["id"] == session_id for session in listed.json())

    detail = client.get(f"/api/v1/sessions/{session_id}")
    assert detail.status_code == 200

    agent = agents.json()[0]
    assert client.get(f"/api/v1/agents/{agent['id']}").status_code == 200
    assert client.get("/api/v1/pricing").status_code == 200
    assert client.post(f"/api/v1/sessions/{session_id}/close").status_code == 200


def test_runtime_settings_endpoints(client) -> None:
    listed = client.get("/api/v1/settings/runtime")
    assert listed.status_code == 200
    body = listed.json()
    assert body["active_provider"] == "ollama"
    assert body["active_model"] == "llama3.2:3b"
    providers = {item["provider"]: item for item in body["providers"]}
    assert set(providers) == {"ollama", "groq", "gemini"}
    assert "llama3.2:latest" in providers["ollama"]["models"]

    updated = client.patch(
        "/api/v1/settings/runtime",
        json={"active_provider": "ollama", "model_name": "llama3.2:latest"},
    )
    assert updated.status_code == 200
    assert updated.json()["active_model"] == "llama3.2:latest"
    assert client.app.state.settings.ollama_model == "llama3.2:latest"

    client.app.state.settings.groq_api_key = ""
    rejected = client.patch(
        "/api/v1/settings/runtime",
        json={"active_provider": "groq", "model_name": "llama-3.3-70b-versatile"},
    )
    assert rejected.status_code == 400
    assert "Groq is not configured" in rejected.json()["detail"]


def test_metrics_and_outcome_summary_endpoints(client) -> None:
    assert client.get("/api/v1/metrics/cost").status_code == 200
    assert client.get("/api/v1/metrics/quality").status_code == 200
    assert client.get("/api/v1/metrics/latency").status_code == 200
    assert client.get("/api/v1/metrics/throughput").status_code == 200
    assert client.get("/api/v1/outcomes/summary").status_code == 200


class NoopAgent:
    async def run(self, task: Task, model_pricing_id: str, retry_of: str | None = None) -> None:
        return None


class NoopRegistry:
    def get(self, agent_id: str) -> NoopAgent:
        return NoopAgent()


def test_task_endpoints_return_expected_schema(client) -> None:
    client.app.state.registry = NoopRegistry()
    session_id = client.post("/api/v1/sessions", json={"name": "Task Router"}).json()["id"]
    payload = {
        "agent_id": "agent-sprint-risk",
        "session_id": session_id,
        "input_payload": {
            "sprint_name": "Orion",
            "team_size": 4,
            "days_remaining": 5,
            "total_tasks": 10,
            "completed_tasks": 4,
            "velocity_history": [8, 9, 7],
        },
        "priority": "HIGH",
    }

    created = client.post("/api/v1/tasks", json=payload)
    assert created.status_code == 200
    task_id = created.json()["id"]
    assert client.get(f"/api/v1/tasks/{task_id}").status_code == 200
    assert client.get(f"/api/v1/tasks/{task_id}/status").json()["id"] == task_id
    assert client.post(f"/api/v1/tasks/{task_id}/retry").status_code == 200

    batch = client.post("/api/v1/tasks/batch", json={"tasks": [payload, payload]})
    assert batch.status_code == 200
    assert len(batch.json()) == 2


@pytest.mark.asyncio
async def test_run_and_outcome_endpoints_return_expected_schema(client) -> None:
    session_id = client.post("/api/v1/sessions", json={"name": "Run Router"}).json()["id"]
    async with AsyncSessionLocal() as db:
        pricing = await db.get(ModelPricing, "price-ollama-llama32-3b")
        assert pricing is not None
        task = Task(
            session_id=session_id,
            agent_id="agent-sprint-risk",
            domain="PROJECT_DELIVERY",
            task_type="sprint_risk_assessment",
            input_payload={},
        )
        db.add(task)
        await db.flush()
        original = AgentRun(
            id="router-run-original",
            task_id=task.id,
            agent_id="agent-sprint-risk",
            model_pricing_id=pricing.id,
            run_type="SINGLE_SHOT",
            model_used="llama3.2:3b",
            status="COMPLETE",
            raw_prompt="prompt",
            raw_response="{}",
            output_payload={"risk_score": 0.5},
            quality_score=0.9,
            quality_dimensions={"reasoning_trace": "ok"},
        )
        retry = AgentRun(
            id="router-run-retry",
            task_id=task.id,
            agent_id="agent-sprint-risk",
            model_pricing_id=pricing.id,
            run_type="SINGLE_SHOT",
            retry_of=original.id,
            model_used="llama3.2:3b",
            status="COMPLETE",
            raw_prompt="prompt",
            raw_response="{}",
            output_payload={},
        )
        outcome = BusinessOutcome(
            task_id=task.id,
            agent_run_id=original.id,
            domain="PROJECT_DELIVERY",
            outcome_type="risk_mitigation",
            metric_name="delivery_risk_mitigated_usd",
            metric_value=1000,
            metric_unit="usd",
            financial_impact_usd=1000,
            confidence_score=0.9,
        )
        db.add_all([original, retry, outcome])
        await db.commit()

    assert client.get("/api/v1/runs").status_code == 200
    assert client.get("/api/v1/runs/router-run-original").status_code == 200
    assert client.get("/api/v1/runs/router-run-original/quality").status_code == 200
    assert client.get("/api/v1/runs/router-run-original/retries").status_code == 200
    assert client.get(f"/api/v1/outcomes/session/{session_id}").status_code == 200
    assert client.get("/api/v1/outcomes/router-run-original").status_code == 200


@pytest.mark.asyncio
async def test_batch_executor_runs_tasks_concurrently(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_execute_task(task_id: str, registry, model_pricing_id: str) -> None:
        calls.append(task_id)
        await asyncio.sleep(0.05)

    monkeypatch.setattr(task_router, "execute_task", fake_execute_task)
    start = time.perf_counter()
    await task_router.execute_tasks_concurrently(
        [("a", object(), "p"), ("b", object(), "p"), ("c", object(), "p")]
    )
    elapsed = time.perf_counter() - start

    assert set(calls) == {"a", "b", "c"}
    assert elapsed < 0.12

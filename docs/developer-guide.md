# AgentOps Control Plane Developer Guide

**Author:** Sarala Biswal

This guide explains how the code is organized, how a run flows through the
platform, and where to make changes when extending the app.

## Architecture Diagrams

The project keeps rendered architecture assets under `docs/assets/`.

![AgentOps Control Plane system architecture](assets/architecture.png)

**System architecture** — end-to-end request, durable task execution,
governance, provider, data, quality, trace access, and outcome flow.

![AgentOps Control Plane logical architecture](assets/logical-architecture.png)

**Logical architecture** — ownership boundaries across experience, API,
durable queue, orchestration, control plane, observability, provider, data, and
operations layers.

![AgentOps Control Plane physical architecture](assets/physical-architecture.png)

**Physical architecture** — local development and Docker runtime topology,
ports, service boundaries, in-process workers, database, migrations, provider
clients, and validation commands.

## System Flow

The application is split into experience, API, durable queue, orchestration,
control-plane, provider, data, and observability layers. A normal run flows
through the system like this:

1. The React shell in `frontend/src/App.tsx` selects a run scope: complete
   platform, Project Management, Revenue Management, or a single agent.
2. The UI creates or reuses an active session through `useSession()` and submits
   one or more tasks through `api.tasks.batch()`.
3. `backend/app/routers/tasks.py` validates each agent, resolves provider/model
   pricing, and writes durable `QUEUED` `Task` rows. The API request does not
   directly execute the agent.
4. `backend/app/agentops/task_queue.py` claims queued tasks through
   `TaskWorker`, preserves retry/pricing metadata, and recovers interrupted
   claims on startup.
5. `backend/app/agents/registry.py` maps persisted agent IDs to executable agent
   classes.
6. Each agent runs inside `AgentOpsManager.run_context()` in
   `backend/app/agentops/manager.py`. This is the control-plane boundary that
   records run status, prompt/response payloads, token counts, cost, metrics,
   outcomes, and SSE events.
7. `backend/app/llm/client.py` resolves the active provider and model. Ollama is
   the default local provider; Groq and Gemini adapters are available when
   configured. Provider adapters reuse async HTTP clients, retry transient
   failures, and close during app shutdown.
8. Completed runs write business impact through
   `backend/app/outcomes/calculator.py` and enqueue quality scoring through
   `QualityQueue`. Quality scoring persists `PENDING`, `SCORED`, or `FAILED`
   status with attempts and errors.
9. The frontend refreshes run state through structured SSE and polling, then
   presents business outcomes, bounded run summaries, cost, quality, and run
   progress. Raw prompt/response traces are available through the protected
   `/runs/{run_id}/trace` endpoint.

## Important Files

| Area | File | Purpose |
|---|---|---|
| App shell | `frontend/src/App.tsx` | Persona views, run scopes, scenario inputs, run progress |
| API client | `frontend/src/api/client.ts` | Browser-to-FastAPI request wrapper |
| API entry | `backend/app/main.py` | FastAPI app, migration-gated startup, shared runtime services |
| Task API | `backend/app/routers/tasks.py` | Task submission, batch creation, retry records |
| Task worker | `backend/app/agentops/task_queue.py` | Durable task claiming, execution, recovery |
| Agent catalog | `backend/app/agents/registry.py` | Maps agent IDs to implementations |
| Run boundary | `backend/app/agentops/manager.py` | Trace, metrics, cost, outcomes, SSE, quality enqueue |
| Stream layer | `backend/app/routers/stream.py` | Structured SSE serialization and session filtering |
| Trace auth | `backend/app/routers/deps.py` | Optional API-key guard for raw trace access |
| Provider layer | `backend/app/llm/client.py` | Active provider/model routing and provider shutdown |
| Costing | `backend/app/agentops/cost_calculator.py` | Token-to-cost calculation from pricing rows |
| Outcomes | `backend/app/outcomes/calculator.py` | Business value formulas by agent |
| Pricing seed | `backend/app/seed/pricing.py` | Input/output model prices, including elevated local demo pricing |
| Migrations | `backend/app/core/migrations.py` | Alembic head validation at startup |
| Postgres smoke | `backend/app/core/postgres_validation.py` | Optional Postgres migration validation command |

## Run Modes

- **Complete Platform:** runs all Project Management and Revenue Management
  agents.
- **Project Management:** runs sprint risk, resource allocation, delivery
  forecast, and the ProjectPlanning workflow.
- **Revenue Management:** runs renewal risk, churn signal, and pipeline forecast.
- **Single Agent:** validates one selected agent against the active domain
  scenario.

The ProjectPlanning workflow is the only multi-node agent. The UI surfaces its
user input directly in the Business View run console, then the backend executes
the workflow from decomposition through synthesis.

## Backend Runtime

`backend/app/main.py` builds the runtime graph during FastAPI startup:

- validates the database is at the current Alembic head
- seeds agents and model pricing
- creates `LLMClient`
- creates `SSEEmitter`
- creates `QualityQueue`
- creates `AgentOpsManager`
- creates `AgentRegistry`
- creates and starts `TaskWorker`
- starts the async quality worker
- recovers stale `RUNNING` runs
- recovers interrupted task claims

Startup does not call `Base.metadata.create_all()`. Run `make migrate` before
serving the app. On shutdown, the app stops the task worker, cancels the quality
worker, closes provider HTTP clients, and disposes the SQLAlchemy engine.

Routers use these app-state services through dependency helpers in
`backend/app/routers/deps.py`.

## AgentOps Contract

Every agent runs inside `AgentOpsManager.run_context()`. Agents only populate:

- `raw_prompt`
- `prompt_tokens`
- `completion_tokens`
- `raw_response`
- `output_payload`

AgentOps owns:

- `AgentRun` creation and update
- task status transitions
- token totals
- latency
- model cost
- time-series metrics
- business outcome writes
- SSE events
- async quality enqueueing

Task queue ownership sits just outside this contract. Routers persist task rows
with `model_pricing_id` and `retry_of_run_id`; `TaskWorker` claims those rows
and then invokes the same AgentOps contract as every other execution path.

This keeps agent implementations focused on domain reasoning while the platform
owns observability and governance.

## Pricing And Cost

Model pricing is seeded from `backend/app/seed/pricing.py`.

Local Ollama demo runs intentionally use elevated prices so cost is visible in
the UI:

- input tokens: `$0.15 / 1K`
- output tokens: `$0.60 / 1K`

Task submission resolves active pricing by provider and model. If more than one
active row exists for the same provider/model, submission fails rather than
guessing. When seeded pricing changes after a row has been referenced by an
`AgentRun`, the existing row is expired and a new active row is inserted, so
historical cost remains auditable.

`CostCalculator.calculate()` uses:

```text
(prompt_tokens / 1000) * input_cost_per_1k
+ (completion_tokens / 1000) * output_cost_per_1k
```

The Business View token cost KPI sums billable top-level runs only:

- `SINGLE_SHOT`
- `WORKFLOW_PARENT`

Workflow child node runs remain visible in traces but are not double-counted in
the top-level business KPI.

## Trace Access

Default run list/detail responses are summaries and do not include
`raw_prompt` or `raw_response`. Privileged trace detail is exposed at:

```text
GET /api/v1/runs/{run_id}/trace
```

If `AGENTOPS_TRACE_API_KEY` is set, callers must send either:

```text
Authorization: Bearer <key>
```

or:

```text
X-API-Key: <key>
```

## Frontend State Flow

`frontend/src/App.tsx` owns the main application state:

- active view
- business or technical persona
- run scope
- selected agent
- current session
- active run progress
- runs and outcomes
- pricing records
- rotating demo scenarios
- ProjectPlanning input

The app refreshes evidence through two paths:

- structured SSE events from `/api/v1/stream/runs`
- polling while an active run is in flight

SSE messages are structured internally and serialized only at the stream edge.
Session-specific streams filter by payload `session_id`, not by searching JSON
strings.

## Adding A New Agent

1. Add the agent definition in `backend/app/seed/agents.py`.
2. Implement the agent class under the right domain folder in `backend/app/agents/`.
3. Register the class in `backend/app/agents/registry.py`.
4. Add or update outcome logic in `backend/app/outcomes/calculator.py`.
5. Add a scenario payload in `frontend/src/App.tsx`.
6. Add tests for parsing, output contract, cost, and outcome behavior.

## Local Development

```bash
cd backend
make install
make migrate
make seed
make dev
```

The frontend runs on `http://localhost:5173` and proxies API calls to
`http://localhost:8000`.

Useful checks:

```bash
cd backend
make test
make lint
make typecheck
make postgres-migrate-smoke  # requires AGENTOPS_POSTGRES_TEST_DATABASE_URL

cd ../frontend
npm run build
```

# AgentOps Control Plane Developer Guide

**Author:** Sarala Biswal

This guide explains how the code is organized, how a run flows through the
platform, and where to make changes when extending the app.

## System Flow

The application is split into experience, API, orchestration, provider, and
observability layers. A normal run flows through the system like this:

1. The React shell in `frontend/src/App.tsx` selects a run scope: complete
   platform, Project Management, Revenue Management, or a single agent.
2. The UI creates or reuses an active session through `useSession()` and submits
   one or more tasks through `api.tasks.batch()`.
3. `backend/app/routers/tasks.py` validates each agent, resolves model pricing,
   writes queued `Task` rows, and schedules background execution.
4. `backend/app/agents/registry.py` maps persisted agent IDs to executable agent
   classes.
5. Each agent runs inside `AgentOpsManager.run_context()` in
   `backend/app/agentops/manager.py`. This is the control-plane boundary that
   records run status, prompt/response payloads, token counts, cost, metrics,
   outcomes, and SSE events.
6. `backend/app/llm/client.py` resolves the active provider and model. Ollama is
   the default local provider; Groq and Gemini adapters are available when
   configured.
7. Completed runs write business impact through
   `backend/app/outcomes/calculator.py` and enqueue quality scoring through
   `QualityQueue`.
8. The frontend refreshes run state through SSE and polling, then presents
   business outcomes, trace evidence, cost, quality, and run progress.

## Important Files

| Area | File | Purpose |
|---|---|---|
| App shell | `frontend/src/App.tsx` | Persona views, run scopes, scenario inputs, run progress |
| API client | `frontend/src/api/client.ts` | Browser-to-FastAPI request wrapper |
| API entry | `backend/app/main.py` | FastAPI app, startup seed, shared runtime services |
| Task API | `backend/app/routers/tasks.py` | Task submission, batch run scheduling, retry |
| Agent catalog | `backend/app/agents/registry.py` | Maps agent IDs to implementations |
| Run boundary | `backend/app/agentops/manager.py` | Trace, metrics, cost, outcomes, SSE, quality enqueue |
| Provider layer | `backend/app/llm/client.py` | Active provider/model routing |
| Costing | `backend/app/agentops/cost_calculator.py` | Token-to-cost calculation from pricing rows |
| Outcomes | `backend/app/outcomes/calculator.py` | Business value formulas by agent |
| Pricing seed | `backend/app/seed/pricing.py` | Input/output model prices, including elevated local demo pricing |

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

- creates tables
- seeds agents and model pricing
- creates `LLMClient`
- creates `SSEEmitter`
- creates `QualityQueue`
- creates `AgentOpsManager`
- creates `AgentRegistry`
- starts the async quality worker
- recovers stale `RUNNING` records

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

This keeps agent implementations focused on domain reasoning while the platform
owns observability and governance.

## Pricing And Cost

Model pricing is seeded from `backend/app/seed/pricing.py`.

Local Ollama demo runs intentionally use elevated prices so cost is visible in
the UI:

- input tokens: `$0.15 / 1K`
- output tokens: `$0.60 / 1K`

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

- SSE events from `/api/v1/stream/runs`
- polling while an active run is in flight

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

cd ../frontend
npm run build
```

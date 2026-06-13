# AgentOps Control Plane

**Author:** Sarala Biswal

> "An agent that can't be traced, costed, or tied to an outcome isn't a production system. It's a demo with uptime.
> The model is the easy part. The management layer — who owns it, what it spent, what it changed — is what separates an experiment from infrastructure."

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C1C1C?style=flat&logo=langchain&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat&logo=typescript&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=flat&logo=ollama&logoColor=white)
![MLflow](https://img.shields.io/badge/MLflow-0194E2?style=flat&logo=mlflow&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=flat&logo=tailwindcss&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat&logo=vite&logoColor=white)

---

## The Business Problem

Enterprise teams deploying AI agents hit the same wall after the demo: the agents run,
outputs are produced, and the organization has no coherent answer to the questions that
determine whether this is a managed production system or an expensive experiment.

| Question | Why it matters |
|---|---|
| Which agents ran, when, and did they succeed or fail? | Without this, you cannot own the reliability SLA |
| What did each run cost, attributed to the decision it was making? | Without this, you cannot defend the budget |
| Is output quality improving or degrading across runs? | Without this, you cannot detect silent regression |
| What financial outcome did this agent decision actually drive? | Without this, you cannot justify the investment |

The gap is not the model. The gap is the management layer — observability, cost
attribution, quality measurement, and financial accountability — that was never built
because teams moved from prototype to deployment without building the infrastructure
that production requires.

**AgentOps Control Plane is that management layer.**

It traces every agent run, attributes every dollar of compute cost to the decision that
triggered it, scores every output asynchronously, and connects agent decisions to
financial outcomes expressed in the language finance already uses: risk mitigated, ARR
protected, pipeline gap recovered.

---

## How It Solves the Problem

The platform is organized around one design decision: the control plane is the
foundation. Agents are plugged into it. Most teams do this in reverse — agents run first,
observability gets bolted on later. That inversion is why production AI is hard to own.

### 1. Enforced observability, not optional logging

Agents execute inside `AgentOpsManager.run_context()`. This is the only path agents have
to the database. Agents populate exactly 5 fields — prompt, tokens, response, output,
and a validated payload. AgentOps owns everything else: run record creation, cost
computation, metrics emission, quality scoring, and outcome attachment. A run is COMPLETE
or FAILED. There is no third state.

### 2. Financial accountability as a first-class output

Every agent produces a dollar-value business outcome, persisted to a `BusinessOutcome`
record linked directly to the `AgentRun` that produced it. Outcomes are expressed in
formulas tied to real business metrics — ARR at risk, delivery cost exposure, quota gap
recovery. A complete platform run produces a cross-domain outcome ledger.

A representative run across all agents:

| Agent | Outcome metric | Value | Confidence |
|---|---|---|---|
| SprintRiskAgent | `delivery_risk_mitigated_usd` | $15,000 | 0.70 |
| ProjectPlanningAgent | `pipeline_confidence_gap_usd` | $120,000 | 0.82 |
| RenewalRiskAgent | `renewal_pipeline_protected_usd` | $280,000 | 0.76 |
| PipelineForecastAgent | `recoverable_quota_gap_usd` | $310,000 | 0.84 |

### 3. Cost locked at write time

Compute cost is computed once at execution and locked to the run record. Pricing changes
do not retroactively alter historical cost. What a run cost is a fact, not a
recalculation.

### 4. Async quality scoring without blocking execution

A `QualityJudgeAgent` scores every completed run across 4 dimensions — relevance,
faithfulness, completeness, and actionability — without blocking task execution. Quality
status (`PENDING` → `SCORED` or `FAILED`) is persisted with error detail. Silent quality
degradation across runs is detectable.

### 5. Dual-persona visibility into every run

The same run data drives two views. The business view leads with financial outcome and
risk narrative. The technical view leads with the run ledger, trace payload, token
counts, and — for LangGraph workflow agents — the node execution graph. A guided demo
mode walks through outcome → domain breakdown → evidence → quality scores → trace
replay.

---

## Architecture

![AgentOps Control Plane Architecture](docs/architecture/agentops-control-plane-architecture.svg)


Each layer has a single responsibility. Agents do domain reasoning. The control plane
owns execution state, cost, quality, trace exposure, and outcome accounting.

| Layer | What it owns |
|---|---|
| **Experience** | Two persona-optimized views from the same run data. Business view: financial outcome and risk narrative. Technical view: run ledger, trace payload, token counts, LangGraph node graph. |
| **API** | FastAPI with typed resource routers for Tasks, Runs, Metrics, and Stream. Raw trace data is omitted from default run responses; `/runs/{run_id}/trace` is gated by `AGENTOPS_TRACE_API_KEY`. |
| **Durable queue** | The `tasks` table is the queue. Submitted work is persisted as `QUEUED` with pricing id, retry lineage, attempt count, and claim recovery metadata. `TaskWorker` requeues interrupted claims on startup. |
| **Orchestration** | Agent Registry maps agent id to implementation. Single-shot and LangGraph workflow agents share one dispatch path. Retry chains preserve lineage via `retry_of` — a first-class data relationship, not a log entry. |
| **Control plane** | `AgentOpsManager.run_context()` is the enforcement boundary. Agents populate their 5 fields. AgentOps writes everything else. |
| **Provider** | `LLMClient.complete()` is the only interface to model providers. Ollama, Groq, and Gemini each have an adapter behind it. Provider failures are recorded on `AgentRun` — never silent. |
| **Data/migration** | Alembic owns schema changes. Startup validates migration head and does not create tables. SQLite is the local default; optional Postgres smoke validation via `make postgres-migrate-smoke`. |
| **Observability** | Structured SSE messages serialized with event IDs. Quality scoring records `PENDING`, `SCORED`, or `FAILED` with attempt count and error detail. |

---

## The AgentOps Contract

The boundary that makes observability enforced rather than aspirational:

**Agents populate exactly 5 fields:**

| Field | Description |
|---|---|
| `raw_prompt` | Generated prompt sent to the model |
| `prompt_tokens` | Normalized input token count |
| `completion_tokens` | Normalized output token count |
| `raw_response` | Provider output text before parsing |
| `output_payload` | Validated structured JSON consumed by outcomes |

**AgentOps owns everything else:**

| Responsibility | Enforcement |
|---|---|
| RUNNING record written before agent execution | In `run_context()` entry |
| COMPLETE or FAILED written in `finally` | Guaranteed — no abandoned runs |
| `cost_usd` computed from locked pricing | At write time — never recomputed |
| Metrics and SSE emitted from one layer | Not from agent code |
| Quality scoring and outcome attachment | After successful execution only |

Agents do not write to the database. Agents do not manage their own lifecycle.

---

## Execution Flow

Every agent run — single-shot or multi-node workflow — follows this governed path:

```
1  Business request    Work enters a scoped session (Project Management or Revenue Management)
2  Task record         FastAPI creates a durable QUEUED task with locked pricing metadata
3  Task claim          TaskWorker claims queued work and dispatches through AgentRegistry
4  Agent execution     Agent runs inside run_context() — single-shot or LangGraph workflow
5  Provider call       LLMClient.complete() normalizes Ollama / Groq / Gemini response
6  AgentOps trace      Prompt, tokens, cost, status, response → AgentRun (locked at write time)
7  Outcomes            Completed run maps to risk reduction, ARR protected, or quota recovery
8  Quality queue       Async judge scores 4 dimensions and persists quality status/error
9  Stream/update       Structured SSE event updates the UI; summary APIs remain bounded
```

---

## Agents and Business Outcome Formulas

| Agent | Domain | Type | Business Outcome Formula |
|---|---|---|---|
| SprintRiskAgent | Project Management | Single shot | `risk_score × delay_cost_per_week_usd` |
| ResourceAllocationAgent | Project Management | Single shot | `tasks × avg_task_hours × efficiency_gain × hourly_rate` |
| DeliveryForecastAgent | Project Management | Single shot | `committed_revenue × (1 − confidence_score)` |
| ProjectPlanningAgent | Project Management | LangGraph workflow | `committed_revenue × (1 − confidence_score)` |
| RenewalRiskAgent | Revenue Management | Single shot | `account_arr × risk_score × historical_save_rate` |
| ChurnSignalAgent | Revenue Management | Single shot | `account_arr × churn_probability × early_intervention_value` |
| PipelineForecastAgent | Revenue Management | Single shot | `recoverable_gap_usd` |
| QualityJudgeAgent | Platform control | Async judge | Scores: relevance · faithfulness · completeness · actionability |

Every formula produces a dollar-value output persisted to `BusinessOutcome` and linked
to the `AgentRun` that produced it.

---

## ProjectPlanningAgent: LangGraph Workflow

`ProjectPlanningAgent` accepts a natural language project request and executes a 5-node
LangGraph graph. Each node produces a separate `AgentRun` record linked to the parent
via `parent_run_id`. Node failures are persisted individually. Downstream nodes do not
execute after a failed dependency.

```
node 1 — Decompose    Epics, stories, critical path, story points            612 tokens
node 2 — Capacity     Load, availability, skill gaps, capacity risk           488 tokens
node 3 — Risk         Delivery risk register with likelihood and mitigation   531 tokens
node 4 — Assign       Stories mapped to engineers by skill, load, risk        459 tokens
node 5 — Synthesize   Executive summary, confidence score, revenue exposure   850 tokens
```

The parent run is COMPLETE only when all 5 nodes complete. The Technical view surfaces
the node graph with per-node token counts and status. The Business view surfaces the
final plan and financial exposure.

---

## Observability Data Model

7 tables. Every platform capability traces back to one of them.

| Table | Role |
|---|---|
| Session | Scoped run container. Aggregates cost, quality, and success rate across tasks. |
| Task | Durable work queue row. Domain, agent id, input payload, priority, queue status, pricing id, retry lineage, attempts, claim metadata. |
| AgentRun | Core audit record. Prompt, response, tokens, cost, status, model, quality status/error, outcome link. |
| AgentDefinition | Agent catalog. Agent id to implementation, domain, model default, quality rubric. |
| ModelPricing | Cost lock. Active lookup is provider + model; referenced rows are expired and replaced, never mutated. |
| Metric | Time-series: `(ts, metric_name, metric_value, dimensions)`. Covers latency, cost, tokens, quality. |
| BusinessOutcome | Financial impact ledger. One row per successful run, linked to Task and AgentRun. |

`AgentRun` is the audit anchor. Governance, observability, retry lineage, quality scores,
and financial outcomes all link to a single row. Every outcome is auditable to its source run.

---

## Operational Control Points

| Control | Enforcement | Status |
|---|---|---|
| RunContext boundary | Agents populate only their 5 fields | Enforced |
| Durable task queue | Task rows store queue state, pricing, retry metadata, and claim recovery | Enforced |
| Migration-gated startup | Alembic head checked before serving; no runtime `create_all()` | Enforced |
| Cost locked at write time | Historical cost is fact, not estimate | Enforced |
| Provider/model pricing | Active pricing resolved by provider + model; duplicate active rows fail | Enforced |
| Provider lifecycle | Reusable clients, transient retries, close-on-shutdown | Enforced |
| Protected trace access | Summary APIs omit raw traces; trace endpoint can require API key | Guardrail |
| Quality async only | Judge never blocks task execution; failures persist quality status/error | Async |
| Retry lineage | `retry_of` preserves relationship to original failed run | Linked |
| SSE event stream | Structured `run_started`, `run_completed`, `quality_scored` events with IDs | Live |
| Stale recovery | Stranded runs and interrupted task claims recovered on startup | Guardrail |
| Backpressure cleanup | Stalled SSE subscribers removed automatically | Guardrail |

---

## Run Scope Model

Three execution scopes, selectable before each run:

**Complete Platform** — All 7 business agents across both domains. Results roll into a
cross-domain executive summary with unified outcome ledger and ROI calculation.

**Project Management** — 4 agents: SprintRiskAgent, ResourceAllocationAgent,
DeliveryForecastAgent, ProjectPlanningAgent. Scoped to delivery risk and planning exposure.

**Revenue Management** — 3 agents: RenewalRiskAgent, ChurnSignalAgent,
PipelineForecastAgent. Scoped to renewal risk, churn signals, and late-quarter pipeline gaps.

`QualityJudgeAgent` is a platform control — not a selectable domain run. It appears in
the Governance view, not the scope selector.

---

## Technology Stack

| Component | Technology |
|---|---|
| API | FastAPI · async SQLAlchemy · typed resource routers |
| Database | SQLite local default · Alembic migrations · optional Postgres smoke validation |
| LLM providers | Ollama (default) · Groq · Gemini — reusable clients through `LLMClient.complete()` |
| Workflow agent | LangGraph 5-node graph with parent-child run records |
| Frontend | React 18 · Vite · TypeScript · Recharts · Tailwind CSS |
| Live feed | Server-Sent Events — structured run and quality events with event IDs |
| Experiment tracking | MLflow |

---

## Quick Start

```bash
cd backend
make install
make migrate
make seed
make dev
```

API: `http://localhost:8000` — Frontend: `http://localhost:5173`

Optional Postgres migration smoke check:

```bash
cd backend
AGENTOPS_POSTGRES_TEST_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db \
  make postgres-migrate-smoke
```

Full developer documentation — code flow, AgentOps contract internals, how to add a
new agent, pricing configuration, and structured SSE streaming model — is at
[docs/developer-guide.md](docs/developer-guide.md).

---

## Design Principles

**The management layer is the product.** Most teams treat observability as an
afterthought bolted onto agents that already run. This platform inverts that: the
control plane is the foundation. Agents are plugged into it.

**Financial accountability is a first-class output.** Every agent decision produces a
dollar-value consequence linked to its run record. If an agent output cannot be expressed
as a business outcome, it should not be in production.

**Separation of agent logic from platform concerns is enforced, not requested.** The
agent contract is a boundary, not a convention. Agents that violate it cannot run.

**Cost is locked at write time.** Historical cost records are facts. Pricing changes do
not retroactively alter what a past run cost.

**Failure is always visible.** A run is COMPLETE or FAILED. The `finally` block in
`run_context()` is a guarantee, not a best practice.
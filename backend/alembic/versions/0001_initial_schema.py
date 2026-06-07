"""Initial AgentOps schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("total_cost_usd", sa.Float(), nullable=False),
        sa.Column("total_tasks", sa.Integer(), nullable=False),
        sa.Column("success_rate", sa.Float(), nullable=False),
        sa.Column("avg_quality_score", sa.Float(), nullable=False),
    )
    op.create_table(
        "agent_definitions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("domain", sa.String(length=60), nullable=False),
        sa.Column("agent_type", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("model_default", sa.String(length=120), nullable=False),
        sa.Column("execution_mode", sa.String(length=60), nullable=False),
        sa.Column("quality_rubric", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_definitions_domain", "agent_definitions", ["domain"])
    op.create_index("ix_agent_definitions_agent_type", "agent_definitions", ["agent_type"])
    op.create_table(
        "model_pricing",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("input_cost_per_1k", sa.Float(), nullable=False),
        sa.Column("output_cost_per_1k", sa.Float(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_model_pricing_provider", "model_pricing", ["provider"])
    op.create_index("ix_model_pricing_model_name", "model_pricing", ["model_name"])
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agent_definitions.id"), nullable=False),
        sa.Column("domain", sa.String(length=60), nullable=False),
        sa.Column("task_type", sa.String(length=120), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_tasks_session_id", "tasks", ["session_id"])
    op.create_index("ix_tasks_agent_id", "tasks", ["agent_id"])
    op.create_index("ix_tasks_domain", "tasks", ["domain"])
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agent_definitions.id"), nullable=False),
        sa.Column("model_pricing_id", sa.String(), sa.ForeignKey("model_pricing.id"), nullable=False),
        sa.Column("run_type", sa.String(length=40), nullable=False),
        sa.Column("parent_run_id", sa.String(), sa.ForeignKey("agent_runs.id")),
        sa.Column("retry_of", sa.String(), sa.ForeignKey("agent_runs.id")),
        sa.Column("model_used", sa.String(length=120), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("raw_prompt", sa.Text(), nullable=False),
        sa.Column("raw_response", sa.Text(), nullable=False),
        sa.Column("output_payload", sa.JSON(), nullable=False),
        sa.Column("quality_score", sa.Float()),
        sa.Column("quality_relevance", sa.Float()),
        sa.Column("quality_faithfulness", sa.Float()),
        sa.Column("quality_completeness", sa.Float()),
        sa.Column("quality_actionability", sa.Float()),
        sa.Column("quality_dimensions", sa.JSON()),
        sa.Column("ran_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_agent_runs_task_id", "agent_runs", ["task_id"])
    op.create_index("ix_agent_runs_agent_id", "agent_runs", ["agent_id"])
    op.create_index("ix_agent_runs_task_ran_at", "agent_runs", ["task_id", "ran_at"])
    op.create_index("ix_agent_runs_quality_score", "agent_runs", ["quality_score"])
    op.create_index("ix_agent_runs_ran_at", "agent_runs", ["ran_at"])
    op.create_table(
        "business_outcomes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("agent_run_id", sa.String(), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("domain", sa.String(length=60), nullable=False),
        sa.Column("outcome_type", sa.String(length=120), nullable=False),
        sa.Column("metric_name", sa.String(length=120), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("metric_unit", sa.String(length=40), nullable=False),
        sa.Column("financial_impact_usd", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_business_outcomes_task_id", "business_outcomes", ["task_id"])
    op.create_index("ix_business_outcomes_agent_run_id", "business_outcomes", ["agent_run_id"])
    op.create_index("ix_business_outcomes_domain", "business_outcomes", ["domain"])
    op.create_table(
        "metrics",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("agent_run_id", sa.String(), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric_name", sa.String(length=120), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("dimensions", sa.JSON(), nullable=False),
    )
    op.create_index("ix_metrics_agent_run_id", "metrics", ["agent_run_id"])
    op.create_index("ix_metrics_metric_name", "metrics", ["metric_name"])
    op.create_index("ix_metrics_ts", "metrics", ["ts"])


def downgrade() -> None:
    op.drop_table("metrics")
    op.drop_table("business_outcomes")
    op.drop_table("agent_runs")
    op.drop_table("tasks")
    op.drop_table("model_pricing")
    op.drop_table("agent_definitions")
    op.drop_table("sessions")


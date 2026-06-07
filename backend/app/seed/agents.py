from app.core.enums import AgentExecutionMode, Domain

AGENT_DEFINITIONS = [
    {
        "id": "agent-sprint-risk",
        "name": "SprintRiskAgent",
        "domain": Domain.PROJECT_DELIVERY,
        "agent_type": "sprint_risk_assessment",
        "description": (
            "Assesses delivery risk for a sprint using velocity, tasks, and team context"
        ),
        "model_default": "llama3.2:3b",
        "execution_mode": AgentExecutionMode.SINGLE_SHOT,
        "quality_rubric": "Assess sprint relevance, faithfulness, completeness, and actionability.",
    },
    {
        "id": "agent-resource-alloc",
        "name": "ResourceAllocationAgent",
        "domain": Domain.PROJECT_DELIVERY,
        "agent_type": "resource_allocation",
        "description": "Optimizes task-to-engineer assignment based on skills, capacity, and risk",
        "model_default": "llama3.2:3b",
        "execution_mode": AgentExecutionMode.SINGLE_SHOT,
        "quality_rubric": (
            "Assess assignment specificity, skill faithfulness, coverage, and actionability."
        ),
    },
    {
        "id": "agent-delivery-forecast",
        "name": "DeliveryForecastAgent",
        "domain": Domain.PROJECT_DELIVERY,
        "agent_type": "delivery_forecast",
        "description": "Forecasts milestone delivery confidence and pipeline exposure",
        "model_default": "llama3.2:3b",
        "execution_mode": AgentExecutionMode.SINGLE_SHOT,
        "quality_rubric": (
            "Assess milestone targeting, evidence use, forecast completeness, and escalations."
        ),
    },
    {
        "id": "agent-renewal-risk",
        "name": "RenewalRiskAgent",
        "domain": Domain.REVENUE_OPS,
        "agent_type": "renewal_risk_score",
        "description": "Scores account renewal risk and recommends save actions",
        "model_default": "llama3.2:3b",
        "execution_mode": AgentExecutionMode.SINGLE_SHOT,
        "quality_rubric": (
            "Assess account specificity, signal grounding, risk completeness, and next steps."
        ),
    },
    {
        "id": "agent-churn-signal",
        "name": "ChurnSignalAgent",
        "domain": Domain.REVENUE_OPS,
        "agent_type": "churn_signal_detection",
        "description": "Detects early churn signals before renewal",
        "model_default": "llama3.2:3b",
        "execution_mode": AgentExecutionMode.SINGLE_SHOT,
        "quality_rubric": (
            "Assess behavioral relevance, no invented signals, signal coverage, and save play."
        ),
    },
    {
        "id": "agent-pipeline-forecast",
        "name": "PipelineForecastAgent",
        "domain": Domain.REVENUE_OPS,
        "agent_type": "pipeline_forecast",
        "description": "Forecasts quota attainment and recoverable pipeline gaps",
        "model_default": "llama3.2:3b",
        "execution_mode": AgentExecutionMode.SINGLE_SHOT,
        "quality_rubric": (
            "Assess deal-specific judgment, time grounding, forecast coverage, and actions."
        ),
    },
    {
        "id": "agent-project-planning",
        "name": "ProjectPlanningAgent",
        "domain": Domain.PROJECT_DELIVERY,
        "agent_type": "project_planning_workflow",
        "description": "5-node workflow from natural language to full project plan",
        "model_default": "llama3.2:3b",
        "execution_mode": AgentExecutionMode.LANGGRAPH_WORKFLOW,
        "quality_rubric": (
            "Assess plan relevance, grounded scope, complete plan, and actionable owners."
        ),
    },
    {
        "id": "agent-quality-judge",
        "name": "QualityJudgeAgent",
        "domain": Domain.PLATFORM,
        "agent_type": "quality_evaluation",
        "description": "Async LLM-as-judge for all agent outputs",
        "model_default": "llama3.1:8b",
        "execution_mode": AgentExecutionMode.SINGLE_SHOT,
        "quality_rubric": "N/A",
    },
]

WORKFLOW_NODE_DEFINITIONS = [
    {
        "id": f"node_{name}",
        "name": f"ProjectPlanning.{name}",
        "domain": Domain.PROJECT_DELIVERY,
        "agent_type": f"workflow_node_{name}",
        "description": f"Internal ProjectPlanningAgent workflow node: {name}",
        "model_default": "llama3.2:3b",
        "execution_mode": AgentExecutionMode.LANGGRAPH_WORKFLOW,
        "quality_rubric": (
            "Evaluate node output for relevance, grounding, completeness, and actionability."
        ),
    }
    for name in ["decompose", "capacity_check", "risk_assess", "assign", "synthesize"]
]

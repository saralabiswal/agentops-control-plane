PROJECT_DELIVERY_FIXTURES = [
    {
        "fixture_id": "project-orion-bank-launch",
        "scenario_name": "Orion v4.2 regional bank launch",
        "milestone_name": "Orion v4.2 FirstWest Bank launch",
        "customer": "FirstWest Bank",
        "business_context": (
            "Mobile onboarding launch is tied to contracted digital account opening revenue."
        ),
        "executive_owner": "Maya Patel, SVP Digital Banking",
        "sprint_name": "Orion v4.2 Launch Readiness",
        "team_size": 7,
        "days_remaining": 9,
        "total_tasks": 31,
        "completed_tasks": 14,
        "velocity_history": [21, 19, 16],
        "external_dependencies": [
            "Identity provider production certificate",
            "Fraud-service rate limit approval",
            "Security exception sign-off",
        ],
        "capacity_notes": (
            "Tech lead is at 60% due to Sev-2 support; QA lead is split with release audit."
        ),
        "delay_cost_per_week_usd": 185000,
        "committed_revenue_usd": 1250000,
        "target_date": "2026-07-18",
        "current_date": "2026-06-07",
        "backlog_count": 42,
        "avg_velocity": 17,
        "sprint_length_days": 14,
        "blockers": [
            "Fraud-service performance test has not passed at target volume",
            "Final SOC2 evidence package is missing two controls",
        ],
        "capacity_changes": "Two engineers are covering production support until June 14.",
        "tasks": [
            {"id": "OIDC-214", "skill": "identity", "estimate_hours": 24, "priority": "HIGH"},
            {"id": "FRAUD-88", "skill": "backend", "estimate_hours": 28, "priority": "HIGH"},
            {"id": "SEC-72", "skill": "security", "estimate_hours": 18, "priority": "HIGH"},
            {"id": "QA-140", "skill": "quality", "estimate_hours": 20, "priority": "HIGH"},
            {"id": "REL-31", "skill": "release", "estimate_hours": 12, "priority": "NORMAL"},
        ],
        "team_members": [
            {
                "name": "Asha Rao",
                "role": "Tech Lead",
                "skills": ["identity", "backend", "security"],
                "load_pct": 82,
                "availability_pct": 70,
            },
            {
                "name": "Mateo Cruz",
                "role": "Senior Engineer",
                "skills": ["backend", "release"],
                "load_pct": 68,
                "availability_pct": 85,
            },
            {
                "name": "Lina Park",
                "role": "QA Lead",
                "skills": ["quality", "automation", "security"],
                "load_pct": 76,
                "availability_pct": 75,
            },
            {
                "name": "Devon Shah",
                "role": "Platform Engineer",
                "skills": ["release", "observability", "backend"],
                "load_pct": 55,
                "availability_pct": 90,
            },
        ],
        "sprint_weeks": 3,
        "avg_task_hours": 20,
        "hourly_rate": 165,
        "timeline_weeks": 6,
        "instruction": (
            "Create a recovery plan for Orion v4.2 launch readiness with epics for "
            "identity, fraud-service readiness, security evidence, QA automation, owners, "
            "risk tradeoffs, and executive decision points."
        ),
    },
    {
        "fixture_id": "project-cpq-stabilization",
        "scenario_name": "CPQ stabilization for enterprise renewals",
        "milestone_name": "GlobalTel CPQ renewal quote readiness",
        "customer": "GlobalTel Communications",
        "business_context": (
            "Pricing defects are delaying renewal quotes for three enterprise accounts."
        ),
        "executive_owner": "Elena Morris, VP Revenue Operations",
        "sprint_name": "CPQ Stabilization 6.1",
        "team_size": 5,
        "days_remaining": 6,
        "total_tasks": 20,
        "completed_tasks": 7,
        "velocity_history": [13, 11, 9],
        "external_dependencies": [
            "ERP tax service regression sign-off",
            "Discount approval matrix from Revenue Ops",
        ],
        "capacity_notes": "Pricing architect is split across two customer escalations.",
        "delay_cost_per_week_usd": 140000,
        "committed_revenue_usd": 780000,
        "target_date": "2026-07-03",
        "current_date": "2026-06-07",
        "backlog_count": 27,
        "avg_velocity": 10,
        "sprint_length_days": 14,
        "blockers": [
            "Tax-service sandbox data differs from production",
            "Regression environment is unstable during nightly runs",
        ],
        "capacity_changes": "Pricing architect available 60%; QA lead available 80%.",
        "tasks": [
            {"id": "CPQ-118", "skill": "pricing", "estimate_hours": 22, "priority": "HIGH"},
            {"id": "ERP-44", "skill": "integration", "estimate_hours": 18, "priority": "HIGH"},
            {"id": "QA-91", "skill": "quality", "estimate_hours": 16, "priority": "HIGH"},
            {"id": "REV-27", "skill": "pricing", "estimate_hours": 12, "priority": "HIGH"},
            {"id": "DOC-12", "skill": "enablement", "estimate_hours": 8, "priority": "NORMAL"},
        ],
        "team_members": [
            {
                "name": "Priya Nair",
                "role": "Pricing Architect",
                "skills": ["pricing", "backend"],
                "load_pct": 86,
                "availability_pct": 65,
            },
            {
                "name": "Noah Brooks",
                "role": "Integration Engineer",
                "skills": ["integration", "quality"],
                "load_pct": 62,
                "availability_pct": 85,
            },
            {
                "name": "Elena Rossi",
                "role": "QA Lead",
                "skills": ["quality", "enablement"],
                "load_pct": 58,
                "availability_pct": 80,
            },
        ],
        "sprint_weeks": 2,
        "avg_task_hours": 16,
        "hourly_rate": 155,
        "timeline_weeks": 4,
        "instruction": (
            "Create a CPQ stabilization plan covering pricing defect correction, ERP tax "
            "validation, regression hardening, renewal quote readiness, owners, and "
            "executive escalation gates."
        ),
    },
    {
        "fixture_id": "project-atlas-migration",
        "scenario_name": "Atlas cloud migration cutover",
        "milestone_name": "Summit Energy Atlas migration cutover",
        "customer": "Summit Energy",
        "business_context": (
            "Cloud cutover unlocks contracted analytics capacity for a regulated energy customer."
        ),
        "executive_owner": "Ravi Menon, VP Platform Engineering",
        "sprint_name": "Atlas Migration Cutover",
        "team_size": 8,
        "days_remaining": 11,
        "total_tasks": 34,
        "completed_tasks": 13,
        "velocity_history": [22, 18, 15],
        "external_dependencies": [
            "Network allowlist approval",
            "Database replication freeze window",
            "Customer DR test window",
        ],
        "capacity_notes": "Two platform engineers are on incident rotation until June 16.",
        "delay_cost_per_week_usd": 210000,
        "committed_revenue_usd": 1350000,
        "target_date": "2026-07-26",
        "current_date": "2026-06-07",
        "backlog_count": 45,
        "avg_velocity": 16,
        "sprint_length_days": 14,
        "blockers": [
            "Database replication dry run has not met RPO",
            "Customer DR test window is not confirmed",
        ],
        "capacity_changes": "Platform team has two engineers on incident rotation.",
        "tasks": [
            {"id": "NET-31", "skill": "network", "estimate_hours": 20, "priority": "HIGH"},
            {"id": "DB-82", "skill": "database", "estimate_hours": 26, "priority": "HIGH"},
            {"id": "CUT-17", "skill": "platform", "estimate_hours": 18, "priority": "HIGH"},
            {"id": "DR-22", "skill": "reliability", "estimate_hours": 20, "priority": "HIGH"},
            {"id": "OBS-09", "skill": "observability", "estimate_hours": 12, "priority": "NORMAL"},
        ],
        "team_members": [
            {
                "name": "Ravi Iyer",
                "role": "Platform Lead",
                "skills": ["platform", "observability", "reliability"],
                "load_pct": 78,
                "availability_pct": 75,
            },
            {
                "name": "Mina Chen",
                "role": "Database Engineer",
                "skills": ["database", "backend"],
                "load_pct": 66,
                "availability_pct": 85,
            },
            {
                "name": "Omar Haddad",
                "role": "Network Engineer",
                "skills": ["network", "platform"],
                "load_pct": 82,
                "availability_pct": 70,
            },
            {
                "name": "Grace Lee",
                "role": "Reliability Engineer",
                "skills": ["reliability", "observability"],
                "load_pct": 58,
                "availability_pct": 90,
            },
        ],
        "sprint_weeks": 3,
        "avg_task_hours": 19,
        "hourly_rate": 170,
        "timeline_weeks": 7,
        "instruction": (
            "Build an Atlas migration cutover plan with epics for network readiness, "
            "database replication, DR validation, observability, rollback criteria, owners, "
            "and executive decision points."
        ),
    },
]

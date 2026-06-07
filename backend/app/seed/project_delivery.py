PROJECT_DELIVERY_FIXTURES = [
    {
        "fixture_id": "sprint-orion-v4",
        "sprint_name": "Orion v4.2",
        "team_size": 6,
        "days_remaining": 8,
        "total_tasks": 22,
        "completed_tasks": 11,
        "velocity_history": [18, 20, 15],
        "external_dependencies": ["Vendor API cert renewal (unconfirmed)"],
        "capacity_notes": "Two engineers at 80% load due to on-call rotation",
        "delay_cost_per_week_usd": 75000,
    },
    {
        "fixture_id": "milestone-platform-q3",
        "milestone_name": "Platform Q3 Milestone",
        "committed_revenue_usd": 240000,
        "target_date": "2026-09-30",
        "current_date": "2026-06-05",
        "backlog_count": 34,
        "avg_velocity": 12,
        "sprint_length_days": 14,
        "blockers": ["Infra provisioning blocked on vendor SLA"],
    },
    {
        "fixture_id": "team-migration",
        "team_members": [
            {
                "name": "Tom W.",
                "role": "Tech Lead",
                "skills": ["infra", "payments", "k8s"],
                "load_pct": 55,
            },
            {
                "name": "James K.",
                "role": "Senior Eng",
                "skills": ["backend", "payments"],
                "load_pct": 60,
            },
            {
                "name": "Mei L.",
                "role": "Senior Eng",
                "skills": ["frontend", "testing"],
                "load_pct": 30,
            },
            {
                "name": "Carlos R.",
                "role": "Mid Eng",
                "skills": ["backend", "infra"],
                "load_pct": 50,
            },
        ],
    },
]

import json
from typing import Any

from app.agentops.context import RunContext
from app.agents.parsing import JSON_ONLY, parse_json_object
from app.agents.workflow.state import ProjectPlanState


def _stories_from_breakdown(work_breakdown: Any) -> list[dict[str, Any]]:
    stories: list[dict[str, Any]] = []
    for epic in work_breakdown or []:
        if not isinstance(epic, dict):
            continue
        epic_stories = epic.get("stories", [])
        if not isinstance(epic_stories, list):
            continue
        stories.extend(story for story in epic_stories if isinstance(story, dict))
    return stories


def _story_identity(story: Any, fallback_index: int) -> tuple[str, str, str | None]:
    if isinstance(story, dict):
        story_id = str(story.get("id") or story.get("story_id") or f"S-{fallback_index}")
        story_name = str(story.get("name") or story.get("title") or story_id)
        epic_id = story.get("epic_id")
        return story_id, story_name, str(epic_id) if epic_id is not None else None
    story_name = str(story)
    return f"S-{fallback_index}", story_name, None


def _load_assignment_results(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _find_story(stories: list[dict[str, Any]], candidate: Any) -> dict[str, Any] | None:
    if not stories:
        return None
    if isinstance(candidate, dict):
        candidate_id = candidate.get("id") or candidate.get("story_id")
        candidate_name = candidate.get("name") or candidate.get("title")
    else:
        candidate_id = None
        candidate_name = str(candidate)

    for story in stories:
        if candidate_id is not None and str(story.get("id")) == str(candidate_id):
            return story
        if candidate_name is not None and str(story.get("name")) == str(candidate_name):
            return story
    return None


def _assignments_from_results(
    results: dict[str, Any], stories: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    assignments: list[dict[str, Any]] = []
    fallback_index = 1
    for assignee, assigned_stories in results.items():
        if not isinstance(assigned_stories, list):
            continue
        for assigned_story in assigned_stories:
            story = _find_story(stories, assigned_story) or assigned_story
            story_id, story_name, epic_id = _story_identity(story, fallback_index)
            assignments.append(
                {
                    "story_id": story_id,
                    "story_name": story_name,
                    "assigned_to": str(assignee),
                    "reasoning": "Normalized from assignment_results.",
                    "epic_id": epic_id,
                }
            )
            fallback_index += 1
    return assignments


def _normalize_assignments(
    data: dict[str, Any], stories: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    assignments = data.get("assignments")
    if isinstance(assignments, list):
        return [item for item in assignments if isinstance(item, dict)]

    assignment_results = _load_assignment_results(data.get("assignment_results"))
    if assignment_results is not None:
        return _assignments_from_results(assignment_results, stories)

    summary = data.get("assignment_summary")
    if isinstance(summary, dict):
        assignment_results = _load_assignment_results(summary.get("assignment_results"))
        if assignment_results is not None:
            return _assignments_from_results(assignment_results, stories)

    return []


async def run(state: ProjectPlanState, ctx: RunContext, llm: Any) -> ProjectPlanState:
    stories = _stories_from_breakdown(state["work_breakdown"])
    capacity_assessment = state["capacity_assessment"] or {"team_capacity": []}
    team_capacity = capacity_assessment.get("team_capacity", [])
    prompt = f"""You are a task assignment optimizer.

Stories to assign: {stories}
Team capacity: {team_capacity}
Risk register: {state['risk_register']}

Assign each story to a team member by risk, skill match, and capacity.
Return JSON with assignments and assignment_summary.
Use assignments as a top-level array of objects with story_id, story_name, assigned_to,
reasoning, and epic_id. Do not put assignments only inside assignment_summary.
{JSON_ONLY}"""
    response = await llm.complete(prompt)
    ctx.raw_prompt = prompt
    ctx.model_used = response.model
    ctx.raw_response = response.text
    ctx.prompt_tokens = response.usage.prompt_tokens
    ctx.completion_tokens = response.usage.completion_tokens
    data = parse_json_object(response.text, required=[])
    assignments = _normalize_assignments(data, stories)
    state["node_traces"].append(
        {
            "node": "assign",
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "latency_ms": response.latency_ms,
            "model": response.model,
        }
    )
    return {**state, "assigned_plan": assignments}

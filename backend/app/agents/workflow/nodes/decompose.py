from typing import Any, cast

from app.agentops.context import RunContext
from app.agents.parsing import JSON_ONLY, parse_json_object
from app.agents.workflow.state import Epic, ProjectPlanState


def _normalize_story(story: dict[str, Any], epic_id: str, story_index: int) -> dict[str, Any]:
    story_id = story.get("id") or story.get("story_id") or f"{epic_id}-S{story_index}"
    effort_points = story.get("effort_points", story.get("story_points"))
    return {
        **story,
        "id": str(story_id),
        "name": str(story.get("name") or story.get("title") or f"Story {story_index}"),
        "effort_points": effort_points,
        "required_skills": story.get("required_skills", story.get("skills", [])),
        "epic_id": epic_id,
    }


def _normalize_epics(epics: Any) -> list[Epic]:
    if not isinstance(epics, list):
        raise ValueError("Field epics must be a list")

    normalized: list[Epic] = []
    for index, epic in enumerate(epics, start=1):
        if not isinstance(epic, dict):
            raise ValueError(f"Epic {index} must be a JSON object")

        epic_id = str(epic.get("id") or f"E-{index:02d}")
        stories = epic.get("stories", epic.get("tasks", []))
        if stories is None:
            stories = []
        if not isinstance(stories, list):
            raise ValueError(f"Epic {epic_id} stories must be a list")
        normalized_stories: list[dict[str, Any]] = []
        for story_index, story in enumerate(stories, start=1):
            if not isinstance(story, dict):
                raise ValueError(f"Epic {epic_id} story {story_index} must be a JSON object")
            normalized_stories.append(_normalize_story(story, epic_id, story_index))

        owners = epic.get("owners", [])
        owner = epic.get("owner")
        if owner is None and isinstance(owners, list) and owners:
            owner = owners[0]
        normalized.append(
            cast(
                Epic,
                {
                    **epic,
                    "id": epic_id,
                    "name": str(epic.get("name") or f"Epic {index}"),
                    "description": str(epic.get("description") or ""),
                    "owner": str(owner or ""),
                    "weeks": str(epic.get("weeks") or ""),
                    "stories": normalized_stories,
                },
            )
        )
    return normalized


async def run(state: ProjectPlanState, ctx: RunContext, llm: Any) -> ProjectPlanState:
    prompt = f"""You are a project decomposition expert.

Project instruction: {state['instruction']}
Team size: {len(state['team_members'])} engineers
Timeline: {state['timeline_weeks']} weeks
Committed revenue: ${state['committed_revenue_usd']:,}

Break this project into 3-5 epics with concrete stories.
Return JSON with epics, total_story_points, and critical_path.
Each epic must include a stories array. Do not use tasks instead of stories.
{JSON_ONLY}"""
    response = await llm.complete(prompt)
    ctx.raw_prompt = prompt
    ctx.model_used = response.model
    ctx.raw_response = response.text
    ctx.prompt_tokens = response.usage.prompt_tokens
    ctx.completion_tokens = response.usage.completion_tokens
    data = parse_json_object(response.text, required=["epics"])
    epics = _normalize_epics(data["epics"])
    state["node_traces"].append(
        {
            "node": "decompose",
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "latency_ms": response.latency_ms,
            "model": response.model,
        }
    )
    return {**state, "work_breakdown": epics}

import json
from collections.abc import Iterable
from typing import Any

JSON_ONLY = (
    "IMPORTANT: Respond ONLY with valid JSON. No preamble, no markdown code fences, "
    "no explanation text. Start your response with { and end with }."
)


def parse_json_object(raw: str, required: Iterable[str]) -> dict[str, Any]:
    data = json.loads(raw.strip())
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    for field in required:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
    return data

import ast
import json
import re
from collections.abc import Iterable
from typing import Any

JSON_ONLY = (
    "IMPORTANT: Respond ONLY with valid JSON. No preamble, no markdown code fences, "
    "no explanation text. Start your response with { and end with }."
)

_NUMBER = r"-?\d+(?:\.\d+)?"
_NUMERIC_EXPRESSION = re.compile(
    rf"(:\s*)({_NUMBER}(?:\s*[+\-*/]\s*{_NUMBER})+)(\s*[,}}\]])"
)
_STRING = r'"(?:[^"\\]|\\.)*"'
_STRING_LITERAL_OBJECT_VALUE = re.compile(
    rf"(:\s*)\{{(\s*{_STRING}\s*(?:,\s*{_STRING}\s*)*)\}}"
)
_KEYLESS_NAME_ARRAY_PROPERTY = re.compile(
    rf'(\{{\s*"name"\s*:\s*{_STRING}\s*,\s*)(\[[^\[\]{{}}]*\])(\s*\}})'
)


def parse_json_object(
    raw: str,
    required: Iterable[str],
    *,
    keyless_array_property: str = "values",
) -> dict[str, Any]:
    data = _loads_json(raw, keyless_array_property=keyless_array_property)
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    for field in required:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
    return data


def _loads_json(raw: str, *, keyless_array_property: str) -> Any:
    text = _extract_json(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError as original_error:
        repaired = _repair_common_model_json_defects(
            text,
            keyless_array_property=keyless_array_property,
        )
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            raise original_error


def _extract_json(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    if start == -1:
        return text
    text = text[start:]
    end = _balanced_json_object_end(text)
    if end is not None and text[end + 1 :].strip():
        text = text[: end + 1]
    return text


def _repair_common_model_json_defects(text: str, *, keyless_array_property: str) -> str:
    repaired = _NUMERIC_EXPRESSION.sub(_replace_numeric_expression, text)
    repaired = _STRING_LITERAL_OBJECT_VALUE.sub(_replace_string_literal_object, repaired)
    repaired = _KEYLESS_NAME_ARRAY_PROPERTY.sub(
        lambda match: _replace_keyless_name_array_property(match, keyless_array_property),
        repaired,
    )
    return _append_missing_closers(repaired)


def _balanced_json_object_end(text: str) -> int | None:
    stack: list[str] = []
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_string:
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char in "{[":
            stack.append(char)
        elif char == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif char == "]" and stack and stack[-1] == "[":
            stack.pop()
        if not stack:
            return index
    return None


def _replace_numeric_expression(match: re.Match[str]) -> str:
    prefix, expression, suffix = match.groups()
    return f"{prefix}{_evaluate_numeric_expression(expression)}{suffix}"


def _replace_string_literal_object(match: re.Match[str]) -> str:
    prefix, values = match.groups()
    return f"{prefix}[{values}]"


def _replace_keyless_name_array_property(
    match: re.Match[str],
    property_name: str,
) -> str:
    prefix, values, suffix = match.groups()
    return f'{prefix}"{property_name}": {values}{suffix}'


def _evaluate_numeric_expression(expression: str) -> str:
    tree = ast.parse(expression, mode="eval")
    value = _evaluate_ast(tree.body)
    return f"{value:.12g}"


def _evaluate_ast(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_evaluate_ast(node.operand)
    if isinstance(node, ast.BinOp):
        left = _evaluate_ast(node.left)
        right = _evaluate_ast(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
    raise ValueError(f"Unsupported numeric expression: {ast.dump(node)}")


def _append_missing_closers(text: str) -> str:
    stack: list[str] = []
    in_string = False
    escaped = False
    for char in text:
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_string:
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char in "{[":
            stack.append(char)
        elif char == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif char == "]" and stack and stack[-1] == "[":
            stack.pop()
    closers = {"{": "}", "[": "]"}
    return text + "".join(closers[opener] for opener in reversed(stack))

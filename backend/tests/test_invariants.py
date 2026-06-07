from pathlib import Path

AGENTS_ROOT = Path("app/agents")


def agent_sources() -> list[tuple[Path, str]]:
    return [
        (path, path.read_text())
        for path in AGENTS_ROOT.rglob("*.py")
        if path.name != "__init__.py"
    ]


def test_agents_do_not_write_to_database_directly() -> None:
    forbidden_write_calls = [".add(", ".commit(", ".execute("]
    offenders = [
        str(path)
        for path, source in agent_sources()
        if any(call in source for call in forbidden_write_calls)
    ]

    assert offenders == []


def test_agents_do_not_emit_sse_or_calculate_cost() -> None:
    offenders = [
        str(path)
        for path, source in agent_sources()
        if "emit_run_" in source or "cost_usd" in source or "CostCalculator" in source
    ]

    assert offenders == []


def test_agents_do_not_import_provider_adapters_or_httpx() -> None:
    forbidden_imports = [
        "import httpx",
        "from app.llm.ollama",
        "from app.llm.groq",
        "from app.llm.gemini",
    ]
    offenders = [
        str(path)
        for path, source in agent_sources()
        if any(import_text in source for import_text in forbidden_imports)
    ]

    assert offenders == []


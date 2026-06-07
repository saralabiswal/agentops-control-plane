import importlib
import pkgutil

import app


def test_import_all_app_modules() -> None:
    failures: list[str] = []
    for module in pkgutil.walk_packages(app.__path__, prefix="app."):
        try:
            importlib.import_module(module.name)
        except Exception as exc:  # pragma: no cover - assertion reports exact module.
            failures.append(f"{module.name}: {type(exc).__name__}: {exc}")

    assert failures == []


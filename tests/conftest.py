"""Pytest configuration: map ``app.*`` imports to top-level packages."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _ensure_root_on_path() -> None:
    root_s = str(ROOT)
    if root_s not in sys.path:
        sys.path.insert(0, root_s)


def _register_audit_stub() -> None:
    """Provide a no-op ``audit.logger`` so executor imports without a DB.

    The production ``audit`` package is not part of this template, but the
    executor imports ``write_audit_event`` at module load time. Tests that
    need to assert on audit calls monkeypatch this stub on the executor
    module directly.
    """
    if "audit.logger" in sys.modules:
        return

    async def write_audit_event(**_: object) -> None:
        return None

    audit_mod = types.ModuleType("audit")
    logger_mod = types.ModuleType("audit.logger")
    logger_mod.write_audit_event = write_audit_event
    audit_mod.logger = logger_mod
    sys.modules["audit"] = audit_mod
    sys.modules["audit.logger"] = logger_mod


def _register_app_namespace() -> None:
    """Expose graph/, llm/, and agent/ modules under the ``app.*`` names."""
    if "app.agents.planner" in sys.modules:
        return

    import config.prompts as config_prompts
    import graph.schemas as graph_schemas
    import graph.state as graph_state
    import llm.providers as llm_providers
    import llm.retry as llm_retry

    app = types.ModuleType("app")
    sys.modules["app"] = app

    graph_mod = types.ModuleType("app.graph")
    graph_mod.schemas = graph_schemas
    graph_mod.state = graph_state
    sys.modules["app.graph"] = graph_mod
    sys.modules["app.graph.schemas"] = graph_schemas
    sys.modules["app.graph.state"] = graph_state

    llm_mod = types.ModuleType("app.llm")
    llm_mod.providers = llm_providers
    llm_mod.retry = llm_retry
    sys.modules["app.llm"] = llm_mod
    sys.modules["app.llm.providers"] = llm_providers
    sys.modules["app.llm.retry"] = llm_retry

    config_mod = types.ModuleType("app.config")
    config_mod.prompts = config_prompts
    sys.modules["app.config"] = config_mod
    sys.modules["app.config.prompts"] = config_prompts

    agents_mod = types.ModuleType("app.agents")
    sys.modules["app.agents"] = agents_mod

    _register_audit_stub()

    planner_path = ROOT / "agent" / "planner.py"
    spec = importlib.util.spec_from_file_location(
        "app.agents.planner",
        planner_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load planner from {planner_path}")
    planner = importlib.util.module_from_spec(spec)
    sys.modules["app.agents.planner"] = planner
    agents_mod.planner = planner
    spec.loader.exec_module(planner)

    executor_path = ROOT / "agent" / "executor.py"
    executor_spec = importlib.util.spec_from_file_location(
        "app.agents.executor",
        executor_path,
    )
    if executor_spec is None or executor_spec.loader is None:
        raise ImportError(f"Cannot load executor from {executor_path}")
    executor = importlib.util.module_from_spec(executor_spec)
    sys.modules["app.agents.executor"] = executor
    agents_mod.executor = executor
    executor_spec.loader.exec_module(executor)


_ensure_root_on_path()
_register_app_namespace()

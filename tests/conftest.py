"""Pytest configuration: map ``app.*`` imports to top-level packages."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _ensure_root_on_path() -> None:
    root_s = str(ROOT)
    if root_s not in sys.path:
        sys.path.insert(0, root_s)


def _register_audit_module() -> None:
    """Load the real audit logger (no-op when pool is unset)."""
    if "audit.logger" in sys.modules:
        return

    import audit.logger as audit_logger

    audit_mod = types.ModuleType("audit")
    audit_mod.logger = audit_logger
    sys.modules["audit"] = audit_mod
    sys.modules["audit.logger"] = audit_logger


def _register_app_namespace() -> None:
    """Attach agent/graph aliases to the real ``app`` HTTP package."""
    if "app.agents.planner" in sys.modules:
        return

    import config.prompts as config_prompts
    import graph.routing as graph_routing
    import graph.schemas as graph_schemas
    import graph.state as graph_state
    import llm.providers as llm_providers
    import llm.retry as llm_retry

    app_pkg = importlib.import_module("app")

    graph_mod = types.ModuleType("app.graph")
    graph_mod.schemas = graph_schemas
    graph_mod.state = graph_state
    graph_mod.routing = graph_routing
    app_pkg.graph = graph_mod
    sys.modules["app.graph"] = graph_mod
    sys.modules["app.graph.schemas"] = graph_schemas
    sys.modules["app.graph.state"] = graph_state
    sys.modules["app.graph.routing"] = graph_routing

    try:
        import graph.builder as graph_builder

        graph_mod.builder = graph_builder
        sys.modules["app.graph.builder"] = graph_builder
    except ImportError:
        pass

    llm_mod = types.ModuleType("app.llm")
    llm_mod.providers = llm_providers
    llm_mod.retry = llm_retry
    app_pkg.llm = llm_mod
    sys.modules["app.llm"] = llm_mod
    sys.modules["app.llm.providers"] = llm_providers
    sys.modules["app.llm.retry"] = llm_retry

    config_mod = types.ModuleType("app.config")
    config_mod.prompts = config_prompts
    app_pkg.config = config_mod
    sys.modules["app.config"] = config_mod
    sys.modules["app.config.prompts"] = config_prompts

    agents_mod = types.ModuleType("app.agents")
    app_pkg.agents = agents_mod
    sys.modules["app.agents"] = agents_mod

    _register_audit_module()

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

    reviewer_path = ROOT / "agent" / "reviewer.py"
    reviewer_spec = importlib.util.spec_from_file_location(
        "app.agents.reviewer",
        reviewer_path,
    )
    if reviewer_spec is None or reviewer_spec.loader is None:
        raise ImportError(f"Cannot load reviewer from {reviewer_path}")
    reviewer = importlib.util.module_from_spec(reviewer_spec)
    sys.modules["app.agents.reviewer"] = reviewer
    agents_mod.reviewer = reviewer
    reviewer_spec.loader.exec_module(reviewer)

    actioner_path = ROOT / "agent" / "actioner.py"
    actioner_spec = importlib.util.spec_from_file_location(
        "app.agents.actioner",
        actioner_path,
    )
    if actioner_spec is None or actioner_spec.loader is None:
        raise ImportError(f"Cannot load actioner from {actioner_path}")
    actioner = importlib.util.module_from_spec(actioner_spec)
    sys.modules["app.agents.actioner"] = actioner
    agents_mod.actioner = actioner
    actioner_spec.loader.exec_module(actioner)

    memorize_path = ROOT / "agent" / "memorize.py"
    memorize_spec = importlib.util.spec_from_file_location(
        "app.agents.memorize",
        memorize_path,
    )
    if memorize_spec is None or memorize_spec.loader is None:
        raise ImportError(f"Cannot load memorize from {memorize_path}")
    memorize = importlib.util.module_from_spec(memorize_spec)
    sys.modules["app.agents.memorize"] = memorize
    agents_mod.memorize = memorize
    memorize_spec.loader.exec_module(memorize)


_ensure_root_on_path()
_register_app_namespace()

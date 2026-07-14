"""Learner tool: run a manifest-listed thread script in Docker."""

from __future__ import annotations

import json

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from app.services.thread_artifacts import lookup_thread_dir
from tools.manifest import require_entry
from tools.sandbox_docker import run_python_in_docker


class RunThreadScriptInput(BaseModel):
    """Input for run_thread_script."""

    path: str = Field(
        description="Scripts-relative .py path listed in manifest.json"
    )


def make_run_thread_script(thread_id: str) -> BaseTool:
    """Build run_thread_script closed over ``thread_id``."""

    @tool("run_thread_script", args_schema=RunThreadScriptInput)
    async def run_thread_script(path: str) -> str:
        """Run a manifest-listed script in Docker; return exit/stdout/stderr."""
        root = lookup_thread_dir(thread_id)
        if root is None:
            raise FileNotFoundError(f"no thread dir for {thread_id!r}")
        scripts = root / "scripts"
        entry = require_entry(scripts, path)
        result = run_python_in_docker(
            scripts, entry.path, args=list(entry.args)
        )
        return json.dumps(
            {
                "path": entry.path,
                "purpose": entry.purpose,
                "status": result.status,
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "message": result.message,
            }
        )

    return run_thread_script

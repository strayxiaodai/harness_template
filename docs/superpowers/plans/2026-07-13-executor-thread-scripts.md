# Executor Thread Scripts + Docker Learner Runs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the executor write Python under `app/threads/<slug>/scripts/` (with manifest), and let the learner run manifest-listed scripts inside Docker S2 for review evidence.

**Architecture:** Thread-scoped tool factories bind `thread_id` from graph state (never trust model-supplied ids). Executor gets `write_thread_file` / `read_thread_file`. Learner mirrors the executor tool-loop and calls `run_thread_script`, which shells out only via `docker run` with network disabled and read-only script mount. No new graph nodes; phase D (skill promote) is out of scope.

**Tech Stack:** LangChain tools, LangGraph agents, Docker CLI subprocess, existing `app/services/thread_artifacts.py` index, pytest mocks for Docker.

**Spec:** [`docs/superpowers/specs/2026-07-13-executor-thread-scripts-design.md`](../specs/2026-07-13-executor-thread-scripts-design.md)

---

## File map

| File | Responsibility |
|------|----------------|
| `tools/thread_files.py` | Resolve thread paths; `write_thread_file` / `read_thread_file` factories |
| `tools/manifest.py` | Load/validate `scripts/manifest.json` entries |
| `tools/sandbox_docker.py` | Docker S2 `run_python_script` (no host fallback) |
| `tools/script_tools.py` | `run_thread_script` factory (learner-only) |
| `tools/registry.py` | Executor defaults + `get_executor_tools(thread_id)` / `get_learner_tools(thread_id)` |
| `agent/executor.py` | Pass `thread_id` into tool factory |
| `agent/learner.py` | Bounded tool loop + summarize; bind learner tools |
| `graph/state.py` | `learner_tool_calls` (+ optional `script_runs`) |
| `config/prompts.yaml` | Architect principles on executor; learner script-run guidance |
| `app/services/thread_artifacts.py` | Include `learner_tool_calls` / `script_runs` in learner stage keys |
| `docs/IMPLEMENTATION.md` | Tools, env vars, defaults |
| `docs/SECURITY.md` | Risk table for write/run tools |
| `tests/test_thread_files.py` | Write/read path rules |
| `tests/test_manifest.py` | Manifest parse/validation |
| `tests/test_sandbox_docker.py` | Mocked docker argv + failure modes |
| `tests/test_learner_tools.py` | Learner loop with mocked LLM/tools |
| `docs/histories/2026-07/…` | History entry after code lands |

---

### Task 1: Thread file helpers + write/read tools

**Files:**
- Create: `tools/thread_files.py`
- Create: `tests/test_thread_files.py`
- Modify: `app/services/thread_artifacts.py` (only if a thin helper is needed — prefer calling `lookup_thread_dir` / `init` from tests)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_thread_files.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.thread_artifacts import init_thread_artifacts
from tools.thread_files import (
    make_read_thread_file,
    make_write_thread_file,
    resolve_scripts_path,
)


@pytest.fixture
def thread_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HARNESS_THREADS_DIR", str(tmp_path))
    return init_thread_artifacts("demo task", "tid-1", plan=["a"])


@pytest.mark.asyncio
async def test_write_thread_file_creates_py_under_scripts(
    thread_dir: Path,
) -> None:
    tool = make_write_thread_file("tid-1")
    result = await tool.ainvoke(
        {"path": "hello.py", "content": "print(1)\n"}
    )
    assert (thread_dir / "scripts" / "hello.py").read_text() == "print(1)\n"
    assert "hello.py" in result


@pytest.mark.asyncio
async def test_write_rejects_parent_escape(thread_dir: Path) -> None:
    tool = make_write_thread_file("tid-1")
    with pytest.raises(ValueError, match="escape|scripts"):
        await tool.ainvoke({"path": "../meta.json", "content": "x"})


@pytest.mark.asyncio
async def test_write_allows_manifest_json(thread_dir: Path) -> None:
    tool = make_write_thread_file("tid-1")
    payload = json.dumps({"entries": []})
    await tool.ainvoke({"path": "manifest.json", "content": payload})
    assert (thread_dir / "scripts" / "manifest.json").is_file()


@pytest.mark.asyncio
async def test_write_rejects_non_py_non_manifest(thread_dir: Path) -> None:
    tool = make_write_thread_file("tid-1")
    with pytest.raises(ValueError):
        await tool.ainvoke({"path": "notes.txt", "content": "x"})


@pytest.mark.asyncio
async def test_read_thread_file_reads_stage_md(thread_dir: Path) -> None:
    tool = make_read_thread_file("tid-1")
    text = await tool.ainvoke({"path": "planner.md"})
    assert "# planner" in text.lower() or "planner" in text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_thread_files.py -v`  
Expected: FAIL with `ModuleNotFoundError` or import error for `tools.thread_files`

- [ ] **Step 3: Implement `tools/thread_files.py`**

```python
# tools/thread_files.py
"""Thread-scoped read/write tools bound to a thread_id."""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from app.services.thread_artifacts import lookup_thread_dir

_MAX_BYTES = 131072
_WRITE_NAMES_OK = {".py",}  # suffix check; manifest.json special-cased


def _thread_root(thread_id: str) -> Path:
    root = lookup_thread_dir(thread_id)
    if root is None:
        raise FileNotFoundError(f"no thread dir for {thread_id!r}")
    return root.resolve()


def resolve_scripts_path(thread_id: str, relative: str) -> Path:
    """Resolve a path under ``scripts/``; reject escapes."""
    if not relative or relative.startswith("/") or ".." in Path(relative).parts:
        raise ValueError("invalid scripts path")
    scripts = (_thread_root(thread_id) / "scripts").resolve()
    scripts.mkdir(parents=True, exist_ok=True)
    target = (scripts / relative).resolve()
    if not target.is_relative_to(scripts):
        raise ValueError("path escapes scripts/")
    return target


def resolve_thread_path(thread_id: str, relative: str) -> Path:
    """Resolve a path under the thread dir for reads."""
    if not relative or relative.startswith("/") or ".." in Path(relative).parts:
        raise ValueError("invalid thread path")
    root = _thread_root(thread_id)
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError("path escapes thread dir")
    return target


class WriteThreadFileInput(BaseModel):
    """Input for write_thread_file."""

    path: str = Field(description="Path relative to scripts/ (*.py or manifest.json)")
    content: str = Field(description="Full file contents to write")


class ReadThreadFileInput(BaseModel):
    """Input for read_thread_file."""

    path: str = Field(description="Path relative to the thread directory")
    max_bytes: int = Field(default=8192, ge=1, le=_MAX_BYTES)


def make_write_thread_file(thread_id: str) -> BaseTool:
    """Build write_thread_file closed over ``thread_id``."""

    @tool("write_thread_file", args_schema=WriteThreadFileInput)
    async def write_thread_file(path: str, content: str) -> str:
        """Write a Python module or manifest.json under this thread's scripts/."""
        name = Path(path).name
        if name == "manifest.json":
            if Path(path).name != path and Path(path) != Path("manifest.json"):
                # allow only top-level manifest.json under scripts/
                if path != "manifest.json":
                    raise ValueError("manifest.json must be at scripts/manifest.json")
        elif not path.endswith(".py"):
            raise ValueError("only *.py or manifest.json may be written")
        raw = content.encode("utf-8")
        if len(raw) > _MAX_BYTES:
            raise ValueError(f"content exceeds {_MAX_BYTES} bytes")
        target = resolve_scripts_path(thread_id, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"wrote scripts/{path} ({len(raw)} bytes)"

    return write_thread_file


def make_read_thread_file(thread_id: str) -> BaseTool:
    """Build read_thread_file closed over ``thread_id``."""

    @tool("read_thread_file", args_schema=ReadThreadFileInput)
    async def read_thread_file(path: str, max_bytes: int = 8192) -> str:
        """Read a file from this thread's artifact directory."""
        target = resolve_thread_path(thread_id, path)
        if not target.is_file():
            raise FileNotFoundError(path)
        return target.read_bytes()[:max_bytes].decode("utf-8", errors="replace")

    return read_thread_file
```

Tighten the manifest path check in implementation if the sample above is awkward: only `path == "manifest.json"` or `path.endswith(".py")` with no `..`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_thread_files.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/thread_files.py tests/test_thread_files.py
git commit -m "$(cat <<'EOF'
feat: add thread-scoped script read/write tools

EOF
)"
```

---

### Task 2: Executor registry defaults + bind thread_id

**Files:**
- Modify: `tools/registry.py`
- Modify: `agent/executor.py`
- Create: `tests/test_executor_tools_registry.py`

- [ ] **Step 1: Write failing registry test**

```python
# tests/test_executor_tools_registry.py
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.thread_artifacts import init_thread_artifacts
from tools.registry import DEFAULT_ALLOWED_TOOLS, get_executor_tools


def test_default_allowlist_includes_thread_file_tools() -> None:
    assert "write_thread_file" in DEFAULT_ALLOWED_TOOLS
    assert "read_thread_file" in DEFAULT_ALLOWED_TOOLS


def test_get_executor_tools_requires_thread_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HARNESS_THREADS_DIR", str(tmp_path))
    monkeypatch.delenv("EXECUTOR_TOOLS", raising=False)
    init_thread_artifacts("t", "tid-reg", plan=[])
    tools = get_executor_tools("tid-reg")
    names = {t.name for t in tools}
    assert "write_thread_file" in names
    assert "read_file" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_executor_tools_registry.py -v`  
Expected: FAIL (default string missing tools and/or signature)

- [ ] **Step 3: Update registry**

Change `DEFAULT_ALLOWED_TOOLS` to:

```python
DEFAULT_ALLOWED_TOOLS = "read_file,list_dir,write_thread_file,read_thread_file"
```

Change `get_executor_tools` to:

```python
def get_executor_tools(thread_id: str) -> list[BaseTool]:
    """Return executor tools; thread-scoped tools bound to ``thread_id``."""
    from tools.thread_files import make_read_thread_file, make_write_thread_file

    allowed = _allowlist()
    available = _executor_tool_map()
    # Replace placeholders with bound factories for thread tools
    available["write_thread_file"] = make_write_thread_file(thread_id)
    available["read_thread_file"] = make_read_thread_file(thread_id)
    missing = allowed - set(available)
    if missing:
        raise RuntimeError(f"Unknown tools in EXECUTOR_TOOLS: {sorted(missing)}")
    return [available[name] for name in sorted(allowed)]
```

Keep static builtins for `read_file` / `list_dir` / RAG. Do **not** put unbound write tools in `_ALL_TOOLS`.

Update `get_tool_by_name` for executor path: either require `(name, thread_id)` or resolve only static tools and have agents call factory map. Prefer:

```python
def get_tool_by_name(name: str, thread_id: str | None = None) -> BaseTool:
    if name in {"write_thread_file", "read_thread_file", "run_thread_script"}:
        if not thread_id:
            raise PermissionError(f"tool {name!r} requires thread_id")
        for tool in (
            get_executor_tools(thread_id)
            if name != "run_thread_script"
            else get_learner_tools(thread_id)
        ):
            if tool.name == name:
                return tool
        raise KeyError(name)
    # existing allow-list + static map for read_file etc.
    ...
```

Simpler approach for executor loop: build `tools = get_executor_tools(thread_id)` once and look up by name from that list inside `_run_tool_loop` instead of `get_tool_by_name`.

In `agent/executor.py`:

```python
tools = get_executor_tools(state["thread_id"])
tool_by_name = {t.name: t for t in tools}
# in loop:
tool = tool_by_name[name]
```

Update all `get_executor_tools()` call sites (executor + tests) to pass `thread_id`.

- [ ] **Step 4: Run registry + executor unit tests**

Run: `pytest tests/test_executor_tools_registry.py tests/test_executor.py -v`  
Expected: PASS (fix executor mocks if signature changed)

- [ ] **Step 5: Commit**

```bash
git add tools/registry.py agent/executor.py tests/test_executor_tools_registry.py tests/test_executor.py
git commit -m "$(cat <<'EOF'
feat: bind thread file tools into executor allow-list

EOF
)"
```

---

### Task 3: Manifest helpers

**Files:**
- Create: `tools/manifest.py`
- Create: `tests/test_manifest.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_manifest.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.manifest import ManifestEntry, load_manifest, require_entry


def test_load_manifest_empty_when_missing(tmp_path: Path) -> None:
    assert load_manifest(tmp_path / "scripts") == []


def test_load_manifest_parses_entries(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "manifest.json").write_text(
        json.dumps(
            {
                "entries": [
                    {"path": "a.py", "purpose": "check", "args": ["--x"]},
                ]
            }
        ),
        encoding="utf-8",
    )
    entries = load_manifest(scripts)
    assert entries == [
        ManifestEntry(path="a.py", purpose="check", args=["--x"])
    ]


def test_require_entry_rejects_unknown(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "manifest.json").write_text(
        json.dumps({"entries": [{"path": "a.py", "purpose": "p"}]}),
        encoding="utf-8",
    )
    with pytest.raises(PermissionError):
        require_entry(scripts, "b.py")
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_manifest.py -v`  
Expected: FAIL import

- [ ] **Step 3: Implement**

```python
# tools/manifest.py
"""Parse and validate scripts/manifest.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ManifestEntry:
    """One runnable script listed by the executor."""

    path: str
    purpose: str = ""
    args: list[str] = field(default_factory=list)


def load_manifest(scripts_dir: Path) -> list[ManifestEntry]:
    """Return entries from manifest.json, or [] if missing/invalid object."""
    path = scripts_dir / "manifest.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    raw = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []
    out: list[ManifestEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        rel = item.get("path")
        if not isinstance(rel, str) or not rel.endswith(".py"):
            continue
        if ".." in Path(rel).parts or rel.startswith("/"):
            continue
        purpose = item.get("purpose") if isinstance(item.get("purpose"), str) else ""
        args_raw = item.get("args") or []
        args = [str(a) for a in args_raw] if isinstance(args_raw, list) else []
        out.append(ManifestEntry(path=rel, purpose=purpose, args=args))
    return out


def require_entry(scripts_dir: Path, rel_path: str) -> ManifestEntry:
    """Return the manifest entry for ``rel_path`` or raise PermissionError."""
    for entry in load_manifest(scripts_dir):
        if entry.path == rel_path:
            return entry
    raise PermissionError(f"{rel_path!r} is not listed in manifest.json")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_manifest.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/manifest.py tests/test_manifest.py
git commit -m "$(cat <<'EOF'
feat: add scripts manifest loader for thread runs

EOF
)"
```

---

### Task 4: Docker S2 sandbox runner

**Files:**
- Create: `tools/sandbox_docker.py`
- Create: `tests/test_sandbox_docker.py`

- [ ] **Step 1: Write failing tests (mocked subprocess)**

```python
# tests/test_sandbox_docker.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tools.sandbox_docker import DockerRunResult, run_python_in_docker


def test_run_builds_secure_docker_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "a.py").write_text("print(1)\n", encoding="utf-8")

    completed = MagicMock()
    completed.returncode = 0
    completed.stdout = b"1\n"
    completed.stderr = b""

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        assert cmd[0] == "docker"
        assert "run" in cmd
        assert "--network=none" in cmd
        assert "--read-only" in cmd
        assert "--cap-drop=ALL" in cmd
        assert any(str(scripts.resolve()) in part for part in cmd)
        return completed

    monkeypatch.setattr("tools.sandbox_docker.subprocess.run", fake_run)
    result = run_python_in_docker(scripts, "a.py", args=[])
    assert result.exit_code == 0
    assert result.stdout.strip() == "1"
    assert result.status == "ok"


def test_docker_missing_hard_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "a.py").write_text("print(1)\n", encoding="utf-8")

    def boom(*_a, **_k):  # noqa: ANN001
        raise FileNotFoundError("docker")

    monkeypatch.setattr("tools.sandbox_docker.subprocess.run", boom)
    result = run_python_in_docker(scripts, "a.py", args=[])
    assert result.status == "error"
    assert "docker" in result.message.lower()


def test_timeout_sets_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess as sp

    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "a.py").write_text("print(1)\n", encoding="utf-8")

    def boom(*_a, **_k):  # noqa: ANN001
        raise sp.TimeoutExpired(cmd="docker", timeout=1)

    monkeypatch.setattr("tools.sandbox_docker.subprocess.run", boom)
    result = run_python_in_docker(scripts, "a.py", args=[], timeout_seconds=1)
    assert result.status == "error"
    assert result.exit_code is None
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_sandbox_docker.py -v`  
Expected: FAIL import

- [ ] **Step 3: Implement runner**

```python
# tools/sandbox_docker.py
"""Docker S2 sandbox for thread script execution."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DockerRunResult:
    """Outcome of a sandboxed script run."""

    status: str  # ok | error
    exit_code: int | None
    stdout: str
    stderr: str
    message: str = ""


def _truncate(raw: bytes, limit: int) -> str:
    return raw[:limit].decode("utf-8", errors="replace")


def run_python_in_docker(
    scripts_dir: Path,
    relative_py: str,
    *,
    args: list[str] | None = None,
    timeout_seconds: float | None = None,
) -> DockerRunResult:
    """Run ``python <relative_py>`` with scripts_dir mounted read-only."""
    scripts = scripts_dir.resolve()
    target = (scripts / relative_py).resolve()
    if not target.is_relative_to(scripts) or not target.is_file():
        return DockerRunResult(
            status="error",
            exit_code=None,
            stdout="",
            stderr="",
            message="script path invalid or missing",
        )
    if not relative_py.endswith(".py") or ".." in Path(relative_py).parts:
        return DockerRunResult(
            status="error",
            exit_code=None,
            stdout="",
            stderr="",
            message="only relative .py scripts allowed",
        )

    docker_bin = os.getenv("HARNESS_DOCKER_BIN", "docker").strip() or "docker"
    image = os.getenv("HARNESS_SCRIPT_IMAGE", "python:3.12-slim").strip()
    timeout = timeout_seconds
    if timeout is None:
        timeout = float(os.getenv("HARNESS_SCRIPT_TIMEOUT_SECONDS", "30"))
    out_cap = int(os.getenv("HARNESS_SCRIPT_OUTPUT_BYTES", "32768"))
    argv = [
        docker_bin,
        "run",
        "--rm",
        "--network=none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,size=64m",
        "--cap-drop=ALL",
        "--security-opt",
        "no-new-privileges",
        "--memory=256m",
        "--cpus=1",
        "--workdir",
        "/workspace",
        "-v",
        f"{scripts}:/workspace:ro",
        image,
        "python",
        relative_py,
        *(args or []),
    ]
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return DockerRunResult(
            status="error",
            exit_code=None,
            stdout="",
            stderr="",
            message="Docker CLI not found; install Docker to run thread scripts",
        )
    except subprocess.TimeoutExpired:
        return DockerRunResult(
            status="error",
            exit_code=None,
            stdout="",
            stderr="",
            message=f"script timed out after {timeout}s",
        )
    except OSError as exc:
        return DockerRunResult(
            status="error",
            exit_code=None,
            stdout="",
            stderr="",
            message=f"Docker run failed: {exc}",
        )

    return DockerRunResult(
        status="ok",
        exit_code=completed.returncode,
        stdout=_truncate(completed.stdout or b"", out_cap),
        stderr=_truncate(completed.stderr or b"", out_cap),
        message="",
    )
```

Note: daemon-down still returns `status=ok` with non-zero exit from docker CLI — document that learner treats stderr; optionally detect `Cannot connect` in stderr and set `status=error`. Prefer:

```python
if completed.returncode != 0 and b"Cannot connect" in (completed.stderr or b""):
    return DockerRunResult(status="error", ...)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_sandbox_docker.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/sandbox_docker.py tests/test_sandbox_docker.py
git commit -m "$(cat <<'EOF'
feat: add Docker S2 runner for thread scripts

EOF
)"
```

---

### Task 5: `run_thread_script` + learner tool registry

**Files:**
- Create: `tools/script_tools.py`
- Modify: `tools/registry.py` (`get_learner_tools`)
- Create: `tests/test_script_tools.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_script_tools.py
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.thread_artifacts import init_thread_artifacts
from tools.registry import get_learner_tools
from tools.sandbox_docker import DockerRunResult


@pytest.fixture
def thread_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HARNESS_THREADS_DIR", str(tmp_path))
    root = init_thread_artifacts("s", "tid-script", plan=[])
    scripts = root / "scripts"
    scripts.mkdir(exist_ok=True)
    (scripts / "ok.py").write_text("print('hi')\n", encoding="utf-8")
    (scripts / "manifest.json").write_text(
        json.dumps({"entries": [{"path": "ok.py", "purpose": "smoke"}]}),
        encoding="utf-8",
    )
    return root


@pytest.mark.asyncio
async def test_run_thread_script_uses_docker(
    thread_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = {t.name: t for t in get_learner_tools("tid-script")}
    assert "write_thread_file" not in tools
    assert "run_thread_script" in tools

    with patch(
        "tools.script_tools.run_python_in_docker",
        return_value=DockerRunResult(
            status="ok", exit_code=0, stdout="hi\n", stderr=""
        ),
    ) as mocked:
        out = await tools["run_thread_script"].ainvoke({"path": "ok.py"})
    mocked.assert_called_once()
    assert "hi" in out


@pytest.mark.asyncio
async def test_run_rejects_unlisted(
    thread_dir: Path,
) -> None:
    tools = {t.name: t for t in get_learner_tools("tid-script")}
    with pytest.raises(PermissionError):
        await tools["run_thread_script"].ainvoke({"path": "other.py"})
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_script_tools.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement tool + registry**

```python
# tools/script_tools.py
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

    path: str = Field(description="Scripts-relative .py path listed in manifest.json")


def make_run_thread_script(thread_id: str) -> BaseTool:
    """Build run_thread_script closed over ``thread_id``."""

    @tool("run_thread_script", args_schema=RunThreadScriptInput)
    async def run_thread_script(path: str) -> str:
        """Run a manifest-listed script in the Docker sandbox; return exit/stdout/stderr."""
        root = lookup_thread_dir(thread_id)
        if root is None:
            raise FileNotFoundError(f"no thread dir for {thread_id!r}")
        scripts = root / "scripts"
        entry = require_entry(scripts, path)
        result = run_python_in_docker(scripts, entry.path, args=list(entry.args))
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
```

In `tools/registry.py`:

```python
def get_learner_tools(thread_id: str) -> list[BaseTool]:
    """Tools the learner may call (read + sandboxed run only)."""
    from tools.script_tools import make_run_thread_script
    from tools.thread_files import make_read_thread_file

    return [
        make_read_thread_file(thread_id),
        make_run_thread_script(thread_id),
    ]
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_script_tools.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/script_tools.py tools/registry.py tests/test_script_tools.py
git commit -m "$(cat <<'EOF'
feat: add learner run_thread_script tool with manifest gate

EOF
)"
```

---

### Task 6: Learner tool loop + state

**Files:**
- Modify: `agent/learner.py`
- Modify: `graph/state.py`
- Modify: `app/services/thread_artifacts.py` (`_stage_keys` for learner)
- Create / modify: `tests/test_learner.py` (or `tests/test_learner_tools.py`)

- [ ] **Step 1: Add state field + failing learner loop test**

In `graph/state.py` add:

```python
learner_tool_calls: NotRequired[list[ToolCallRecord]]
script_runs: NotRequired[list[dict[str, object]]]
```

Test sketch (mirror `tests/test_executor.py` tool loop):

```python
@pytest.mark.asyncio
async def test_learner_runs_tool_then_summarizes(monkeypatch):
    # patch get_llm / get_learner_tools / call_llm
    # first AIMessage has tool_calls=[{name: run_thread_script, ...}]
    # second returns LearningResult
    # assert state patch includes learner_tool_calls
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_learner.py -v` (or new file)  
Expected: FAIL on missing tool loop behavior

- [ ] **Step 3: Implement learner loop**

Refactor `learner_agent` to:

1. Load manifest summary via `lookup_thread_dir` + `load_manifest` for the human prompt.
2. `tools = get_learner_tools(state["thread_id"])`; bind to LLM.
3. Bounded loop (`MAX_TOOL_ITERATIONS = 5`) identical pattern to executor (audit `node="learner"`).
4. Second phase: `with_structured_output(LearningResult)` + existing summarize — extend human message with tool outputs already in history.
5. Return `learner_tool_calls` records; optionally parse JSON tool results into `script_runs`.

Update `thread_artifacts._stage_keys("learner")` to include `learner_tool_calls` and `script_runs`.

- [ ] **Step 4: Run learner + graph smoke tests**

Run: `pytest tests/test_learner.py tests/test_graph.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/learner.py graph/state.py app/services/thread_artifacts.py tests/test_learner.py
git commit -m "$(cat <<'EOF'
feat: give learner a Docker script tool loop for review

EOF
)"
```

---

### Task 7: Prompts

**Files:**
- Modify: `config/prompts.yaml`
- Create: `tests/test_executor_prompt_scripts.py` (optional smoke)

- [ ] **Step 1: Extend `executor.system`**

Append condensed architect rules:

```yaml
    Prefer Python over LLM reasoning whenever a task is deterministic
    (known rules / algorithms). Classify work as Deterministic, LLM
    Reasoning, or Hybrid. For Deterministic or Hybrid steps, write modular
    production Python under this thread's scripts/ directory via
    write_thread_file, and keep scripts/manifest.json updated for any
    script the learner should run. Do not execute scripts yourself.
    Use LLM only for semantic understanding, generation, or ambiguous
    decisions. Inspect the workspace with read tools when needed.
```

- [ ] **Step 2: Extend `learner.system`**

```yaml
    When the thread has scripts/manifest.json entries, call
    run_thread_script for relevant entries and use exit codes / stdout /
    stderr as verification evidence before finalizing the verdict.
    If Docker/sandbox returns an error (unavailable daemon, timeout),
    treat that as a verification gap — do not pass solely on untested claims.
```

- [ ] **Step 3: Smoke-load prompts**

```python
from config.prompts import PROMPTS

def test_executor_prompt_mentions_scripts() -> None:
    text = PROMPTS["executor"]["system"]
    assert "manifest" in text.lower() or "scripts/" in text
```

Run: `pytest tests/test_executor_prompt_scripts.py -v`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add config/prompts.yaml tests/test_executor_prompt_scripts.py
git commit -m "$(cat <<'EOF'
docs: teach executor/learner thread-script workflow in prompts

EOF
)"
```

---

### Task 8: Docs + security + history

**Files:**
- Modify: `docs/IMPLEMENTATION.md` (Executor Tools table, env vars)
- Modify: `docs/SECURITY.md` (tool risk rows)
- Create: `docs/histories/2026-07/YYYYMMDD-HHmm-executor-thread-scripts.md`
- Optionally mark: `docs/PLANS_GUIDE.md` example as addressed (skip unless needed)

- [ ] **Step 1: Update IMPLEMENTATION.md**

Add tools:

| Tool | Default | Description |
|------|---------|-------------|
| `write_thread_file` | Yes | Write `scripts/*.py` or `manifest.json` for current thread |
| `read_thread_file` | Yes | Read under `app/threads/<slug>/` |
| `run_thread_script` | Learner only | Docker S2 run of manifest entry |

Env vars:

| Var | Default | Purpose |
|-----|---------|---------|
| `HARNESS_SCRIPT_IMAGE` | `python:3.12-slim` | Docker image |
| `HARNESS_SCRIPT_TIMEOUT_SECONDS` | `30` | Per-script timeout |
| `HARNESS_SCRIPT_OUTPUT_BYTES` | `32768` | Stdout/stderr cap |
| `HARNESS_DOCKER_BIN` | `docker` | CLI binary |

Note: no host-Python fallback; Docker required for learner script verify.

- [ ] **Step 2: Update SECURITY.md**

| Tool | Risk | Enable |
|------|------|--------|
| `write_thread_file` | Medium (thread-scoped) | Default with feature |
| `run_thread_script` | High→mitigated by Docker S2 | Learner only |

State Docker flags and no host fallback.

- [ ] **Step 3: History entry** per `docs/HISTORY_GUIDE.md`

- [ ] **Step 4: Run `graphify update .`** after code files settle

- [ ] **Step 5: Commit**

```bash
git add docs/IMPLEMENTATION.md docs/SECURITY.md docs/histories/2026-07/*executor-thread-scripts.md
git commit -m "$(cat <<'EOF'
docs: document thread script tools and Docker sandbox

EOF
)"
```

---

### Task 9 (optional): Real Docker integration marker

**Files:**
- Create: `tests/test_sandbox_docker_integration.py`

```python
import os
import shutil

import pytest

pytestmark = pytest.mark.docker

@pytest.mark.skipif(shutil.which("docker") is None, reason="docker missing")
def test_real_docker_print(tmp_path):
    ...
```

Run only when explicitly selected: `pytest -m docker`.

Skip this task if the team wants mocks-only for now.

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Write under `scripts/` only | 1 |
| `manifest.json` contract | 1, 3 |
| Executor default tools | 2 |
| Bind thread_id from state | 2, 5, 6 |
| Architect prompt always-on | 7 |
| Learner tool loop Approach 2 | 6 |
| `run_thread_script` + manifest gate | 5 |
| Docker S2, no host fallback | 4 |
| `learner_tool_calls` / artifacts | 6 |
| SECURITY + IMPLEMENTATION | 8 |
| Phase D not implemented | (explicit non-goal; no task) |

## Self-review notes

- No workspace-wide `write_file`.
- `get_executor_tools(thread_id)` signature change must update mocks in `tests/test_executor.py`.
- Learner must not receive `write_thread_file`.
- Commit steps assume user allows commits; if commits are deferred, still land tests green per task.

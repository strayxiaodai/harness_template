"""Docker S2 sandbox for thread script execution."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DockerRunResult:
    """Outcome of a sandboxed script run."""

    status: str
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
    if (
        not relative_py.endswith(".py")
        or ".." in Path(relative_py).parts
        or relative_py.startswith("/")
    ):
        return DockerRunResult(
            status="error",
            exit_code=None,
            stdout="",
            stderr="",
            message="only relative .py scripts allowed",
        )
    target = (scripts / relative_py).resolve()
    if not target.is_relative_to(scripts) or not target.is_file():
        return DockerRunResult(
            status="error",
            exit_code=None,
            stdout="",
            stderr="",
            message="script path invalid or missing",
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

    stderr_text = _truncate(completed.stderr or b"", out_cap)
    if completed.returncode != 0 and "Cannot connect" in stderr_text:
        return DockerRunResult(
            status="error",
            exit_code=completed.returncode,
            stdout=_truncate(completed.stdout or b"", out_cap),
            stderr=stderr_text,
            message="Docker daemon unavailable",
        )

    return DockerRunResult(
        status="ok",
        exit_code=completed.returncode,
        stdout=_truncate(completed.stdout or b"", out_cap),
        stderr=stderr_text,
        message="",
    )

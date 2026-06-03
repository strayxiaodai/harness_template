# Enterprise LangGraph Harness Template

This document describes a reusable Python service template for building
multi-agent workflows with LangGraph and exposing them through FastAPI.

The template includes:

- LangGraph orchestration with a Plan -> Do -> Check -> Action loop
- Peer specialist agents for planning, execution, review, and refinement
- A pluggable LLM provider layer for OpenAI, Anthropic, and Ollama
- FastAPI endpoints for invoke, stream, and resume
- An optional human-in-the-loop mode that pauses after every node
- A round budget (3 by default) that bounds the refinement loop
- Wall-clock request timeouts for `/run` and `/resume`
- LLM retry/backoff around transient provider failures
- Durable audit logging for routing decisions and human overrides
- Postgres-backed checkpoints with a lifespan-managed saver
- Docker Compose with Postgres and Redis healthchecks
- Agent system prompts in `config/prompts.yaml` (static copy only)

The examples below are intentionally small. They are meant to give the
repository a sound starting shape, not to replace production hardening.

## Project Layout

```bash
enterprise-langgraph-harness/
├── app/
│   ├── api/
│   │   ├── schemas.py
│   │   └── server.py
│   ├── agents/
│   │   ├── actioner.py
│   │   ├── executor.py
│   │   ├── planner.py
│   │   └── reviewer.py
│   ├── audit/
│   │   └── logger.py
│   ├── graph/
│   │   ├── builder.py
│   │   ├── routing.py
│   │   ├── schemas.py
│   │   └── state.py
│   ├── llm/
│   │   ├── providers.py
│   │   └── retry.py
│   ├── memory/
│   │   └── checkpoint.py
│   └── tools/
│       ├── code_tools.py
│       ├── registry.py
│       └── shell_tools.py
├── config/
│   ├── __init__.py
│   ├── prompts.py          # loads prompts.yaml into PROMPTS
│   ├── prompts.yaml        # system prompts per agent
│   └── settings.yaml
├── docker/
│   └── Dockerfile
├── migrations/
│   └── 001_create_agent_audit_log.sql
├── tests/
│   ├── test_compose_integration.py
│   └── test_graph.py
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## Architecture

The service receives a task and runs a Plan -> Do -> Check -> Action loop:

```text
planner -> executor -> reviewer -> actioner
```

After `actioner`, exactly one of three things happens:

- `finish` if the reviewer approved the result or the round budget is hit
- `executor` to redo the work with the same plan
- `planner` to revise the plan first

When `human_in_the_loop=false` (the default), the graph keeps running this
loop until the reviewer approves or the round budget is reached.
`max_rounds` defaults to 3 and is configurable per request, bounded to
`[1, 20]`. One round = one full `planner -> executor -> reviewer -> actioner` pass; the actioner increments the counter at the end of each
round.

Human-in-the-loop is an orthogonal mode. When the client sets
`human_in_the_loop=true` on `/run`, the graph pauses after every node
(`planner`, `executor`, `reviewer`, `actioner`) so a human can inspect what
just happened before the next node runs. The round budget still applies in
HITL mode.

Postgres holds durable LangGraph checkpoints so paused threads survive
restarts and multiple API workers. Redis is available for queues, pub/sub
streaming, cancellation flags, and short-lived coordination.

The `executor` is the only agent that can call tools. It runs a bounded
inner tool-calling loop, then summarizes its trajectory into the typed
`ExecutorResult` the reviewer consumes. Tools are loaded from an
allow-list (`EXECUTOR_TOOLS`) and every call is recorded in
`agent_audit_log`.

## Structured Schemas

Planner, executor, and reviewer all return structured output so downstream
nodes never have to parse free-form prose. The planner produces the `plan`
list that flows into the executor; the executor produces a structured
result with summary, changes, risks, and verification; the reviewer
produces a verdict and `suggested_step` that the actioner reads.

```python
# app/graph/schemas.py
from typing import Literal

from pydantic import BaseModel, Field


class PlanResult(BaseModel):
    """Structured planner output written to state.plan."""

    steps: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)


class ExecutorResult(BaseModel):
    """Structured executor output consumed by the reviewer."""

    summary: str = Field(min_length=1)
    changes: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    verification: list[str] = Field(default_factory=list)


class ReviewResult(BaseModel):
    """Structured reviewer output consumed by the actioner."""

    verdict: Literal["pass", "fail"]
    reason: str = Field(min_length=1)
    suggested_step: Literal["planner", "executor", "finish"]
```

## Prompts

Put **system prompts** (the stable “who you are” instructions) in
`config/prompts.yaml`. Keep **human messages** in the agent code as ordinary
f-strings — they are mostly state (`task`, `plan`, review feedback) and are
easier to read next to the node logic.

```python
# config/prompts.py
from pathlib import Path
import yaml

with Path(__file__).parent.joinpath("prompts.yaml").open() as f:
    PROMPTS = yaml.safe_load(f)
```

```python
from app.config.prompts import PROMPTS

SystemMessage(content=PROMPTS["planner"]["system"].strip())
HumanMessage(
    content=(
        f"Task: {state['task']}\n"
        f"Current plan: {state['plan']}\n"
        f"Prior review feedback: {feedback}"
    )
)
```

The executor also has a static `summarize` line in YAML for the second LLM
call after the tool loop.

## Core State

The `messages` field uses LangGraph's `add_messages` reducer, so nodes return
only the new messages they produce instead of rebuilding the full list.

```python
# app/graph/state.py
from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ExecutionRecord(TypedDict):
    """Serialized form of an ExecutorResult stored in state."""

    summary: str
    changes: list[str]
    risks: list[str]
    verification: list[str]


class ReviewRecord(TypedDict):
    """Serialized form of a ReviewResult stored in the graph state."""

    verdict: str
    reason: str
    suggested_step: str


class ToolCallRecord(TypedDict):
    """Compact record of one tool call made by the executor."""

    iteration: int
    tool: str
    args: dict[str, object]
    status: str


class AgentState(TypedDict):
    """Shared state passed between LangGraph nodes.

    ``thread_id`` is intentionally duplicated from the LangGraph runtime
    config (``config["configurable"]["thread_id"]``). Nodes receive the
    state but not the config, so storing the id here lets audit logging
    and prompt construction reference it without threading the config
    through every helper.
    """

    thread_id: str
    task: str
    messages: Annotated[list[BaseMessage], add_messages]
    plan: list[str]
    rounds: int
    max_rounds: int
    role: str
    result: NotRequired[str]
    execution: NotRequired[ExecutionRecord]
    approved: bool
    review: NotRequired[ReviewRecord]
    refine_from: NotRequired[str]
    tool_calls: NotRequired[list[ToolCallRecord]]
    human_in_the_loop: bool
```

## Routing

The graph always runs `planner -> executor -> reviewer -> actioner`. The
only conditional edge is after `actioner`, which chooses the next step
using the reviewer's structured suggestion and the round budget.

```python
# app/graph/routing.py
from typing import Literal

from app.graph.state import AgentState

ActionRoute = Literal["executor", "planner", "finish"]

DEFAULT_MAX_ROUNDS = 3


def route_after_action(state: AgentState) -> ActionRoute:
    """Finish or refine after the action step."""
    if state.get("approved"):
        return "finish"

    if state["rounds"] >= state.get("max_rounds", DEFAULT_MAX_ROUNDS):
        return "finish"

    refine_from = state.get("refine_from", "executor")

    if refine_from == "planner":
        return "planner"

    if refine_from == "finish":
        return "finish"

    return "executor"
```

## Agent Nodes

Every node is async. Each node returns only the fields it wants to update.
With the `add_messages` reducer, message lists are appended automatically.

```python
# app/agents/planner.py
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.config.prompts import PROMPTS
from app.graph.schemas import PlanResult
from app.graph.state import AgentState
from app.llm.providers import get_llm
from app.llm.retry import call_llm


async def planner_agent(state: AgentState) -> dict[str, object]:
    """Draft or revise the implementation plan."""
    llm = get_llm()
    structured = llm.with_structured_output(PlanResult)

    review = state.get("review")
    feedback = review["reason"] if review else "(none)"

    plan: PlanResult = await call_llm(
        structured,
        [
            SystemMessage(content=PROMPTS["planner"]["system"].strip()),
            HumanMessage(
                content=(
                    f"Task: {state['task']}\n"
                    f"Current plan: {state['plan']}\n"
                    f"Prior review feedback: {feedback}"
                )
            ),
        ],
    )

    return {
        "role": "planner",
        "plan": plan.steps,
        "messages": [
            AIMessage(
                content=f"Plan rationale: {plan.rationale}\nSteps: {plan.steps}"
            )
        ],
    }
```

```python
# app/agents/executor.py
import json
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.audit.logger import write_audit_event
from app.config.prompts import PROMPTS
from app.graph.schemas import ExecutorResult
from app.graph.state import AgentState, ToolCallRecord
from app.llm.providers import get_llm
from app.llm.retry import call_llm
from app.tools.registry import get_executor_tools, get_tool_by_name

MAX_TOOL_ITERATIONS = 5


def _tool_output_to_content(output: Any) -> str:
    """Serialize a tool return value to a ToolMessage content string."""
    if isinstance(output, str):
        return output
    if isinstance(output, (list, dict, int, float, bool)) or output is None:
        return json.dumps(output, default=str)
    return str(output)


async def _run_tool_loop(
    state: AgentState,
    trajectory: list[BaseMessage],
    records: list[ToolCallRecord],
) -> list[BaseMessage]:
    """Run a bounded tool-calling loop and return the working history.

    ``trajectory`` accumulates messages destined for the graph state via
    the ``add_messages`` reducer. ``records`` accumulates compact
    ToolCallRecords for the reviewer and the audit log.
    """
    tools = get_executor_tools()
    llm = get_llm().bind_tools(tools)

    prior_review = state.get("review")
    feedback = prior_review["reason"] if prior_review else "(none)"

    history: list[BaseMessage] = [
        SystemMessage(content=PROMPTS["executor"]["system"].strip()),
        HumanMessage(
            content=(
                f"Task: {state['task']}\n"
                f"Plan: {state['plan']}\n"
                f"Prior review feedback: {feedback}"
            )
        ),
    ]

    for iteration in range(MAX_TOOL_ITERATIONS):
        response: AIMessage = await call_llm(llm, history)
        trajectory.append(response)
        history.append(response)

        if not response.tool_calls:
            return history

        for call in response.tool_calls:
            name = call["name"]
            args = call.get("args", {}) or {}
            try:
                tool = get_tool_by_name(name)
                output = await tool.ainvoke(args)
                content = _tool_output_to_content(output)
                status = "ok"
            except Exception as exc:
                content = f"error: {exc}"
                status = "error"

            records.append(
                ToolCallRecord(
                    iteration=iteration,
                    tool=name,
                    args=args,
                    status=status,
                )
            )
            await write_audit_event(
                thread_id=state["thread_id"],
                round_number=state["rounds"] + 1,
                node="executor",
                event_type="tool_call",
                payload={
                    "iteration": iteration,
                    "tool": name,
                    "args": args,
                    "status": status,
                },
            )

            tool_msg = ToolMessage(content=content, tool_call_id=call["id"])
            trajectory.append(tool_msg)
            history.append(tool_msg)

    return history


async def executor_agent(state: AgentState) -> dict[str, object]:
    """Run a bounded tool-calling loop, then summarize as ExecutorResult.

    Phase 1: bind the executor tools and let the model call them until it
    stops asking for tools or hits ``MAX_TOOL_ITERATIONS``.

    Phase 2: pass the resulting trajectory to ``with_structured_output``
    to produce the typed ExecutorResult the reviewer consumes. ``bind_tools``
    and ``with_structured_output`` use the same underlying tool-calling
    mechanism, so the two phases must use separate model instances.
    """
    trajectory: list[BaseMessage] = []
    records: list[ToolCallRecord] = []
    history = await _run_tool_loop(state, trajectory, records)

    structured = get_llm().with_structured_output(ExecutorResult)
    execution: ExecutorResult = await call_llm(
        structured,
        history
        + [
            HumanMessage(
                content=PROMPTS["executor"]["summarize"].strip()
            )
        ],
    )

    return {
        "role": "executor",
        "execution": execution.model_dump(),
        "result": execution.summary,
        "tool_calls": records,
        "messages": trajectory
        + [AIMessage(content=f"Executor summary: {execution.summary}")],
    }
```

```python
# app/agents/reviewer.py
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.config.prompts import PROMPTS
from app.graph.schemas import ReviewResult
from app.graph.state import AgentState
from app.llm.providers import get_llm
from app.llm.retry import call_llm


async def reviewer_agent(state: AgentState) -> dict[str, object]:
    """Check the current result and return a structured verdict."""
    llm = get_llm()
    structured = llm.with_structured_output(ReviewResult)
    execution = state.get("execution") or {}

    review: ReviewResult = await call_llm(
        structured,
        [
            SystemMessage(content=PROMPTS["reviewer"]["system"].strip()),
            HumanMessage(
                content=(
                    f"Task: {state['task']}\n"
                    f"Plan: {state['plan']}\n"
                    f"Executor summary: {execution.get('summary', '')}\n"
                    f"Changes: {execution.get('changes', [])}\n"
                    f"Risks: {execution.get('risks', [])}\n"
                    f"Verification: {execution.get('verification', [])}"
                )
            ),
        ],
    )

    return {
        "role": "reviewer",
        "approved": review.verdict == "pass",
        "review": review.model_dump(),
        "messages": [
            AIMessage(content=f"Review {review.verdict}: {review.reason}")
        ],
    }
```

```python
# app/agents/actioner.py
from app.audit.logger import write_audit_event
from app.graph.state import AgentState


async def actioner_agent(state: AgentState) -> dict[str, object]:
    """Decide where the refinement loop should resume.

    The actioner does not redo the work. It increments the round counter,
    reads the reviewer's structured suggestion, and updates `refine_from`.
    Routing is then driven by `route_after_action`.
    """
    review = state.get("review")
    suggestion = "finish" if review is None else review["suggested_step"]
    next_round = state["rounds"] + 1

    await write_audit_event(
        thread_id=state["thread_id"],
        round_number=next_round,
        node="actioner",
        event_type="route_decision",
        payload={"suggested_step": suggestion, "approved": state["approved"]},
    )

    return {
        "role": "actioner",
        "rounds": next_round,
        "refine_from": suggestion,
    }
```

## Executor Tools

Only the executor can call tools. Planner, reviewer, and actioner are
deliberately tool-free so the loop stays cheap and predictable.

Tools are LangChain `BaseTool` instances. Each has a typed Pydantic input
schema so arguments coming back from the model are validated before
execution. The registry enforces an allow-list driven by the
`EXECUTOR_TOOLS` environment variable, so granting a new capability to the
executor is a deployment-time decision, not a code change.

```python
# app/tools/code_tools.py
from pathlib import Path

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class ReadFileInput(BaseModel):
    """Input schema for the read_file tool."""

    path: str = Field(
        min_length=1,
        description="Workspace-relative path to read.",
    )
    max_bytes: int = Field(
        default=8192,
        ge=1,
        le=131072,
        description="Cap on bytes returned.",
    )


@tool("read_file", args_schema=ReadFileInput)
async def read_file(path: str, max_bytes: int = 8192) -> str:
    """Read up to ``max_bytes`` bytes from a workspace file."""
    workspace = Path.cwd().resolve()
    target = (workspace / path).resolve()
    if not target.is_relative_to(workspace):
        raise ValueError("path escapes the workspace")
    if not target.is_file():
        raise FileNotFoundError(path)
    return target.read_bytes()[:max_bytes].decode("utf-8", errors="replace")


class ListDirInput(BaseModel):
    """Input schema for the list_dir tool."""

    path: str = Field(
        default=".",
        description="Workspace-relative directory.",
    )


@tool("list_dir", args_schema=ListDirInput)
async def list_dir(path: str = ".") -> list[str]:
    """List entries inside a workspace directory."""
    workspace = Path.cwd().resolve()
    target = (workspace / path).resolve()
    if not target.is_relative_to(workspace) or not target.is_dir():
        raise ValueError("invalid directory")
    return sorted(p.name for p in target.iterdir())
```

```python
# app/tools/registry.py
import os

from langchain_core.tools import BaseTool

from app.tools.code_tools import list_dir, read_file

_ALL_TOOLS: dict[str, BaseTool] = {
    read_file.name: read_file,
    list_dir.name: list_dir,
}

DEFAULT_ALLOWED_TOOLS = "read_file,list_dir"


def _allowlist() -> set[str]:
    """Read EXECUTOR_TOOLS (comma-separated). Default: read-only tools."""
    raw = os.getenv("EXECUTOR_TOOLS", DEFAULT_ALLOWED_TOOLS)
    return {name.strip() for name in raw.split(",") if name.strip()}


def get_executor_tools() -> list[BaseTool]:
    """Return the tools the executor is allowed to call."""
    allowed = _allowlist()
    missing = allowed - set(_ALL_TOOLS)
    if missing:
        raise RuntimeError(
            f"Unknown tools in EXECUTOR_TOOLS: {sorted(missing)}"
        )
    return [_ALL_TOOLS[name] for name in sorted(allowed)]


def get_tool_by_name(name: str) -> BaseTool:
    """Look up a tool by name. Raises if missing or not allow-listed."""
    if name not in _allowlist():
        raise PermissionError(f"tool {name!r} is not in the allow-list")
    return _ALL_TOOLS[name]
```

`app/tools/shell_tools.py` is intentionally left as a placeholder. Shell
tools should never be added to `DEFAULT_ALLOWED_TOOLS`; require an explicit
`EXECUTOR_TOOLS=read_file,list_dir,run_shell` opt-in, sandbox the
subprocess, and add per-tool guardrails (command allow-list, timeout,
output cap) before enabling them.

### Tool-Calling Contract

- The executor runs at most `MAX_TOOL_ITERATIONS` (default `5`) tool
rounds. If the model still wants to call tools after the cap, the loop
exits and the structured-summary phase runs anyway, using whatever
evidence was gathered.
- Each tool call writes an `event_type="tool_call"` audit row with the
tool name, arguments, and `ok`/`error` status. Failed calls do not
abort the loop; the error string is fed back to the model as the
`ToolMessage` content so it can react.
- Tool outputs become `ToolMessage` content. Non-string outputs are
serialized with `json.dumps`.
- The reviewer sees the executor's tool trajectory through
`state["messages"]` and the compact `state["tool_calls"]` list, so it
can fail a result that ignored a clearly relevant tool output.

## Graph Builder

The builder exposes a factory. Compilation happens once at app startup. Two
compiled graphs are produced: one that runs end-to-end (auto) and one that
pauses after every node for human review (step). Both share the same
checkpointer so a thread can be inspected at any time.

```python
# app/graph/builder.py
from langgraph.graph import END, START, StateGraph

from app.agents.actioner import actioner_agent
from app.agents.executor import executor_agent
from app.agents.planner import planner_agent
from app.agents.reviewer import reviewer_agent
from app.graph.routing import route_after_action
from app.graph.state import AgentState

HITL_PAUSE_NODES: list[str] = [
    "planner",
    "executor",
    "reviewer",
    "actioner",
]


def create_workflow() -> StateGraph:
    """Create the uncompiled LangGraph workflow."""
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_agent)
    graph.add_node("executor", executor_agent)
    graph.add_node("reviewer", reviewer_agent)
    graph.add_node("actioner", actioner_agent)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "reviewer")
    graph.add_edge("reviewer", "actioner")

    graph.add_conditional_edges(
        "actioner",
        route_after_action,
        {
            "executor": "executor",
            "planner": "planner",
            "finish": END,
        },
    )

    return graph


def compile_with_checkpointer(
    checkpointer: object, *, human_in_the_loop: bool = False
) -> object:
    """Compile the workflow with a checkpointer.

    When `human_in_the_loop` is True, the compiled graph pauses after every
    node so a human can inspect state before the next node runs.
    """
    workflow = create_workflow()
    if human_in_the_loop:
        return workflow.compile(
            checkpointer=checkpointer,
            interrupt_after=HITL_PAUSE_NODES,
        )
    return workflow.compile(checkpointer=checkpointer)
```

## Checkpointer Lifespan

Persistent checkpoints are required for any resume flow. The saver and the
audit pool both live for the lifetime of the FastAPI app via a lifespan
context. Both compiled graphs are stored on `app.state`, and the audit
module is bound to the same pool so audit writes never open a per-call
connection.

```python
# app/memory/checkpoint.py
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from app.audit.logger import set_audit_pool
from app.graph.builder import compile_with_checkpointer


@asynccontextmanager
async def graph_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the checkpointer and audit pool, then compile both graphs."""
    database_url = os.environ["DATABASE_URL"]

    async with AsyncConnectionPool(database_url, open=False) as audit_pool:
        await audit_pool.open()
        set_audit_pool(audit_pool)

        async with AsyncPostgresSaver.from_conn_string(database_url) as saver:
            await saver.setup()
            app.state.graph_auto = compile_with_checkpointer(
                saver, human_in_the_loop=False
            )
            app.state.graph_step = compile_with_checkpointer(
                saver, human_in_the_loop=True
            )
            try:
                yield
            finally:
                set_audit_pool(None)
```

## Human-In-The-Loop Option

Human review is optional and triggered per request. When the client sets
`human_in_the_loop=true` on `/run`, the server uses the graph compiled with
`interrupt_after=["planner", "executor", "reviewer", "actioner"]`. The graph
runs one node at a time:

1. Client calls `POST /run` with a `thread_id` and `human_in_the_loop=true`.
2. `planner` runs. The graph commits the planner's output to the
  checkpoint and pauses. `ainvoke` returns.
3. The server inspects the snapshot. `snapshot.next` is `("executor",)`,
  so the response reports `status="awaiting_human"` and `next_action`.
4. The client previews the latest message (or `result`) and posts
  `POST /resume` with the same `thread_id`.
5. The graph runs `executor`, pauses again, and so on through `reviewer`
  and `actioner`. After `actioner`, routing decides whether to continue
   the next loop iteration or finish.

The human does not need to send a decision payload to continue. To
override what a node produced (for example, edit the plan or the result),
the client can include `overrides` on `/resume`; the server applies them
through `update_state` before resuming. `overrides` is validated against
the typed `ResumeOverrides` model (`plan`, `task`, `result`, `review`,
`refine_from`) with `extra="forbid"`, so a client cannot mutate counters or
routing internals by accident.

If `human_in_the_loop=false`, the server uses the auto graph and the run
completes in a single call without pausing.

`/resume` reads `human_in_the_loop` from the thread's checkpoint and
returns `409 Conflict` if the thread was not started in HITL mode, so
auto threads cannot be accidentally pushed through the step graph.

## FastAPI Service

```python
# app/api/schemas.py
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RunRequest(BaseModel):
    """Request body for graph execution."""

    task: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    plan: list[str] = Field(default_factory=list)
    max_rounds: int = Field(default=3, ge=1, le=20)
    timeout_seconds: float = Field(default=120.0, ge=1.0, le=900.0)
    human_in_the_loop: bool = False


class ReviewOverride(BaseModel):
    """Typed review override for HITL correction."""

    verdict: Literal["pass", "fail"]
    reason: str = Field(min_length=1)
    suggested_step: Literal["planner", "executor", "finish"]


class ResumeOverrides(BaseModel):
    """Allowed state edits before a HITL thread resumes."""

    model_config = ConfigDict(extra="forbid")

    plan: list[str] | None = None
    task: str | None = None
    result: str | None = None
    review: ReviewOverride | None = None
    refine_from: Literal["planner", "executor", "finish"] | None = None


class ResumeRequest(BaseModel):
    """Request body for /resume during human-in-the-loop runs.

    `overrides` is a typed model with `extra="forbid"`, so clients cannot
    mutate routing internals or counters by accident.
    """

    thread_id: str = Field(min_length=1)
    timeout_seconds: float = Field(default=120.0, ge=1.0, le=900.0)
    overrides: ResumeOverrides | None = None


class RunResponse(BaseModel):
    """Response body for graph execution and resume."""

    thread_id: str
    status: Literal["complete", "awaiting_human"]
    approved: bool
    needs_human: bool = False
    result: str | None = None
    next_action: str | None = None
    last_role: str | None = None
    rounds: int = 0
    max_rounds: int = 0
```

```python
# app/api/server.py
import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.schemas import ResumeRequest, RunRequest, RunResponse
from app.audit.logger import write_audit_event
from app.memory.checkpoint import graph_lifespan

api = FastAPI(
    title="Enterprise LangGraph Harness",
    lifespan=graph_lifespan,
)


def _initial_state(request: RunRequest) -> dict[str, object]:
    """Build the starting graph state for a new thread."""
    return {
        "thread_id": request.thread_id,
        "task": request.task,
        "messages": [],
        "plan": request.plan,
        "rounds": 0,
        "max_rounds": request.max_rounds,
        "role": "",
        "approved": False,
        "human_in_the_loop": request.human_in_the_loop,
    }


async def _snapshot_to_response(
    graph: object, thread_id: str
) -> RunResponse:
    """Translate the latest checkpoint into an API response.

    `needs_human` is only set when the thread is in human-in-the-loop
    mode AND the graph has more nodes to run. This avoids reporting
    `awaiting_human` for auto threads if a snapshot ever leaves
    `snapshot.next` non-empty for an unrelated reason.
    """
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await graph.aget_state(config)
    next_nodes = tuple(snapshot.next or ())
    values = snapshot.values or {}
    hitl = bool(values.get("human_in_the_loop", False))
    needs_human = hitl and bool(next_nodes)

    return RunResponse(
        thread_id=thread_id,
        status="awaiting_human" if needs_human else "complete",
        approved=bool(values.get("approved", False)),
        needs_human=needs_human,
        result=values.get("result"),
        next_action=next_nodes[0] if next_nodes else None,
        last_role=values.get("role") or None,
        rounds=int(values.get("rounds", 0)),
        max_rounds=int(values.get("max_rounds", 0)),
    )


@api.get("/health")
async def health() -> dict[str, str]:
    """Return service health."""
    return {"status": "ok"}


@api.post("/run", response_model=RunResponse)
async def run_agent(request: RunRequest, http: Request) -> RunResponse:
    """Run the graph for a new thread until completion or HITL pause."""
    graph = (
        http.app.state.graph_step
        if request.human_in_the_loop
        else http.app.state.graph_auto
    )
    config = {"configurable": {"thread_id": request.thread_id}}

    try:
        await asyncio.wait_for(
            graph.ainvoke(_initial_state(request), config=config),
            timeout=request.timeout_seconds,
        )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=(
                f"Graph run exceeded {request.timeout_seconds} seconds."
            ),
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return await _snapshot_to_response(graph, request.thread_id)


@api.post("/resume", response_model=RunResponse)
async def resume(request: ResumeRequest, http: Request) -> RunResponse:
    """Continue a paused HITL thread.

    The thread's `human_in_the_loop` flag is read from its persisted
    checkpoint, so a thread that was started in auto mode cannot be
    resumed through the HITL graph by accident. Optional `overrides`
    are applied through `update_state` before the graph resumes.
    """
    config = {"configurable": {"thread_id": request.thread_id}}

    # Both compiled graphs share the same checkpointer, so we can probe
    # state through either one. Use the step graph since it is the only
    # one that ever pauses.
    graph_step = http.app.state.graph_step
    snapshot = await graph_step.aget_state(config)
    values = snapshot.values or {}

    if not values:
        raise HTTPException(
            status_code=404,
            detail=f"Thread {request.thread_id} has no checkpoint.",
        )

    if not values.get("human_in_the_loop", False):
        raise HTTPException(
            status_code=409,
            detail=(
                "Thread was not started in human-in-the-loop mode; "
                "nothing to resume."
            ),
        )

    graph = graph_step

    try:
        if request.overrides:
            override_payload = request.overrides.model_dump(
                exclude_none=True
            )
            await graph.aupdate_state(
                config,
                override_payload,
            )
            await write_audit_event(
                thread_id=request.thread_id,
                round_number=int(values.get("rounds", 0)),
                node="human",
                event_type="override",
                payload=override_payload,
            )
        await asyncio.wait_for(
            graph.ainvoke(None, config=config),
            timeout=request.timeout_seconds,
        )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=(
                f"Graph resume exceeded {request.timeout_seconds} seconds."
            ),
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return await _snapshot_to_response(graph, request.thread_id)


@api.post("/stream")
async def stream_agent(
    request: RunRequest, http: Request
) -> StreamingResponse:
    """Stream graph updates as Server-Sent Events for a new thread."""
    graph = (
        http.app.state.graph_step
        if request.human_in_the_loop
        else http.app.state.graph_auto
    )
    config = {"configurable": {"thread_id": request.thread_id}}

    async def event_generator() -> AsyncIterator[str]:
        async for chunk in graph.astream(
            _initial_state(request), config=config
        ):
            yield f"data: {json.dumps(chunk, default=str)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
```

## Configuration

Use environment variables for runtime configuration:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini

ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=claude-sonnet-4-5

OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5-coder

DATABASE_URL=postgresql://postgres:postgres@db:5432/agents
REDIS_URL=redis://redis:6379/0

# Comma-separated tools the executor may call. Omit to fall back to the
# read-only default (read_file,list_dir). Never include shell-style tools
# without an explicit security review.
EXECUTOR_TOOLS=read_file,list_dir
```

## LLM Provider Switcher

```python
# app/llm/providers.py
import os
from typing import Any


def get_llm() -> Any:
    """Return a chat model based on LLM_PROVIDER."""
    provider = os.getenv("LLM_PROVIDER", "openai").lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=os.getenv("OLLAMA_MODEL", "qwen2.5-coder"))

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")
```

`with_structured_output(ReviewResult)` is supported natively by ChatOpenAI
and ChatAnthropic. With ChatOllama, pick a model that supports JSON-mode
output and pass `format="json"` to the constructor.

## Retry And Backoff

Transient model-provider failures should be retried at the LLM call boundary,
not only caught by FastAPI after the graph has already failed. Keep the retry
helper small and call it from each node.

```python
# app/llm/retry.py
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)


TRANSIENT_ERRORS: tuple[type[Exception], ...] = (
    TimeoutError,
    ConnectionError,
)


@retry(
    retry=retry_if_exception_type(TRANSIENT_ERRORS),
    wait=wait_exponential_jitter(initial=1, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def call_llm(runnable: Any, messages: list[Any]) -> Any:
    """Invoke an LLM runnable with bounded retry/backoff."""
    return await runnable.ainvoke(messages)
```

Provider SDKs expose more specific exceptions, such as rate-limit and API
connection errors. Add those exception classes to `TRANSIENT_ERRORS` once the
provider packages are imported in the concrete project.

## Audit Logging

Audit logging should be separate from checkpoints. Checkpoints make graph
execution resumable; audit rows make the run explainable later.

```sql
-- migrations/001_create_agent_audit_log.sql
CREATE TABLE IF NOT EXISTS agent_audit_log (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    thread_id TEXT NOT NULL,
    round INTEGER NOT NULL,
    node TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_agent_audit_thread
    ON agent_audit_log (thread_id, created_at);
```

```python
# app/audit/logger.py
import json
import logging
from typing import Any

from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

_audit_pool: AsyncConnectionPool | None = None


def set_audit_pool(pool: AsyncConnectionPool | None) -> None:
    """Install a pooled connection used by all audit writes.

    The pool is owned by the FastAPI lifespan so this module never opens
    a per-write connection. Tests can pass ``None`` to disable writes.
    """
    global _audit_pool
    _audit_pool = pool


async def write_audit_event(
    *,
    thread_id: str,
    round_number: int,
    node: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Write a durable audit event for graph execution.

    Audit writes are best-effort. They must never abort a graph run if
    Postgres is briefly unavailable, so all exceptions are logged and
    swallowed. If reliable delivery is required, replace this body with
    an enqueue to a durable broker (for example, Redis Streams or SQS).
    """
    if _audit_pool is None:
        logger.debug("audit pool not configured; skipping event %s", event_type)
        return

    try:
        async with _audit_pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO agent_audit_log (
                    thread_id, round, node, event_type, payload
                )
                VALUES (%s, %s, %s, %s, %s::jsonb)
                """,
                (
                    thread_id,
                    round_number,
                    node,
                    event_type,
                    json.dumps(payload),
                ),
            )
    except Exception:
        logger.exception(
            "failed to write audit event thread=%s node=%s type=%s",
            thread_id,
            node,
            event_type,
        )
```

The audit pool is opened and disposed inside `graph_lifespan` (see the
[Checkpointer Lifespan](#checkpointer-lifespan) section), so audit writes
reuse pooled connections instead of opening a new one per call.

Call `write_audit_event` after each node returns and after every HITL
override. For very high throughput, replace the inline INSERT with an
enqueue to a durable broker so the database is written to in batches.

## Docker

```dockerfile
# docker/Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.api.server:api", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
services:
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    environment:
      LLM_PROVIDER: openai
      DATABASE_URL: postgresql://postgres:postgres@db:5432/agents
      REDIS_URL: redis://redis:6379/0
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  db:
    image: postgres:16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: agents
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d agents"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  postgres_data:
```

## Requirements

Runtime dependencies live in `requirements.txt`. Test-only dependencies
(`httpx`, `pytest`, `pytest-asyncio`) live in `requirements-dev.txt` so a
production image never installs them.

```txt
# requirements.txt
fastapi
uvicorn[standard]
langgraph
langgraph-checkpoint-postgres
langchain-core
langchain-openai
langchain-anthropic
langchain-ollama
psycopg[binary]
psycopg_pool
redis
pydantic
tenacity
```

```txt
# requirements-dev.txt
-r requirements.txt
httpx
pytest
pytest-asyncio
```

## Running Locally

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.api.server:api --reload
```

Run without HITL (one call, loops up to `max_rounds` times):

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "demo-1",
    "task": "Create a plan for adding request tracing",
    "plan": [],
    "max_rounds": 3
  }'
```

Run with HITL (pauses after every node, still respects `max_rounds`):

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "demo-2",
    "task": "Create a plan for adding request tracing",
    "plan": [],
    "max_rounds": 3,
    "human_in_the_loop": true
  }'
```

Continue a paused HITL thread:

```bash
curl -X POST http://localhost:8000/resume \
  -H "Content-Type: application/json" \
  -d '{"thread_id": "demo-2"}'
```

Continue with state overrides (for example, edit the plan before
executor runs):

```bash
curl -X POST http://localhost:8000/resume \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "demo-2",
    "overrides": {"plan": ["clarify requirements", "add tracing"]}
  }'
```

Stream updates:

```bash
curl -N -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "demo-3",
    "task": "Review the current architecture",
    "plan": ["inspect graph", "check persistence", "check tests"]
  }'
```

## Testing

Start with deterministic tests around routing and graph shape. Mock LLM
calls for node-level tests so the suite does not depend on external
providers.

Configure `pytest-asyncio` in `pyproject.toml` so the async test below
runs without extra opt-in:

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "strict"
testpaths = ["tests"]
markers = [
    "integration: requires Docker Compose and external services",
]
```

```python
# tests/test_graph.py
import pytest

from app.graph.routing import DEFAULT_MAX_ROUNDS, route_after_action


def _state(**overrides: object) -> dict[str, object]:
    """Build a minimal AgentState dict for routing tests."""
    base: dict[str, object] = {
        "task": "Implement feature",
        "messages": [],
        "plan": [],
        "rounds": 0,
        "max_rounds": 3,
        "role": "actioner",
        "approved": False,
        "human_in_the_loop": False,
    }
    base.update(overrides)
    return base


def test_actioner_finishes_when_approved() -> None:
    """Approved checks should finish."""
    assert route_after_action(_state(approved=True)) == "finish"


def test_actioner_defaults_to_executor_refinement() -> None:
    """Failed checks should resume execution by default."""
    assert route_after_action(_state()) == "executor"


def test_actioner_can_resume_at_planner() -> None:
    """Planning suggestions should restart refinement from planning."""
    assert (
        route_after_action(_state(refine_from="planner")) == "planner"
    )


def test_actioner_respects_round_budget() -> None:
    """The loop must finish once the round budget is exhausted."""
    assert (
        route_after_action(
            _state(rounds=3, max_rounds=3, refine_from="executor")
        )
        == "finish"
    )


def test_default_round_budget_is_three() -> None:
    """The default budget must terminate after three rounds."""
    assert DEFAULT_MAX_ROUNDS == 3
    state = _state(rounds=3)
    state.pop("max_rounds")
    assert route_after_action(state) == "finish"


def test_resume_request_accepts_allowed_overrides() -> None:
    """ResumeRequest should accept allowlisted override keys."""
    from app.api.schemas import ResumeRequest

    req = ResumeRequest(
        thread_id="t1",
        overrides={"plan": ["a", "b"], "result": "ok"},
    )

    assert req.overrides is not None
    assert req.overrides.model_dump(exclude_none=True) == {
        "plan": ["a", "b"],
        "result": "ok",
    }


def test_resume_request_rejects_unknown_override_key() -> None:
    """ResumeRequest must reject any non-allowlisted override key."""
    from pydantic import ValidationError

    from app.api.schemas import ResumeRequest

    with pytest.raises(ValidationError):
        ResumeRequest(thread_id="t1", overrides={"rounds": 5})


@pytest.mark.asyncio
async def test_planner_writes_plan_to_state(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    """Planner must return the structured plan as state.plan."""
    from unittest.mock import AsyncMock, MagicMock

    from app.agents import planner as planner_module
    from app.graph.schemas import PlanResult

    plan = PlanResult(steps=["a", "b"], rationale="why")
    fake_structured = MagicMock()
    fake_structured.ainvoke = AsyncMock(return_value=plan)
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured
    monkeypatch.setattr(planner_module, "get_llm", lambda: fake_llm)

    result = await planner_module.planner_agent(_state())

    assert result["plan"] == ["a", "b"]
    assert result["role"] == "planner"


def test_compile_with_checkpointer_returns_distinct_graphs() -> None:
    """The HITL flag must produce two distinct compiled graphs."""
    from langgraph.checkpoint.memory import MemorySaver

    from app.graph.builder import compile_with_checkpointer

    saver = MemorySaver()
    auto = compile_with_checkpointer(saver, human_in_the_loop=False)
    step = compile_with_checkpointer(saver, human_in_the_loop=True)

    assert auto is not step


def test_executor_tools_allowlist_filters_unknown(monkeypatch) -> None:
    """get_tool_by_name must refuse tools that are not in the allow-list."""
    from app.tools.registry import get_executor_tools, get_tool_by_name

    monkeypatch.setenv("EXECUTOR_TOOLS", "read_file")

    tools = {tool.name for tool in get_executor_tools()}
    assert tools == {"read_file"}

    with pytest.raises(PermissionError):
        get_tool_by_name("list_dir")


@pytest.mark.asyncio
async def test_executor_runs_tool_loop_then_summarizes(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    """Executor calls a tool, then produces the structured ExecutorResult."""
    from unittest.mock import AsyncMock, MagicMock

    from langchain_core.messages import AIMessage

    from app.agents import executor as executor_module
    from app.graph.schemas import ExecutorResult

    monkeypatch.setenv("EXECUTOR_TOOLS", "read_file")

    tool_call_response = AIMessage(
        content="",
        tool_calls=[
            {
                "id": "call-1",
                "name": "read_file",
                "args": {"path": "README.md"},
            }
        ],
    )
    final_response = AIMessage(content="all done")

    bound_llm = MagicMock()
    bound_llm.ainvoke = AsyncMock(
        side_effect=[tool_call_response, final_response]
    )

    base_llm = MagicMock()
    base_llm.bind_tools.return_value = bound_llm

    execution = ExecutorResult(
        summary="read README",
        changes=["noted intro"],
        risks=[],
        verification=["re-read file"],
    )
    structured = MagicMock()
    structured.ainvoke = AsyncMock(return_value=execution)
    structured_llm = MagicMock()
    structured_llm.with_structured_output.return_value = structured

    llm_instances = iter([base_llm, structured_llm])
    monkeypatch.setattr(
        executor_module, "get_llm", lambda: next(llm_instances)
    )

    fake_tool = MagicMock()
    fake_tool.ainvoke = AsyncMock(return_value="# README contents")
    monkeypatch.setattr(
        executor_module, "get_tool_by_name", lambda name: fake_tool
    )
    monkeypatch.setattr(
        executor_module, "get_executor_tools", lambda: [fake_tool]
    )

    state = {
        "thread_id": "t1",
        "task": "summarize README",
        "messages": [],
        "plan": ["read README", "summarize"],
        "rounds": 0,
        "max_rounds": 3,
        "role": "executor",
        "approved": False,
        "human_in_the_loop": False,
    }

    result = await executor_module.executor_agent(state)

    fake_tool.ainvoke.assert_awaited_once_with({"path": "README.md"})
    assert result["result"] == "read README"
    assert result["execution"]["summary"] == "read README"
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["tool"] == "read_file"
    assert result["tool_calls"][0]["status"] == "ok"
```

For a minimal Compose-backed integration test, keep the test separate from
fast unit tests and mark it explicitly:

```python
# tests/test_compose_integration.py
import subprocess
import time

import httpx
import pytest


pytestmark = pytest.mark.integration


def _compose(*args: str) -> None:
    """Run a docker compose command for the integration stack."""
    subprocess.run(
        ["docker", "compose", *args],
        check=True,
        text=True,
    )


def test_compose_health_and_run() -> None:
    """Boot Compose, check health, and submit one graph run."""
    _compose("up", "-d", "--build")
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                response = httpx.get("http://localhost:8000/health")
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        else:
            raise AssertionError("API did not become healthy")

        response = httpx.post(
            "http://localhost:8000/run",
            json={
                "thread_id": "integration-demo",
                "task": "Create a short implementation plan",
                "max_rounds": 1,
                "timeout_seconds": 120,
            },
            timeout=130,
        )

        assert response.status_code == 200
        assert response.json()["thread_id"] == "integration-demo"
    finally:
        _compose("down", "-v")
```

## Production Notes

Before using this template for a real system, add:

- Authentication and authorization for every API route
- Request IDs, structured logs, and trace propagation
- Rate limiting and per-tenant quotas
- Prompt-injection and tool-use guardrails
- Secrets management through the deployment platform
- CI checks for unit tests, formatting, type checking, and security scanning
- Observability for latency, token usage, failure rates, and retries
- Postgres connection pooling with a fixed-size pool
- A TTL cleanup job for paused HITL threads so stale runs are archived

## Roadmap

Useful next increments:

- Add Redis-backed cancellation flags checked between graph steps
- Add a typed SSE event format with stable event names
- Add a tool registry with allowlisted tools and per-tool permissions
- Add Celery or a similar worker for long-running tool calls
- Expand Compose integration tests to cover HITL `/resume`
- Add an admin endpoint to list paused threads and replay their history

## **Recommendation: "Goal → Refined Task List"**


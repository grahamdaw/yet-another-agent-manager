"""LangGraph orchestrator graph for multi-agent task execution.

Nodes
-----
plan_node       - Supervisor breaks the goal into tasks and assigns profiles.
dispatch_node   - Spawns an agent session per task via `yaam new`.
monitor_node    - Polls tmux session liveness and result files.
collect_node    - Reads result files written by worker agents.
review_node     - Supervisor reviews results and decides next step.

Edges
-----
plan → dispatch → monitor → collect → review → (done | plan again)
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from yaam import session as session_mod
from yaam import tmux as tmux_mod
from yaam.orchestrator.models import OrchestratorState, Task, TaskResult

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_MODEL = "claude-haiku-4-5-20251001"
_RESULTS_DIR = Path("results")
_POLL_INTERVAL = 5  # seconds between liveness checks
_MAX_POLLS = 60  # give up after 5 minutes


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def plan_node(state: OrchestratorState) -> dict:
    """Break the user's goal into tasks, each assigned to a profile."""
    llm = ChatAnthropic(model=_MODEL, max_tokens=1024)

    messages = [
        SystemMessage(
            content=(
                "You are a software engineering supervisor. "
                "Break the given goal into concrete, actionable sub-tasks. "
                "For each sub-task, assign a profile name (use 'default' if unsure). "
                "Respond ONLY with a JSON array, e.g.:\n"
                '[{"id":"t1","description":"...","profile":"backend"}]'
            )
        ),
        HumanMessage(content=state["goal"]),
    ]

    response = llm.invoke(messages)
    raw = response.content.strip()

    # Extract JSON from possible markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    tasks: list[Task] = json.loads(raw)
    # Ensure each task has a unique id
    for task in tasks:
        if not task.get("id"):
            task["id"] = str(uuid.uuid4())[:8]

    return {"tasks": tasks, "phase": "executing"}


def dispatch_node(state: OrchestratorState) -> dict:
    """Spawn one agent session per planned task."""
    import subprocess

    agent_names: list[str] = []

    for task in state["tasks"]:
        agent_name = f"orch-{task['id']}"
        cmd = [
            "yaam",
            "new",
            agent_name,
            "--profile",
            task.get("profile", "default"),
        ]
        env_override = {"AGENT_TASK": task["description"]}

        import os

        proc_env = {**os.environ, **env_override}
        result = subprocess.run(cmd, env=proc_env, capture_output=True, text=True)

        if result.returncode != 0:
            # Log but continue — don't let one failure abort the whole run
            print(f"[dispatch] Failed to spawn {agent_name}: {result.stderr}")
        else:
            agent_names.append(agent_name)

    return {"agents": agent_names, "phase": "executing"}


def monitor_node(state: OrchestratorState) -> dict:
    """Poll until all agents have finished (result file exists or tmux session is gone)."""
    store = session_mod.SessionStore()
    remaining = list(state["agents"])

    for _ in range(_MAX_POLLS):
        if not remaining:
            break

        still_running = []
        for name in remaining:
            result_file = _RESULTS_DIR / f"{name}.json"
            if result_file.exists():
                continue  # done

            session = store.get(name)
            if session is None:
                continue  # removed from store, treat as done

            try:
                alive = tmux_mod.session_alive(session.tmux_session)
            except Exception:
                alive = False

            if alive:
                still_running.append(name)
            # else: session gone without result file → collect_node will mark failure

        remaining = still_running
        if remaining:
            time.sleep(_POLL_INTERVAL)

    return {}  # no state change; side-effect is waiting


def collect_node(state: OrchestratorState) -> dict:
    """Read result files produced by worker agents."""
    results: list[TaskResult] = []

    for name in state["agents"]:
        result_file = _RESULTS_DIR / f"{name}.json"

        if result_file.exists():
            data = json.loads(result_file.read_text())
            results.append(
                TaskResult(
                    task_id=data.get("session_name", name),
                    agent_name=name,
                    status=data.get("status", "failure"),
                    output=data.get("output", ""),
                )
            )
        else:
            results.append(
                TaskResult(
                    task_id=name,
                    agent_name=name,
                    status="timeout",
                    output="No result file found after polling period.",
                )
            )

    return {"results": results, "phase": "reviewing"}


def review_node(state: OrchestratorState) -> dict:
    """Supervisor reviews results and decides whether we're done."""
    llm = ChatAnthropic(model=_MODEL, max_tokens=512)

    summary = "\n".join(
        f"- {r['agent_name']}: {r['status']} — {r['output'][:200]}" for r in state["results"]
    )

    messages = [
        SystemMessage(
            content=(
                "You are a supervisor reviewing agent results. "
                "Given the original goal and results, decide if the goal is achieved. "
                "Reply with exactly one word: DONE or RETRY."
            )
        ),
        HumanMessage(content=f"Goal: {state['goal']}\n\nResults:\n{summary}"),
    ]

    response = llm.invoke(messages)
    verdict = response.content.strip().upper()

    if "RETRY" in verdict:
        return {"phase": "planning"}
    return {"phase": "done"}


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def _route_after_review(state: OrchestratorState) -> str:
    if state["phase"] == "done":
        return END
    return "plan"


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------


def build_graph() -> StateGraph:
    """Assemble and compile the orchestrator graph."""
    builder = StateGraph(OrchestratorState)

    builder.add_node("plan", plan_node)
    builder.add_node("dispatch", dispatch_node)
    builder.add_node("monitor", monitor_node)
    builder.add_node("collect", collect_node)
    builder.add_node("review", review_node)

    builder.set_entry_point("plan")
    builder.add_edge("plan", "dispatch")
    builder.add_edge("dispatch", "monitor")
    builder.add_edge("monitor", "collect")
    builder.add_edge("collect", "review")
    builder.add_conditional_edges("review", _route_after_review, {END: END, "plan": "plan"})

    return builder.compile()

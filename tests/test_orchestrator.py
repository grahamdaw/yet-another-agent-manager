"""Unit tests for the orchestrator — models, worker, and graph nodes."""

import json
from unittest.mock import MagicMock, patch

from yaam.orchestrator.models import OrchestratorState, Task, TaskResult
from yaam.orchestrator.worker import run as worker_run

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


def test_task_typeddict():
    t: Task = {"id": "t1", "description": "do stuff", "profile": "backend"}
    assert t["id"] == "t1"
    assert t["profile"] == "backend"


def test_task_result_typeddict():
    r: TaskResult = {
        "task_id": "t1",
        "agent_name": "orch-t1",
        "status": "success",
        "output": "done",
    }
    assert r["status"] == "success"


def test_orchestrator_state_typeddict():
    s: OrchestratorState = {
        "goal": "add health check",
        "tasks": [],
        "agents": [],
        "results": [],
        "phase": "planning",
        "error": None,
    }
    assert s["phase"] == "planning"


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


def test_worker_writes_result_file(tmp_path):
    with patch.dict("os.environ", {"AGENT_TASK": "do the thing"}):
        worker_run("my-agent", tmp_path)

    result_file = tmp_path / "my-agent.json"
    assert result_file.exists()
    data = json.loads(result_file.read_text())
    assert data["status"] == "success"
    assert "do the thing" in data["task"]
    assert data["session_name"] == "my-agent"


def test_worker_creates_results_dir(tmp_path):
    results_dir = tmp_path / "nested" / "results"
    assert not results_dir.exists()
    with patch.dict("os.environ", {"AGENT_TASK": "task"}):
        worker_run("agent1", results_dir)
    assert results_dir.exists()


def test_worker_result_includes_completed_at(tmp_path):
    with patch.dict("os.environ", {"AGENT_TASK": "ping"}):
        worker_run("agent2", tmp_path)
    data = json.loads((tmp_path / "agent2.json").read_text())
    assert "completed_at" in data


def test_worker_default_task_if_env_missing(tmp_path):
    env = {k: v for k, v in __import__("os").environ.items() if k != "AGENT_TASK"}
    with patch.dict("os.environ", env, clear=True):
        worker_run("agent3", tmp_path)
    data = json.loads((tmp_path / "agent3.json").read_text())
    assert data["task"] == "(no task provided)"


# ---------------------------------------------------------------------------
# Graph nodes (unit tests with heavy mocking)
# ---------------------------------------------------------------------------


def _base_state(**overrides) -> OrchestratorState:
    state: OrchestratorState = {
        "goal": "add health check endpoint",
        "tasks": [],
        "agents": [],
        "results": [],
        "phase": "planning",
        "error": None,
    }
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


def test_plan_node_parses_tasks():
    from yaam.orchestrator.graph import plan_node

    mock_response = MagicMock()
    mock_response.content = json.dumps(
        [{"id": "t1", "description": "add /health route", "profile": "backend"}]
    )

    with patch("yaam.orchestrator.graph.ChatAnthropic") as mock_llm_cls:
        mock_llm_cls.return_value.invoke.return_value = mock_response
        result = plan_node(_base_state())

    assert result["phase"] == "executing"
    assert len(result["tasks"]) == 1
    assert result["tasks"][0]["id"] == "t1"


def test_plan_node_assigns_id_if_missing():
    from yaam.orchestrator.graph import plan_node

    mock_response = MagicMock()
    mock_response.content = json.dumps([{"description": "do something", "profile": "default"}])

    with patch("yaam.orchestrator.graph.ChatAnthropic") as mock_llm_cls:
        mock_llm_cls.return_value.invoke.return_value = mock_response
        result = plan_node(_base_state())

    assert result["tasks"][0]["id"]  # auto-generated


def test_plan_node_handles_markdown_fence():
    from yaam.orchestrator.graph import plan_node

    mock_response = MagicMock()
    mock_response.content = '```json\n[{"id":"t1","description":"task","profile":"backend"}]\n```'

    with patch("yaam.orchestrator.graph.ChatAnthropic") as mock_llm_cls:
        mock_llm_cls.return_value.invoke.return_value = mock_response
        result = plan_node(_base_state())

    assert result["tasks"][0]["profile"] == "backend"


def test_dispatch_node_spawns_agents():
    from yaam.orchestrator.graph import dispatch_node

    tasks: list[Task] = [
        {"id": "t1", "description": "task one", "profile": "backend"},
    ]
    state = _base_state(tasks=tasks)

    mock_result = MagicMock()
    mock_result.returncode = 0

    with patch("subprocess.run", return_value=mock_result):
        result = dispatch_node(state)

    assert "orch-t1" in result["agents"]


def test_dispatch_node_continues_on_failure():
    from yaam.orchestrator.graph import dispatch_node

    tasks: list[Task] = [
        {"id": "t1", "description": "task one", "profile": "backend"},
        {"id": "t2", "description": "task two", "profile": "backend"},
    ]
    state = _base_state(tasks=tasks)

    fail = MagicMock(returncode=1, stderr="boom")
    ok = MagicMock(returncode=0, stderr="")

    with patch("subprocess.run", side_effect=[fail, ok]):
        result = dispatch_node(state)

    # t1 failed, t2 succeeded
    assert "orch-t2" in result["agents"]
    assert "orch-t1" not in result["agents"]


def test_collect_node_reads_result_files(tmp_path):
    from yaam.orchestrator.graph import collect_node

    result_data = {
        "session_name": "orch-t1",
        "status": "success",
        "output": "health check added",
    }
    (tmp_path / "orch-t1.json").write_text(json.dumps(result_data))

    state = _base_state(agents=["orch-t1"])

    with patch("yaam.orchestrator.graph._RESULTS_DIR", tmp_path):
        result = collect_node(state)

    assert result["results"][0]["status"] == "success"
    assert result["phase"] == "reviewing"


def test_collect_node_marks_timeout_for_missing_file(tmp_path):
    from yaam.orchestrator.graph import collect_node

    state = _base_state(agents=["orch-missing"])

    with patch("yaam.orchestrator.graph._RESULTS_DIR", tmp_path):
        result = collect_node(state)

    assert result["results"][0]["status"] == "timeout"


def test_review_node_returns_done():
    from yaam.orchestrator.graph import review_node

    mock_response = MagicMock()
    mock_response.content = "DONE"

    results: list[TaskResult] = [
        {"task_id": "t1", "agent_name": "orch-t1", "status": "success", "output": "ok"}
    ]
    state = _base_state(results=results, phase="reviewing")

    with patch("yaam.orchestrator.graph.ChatAnthropic") as mock_llm_cls:
        mock_llm_cls.return_value.invoke.return_value = mock_response
        result = review_node(state)

    assert result["phase"] == "done"


def test_review_node_returns_retry():
    from yaam.orchestrator.graph import review_node

    mock_response = MagicMock()
    mock_response.content = "RETRY"

    results: list[TaskResult] = [
        {"task_id": "t1", "agent_name": "orch-t1", "status": "failure", "output": ""}
    ]
    state = _base_state(results=results, phase="reviewing")

    with patch("yaam.orchestrator.graph.ChatAnthropic") as mock_llm_cls:
        mock_llm_cls.return_value.invoke.return_value = mock_response
        result = review_node(state)

    assert result["phase"] == "planning"


def test_build_graph_returns_compiled():
    from yaam.orchestrator.graph import build_graph

    graph = build_graph()
    assert graph is not None


# ---------------------------------------------------------------------------
# CLI: agent run
# ---------------------------------------------------------------------------


def test_run_command_happy_path():
    from typer.testing import CliRunner

    from yaam.cli import app

    runner = CliRunner()

    final_state = {
        "goal": "add health check",
        "tasks": [{"id": "t1", "description": "task", "profile": "backend"}],
        "agents": ["orch-t1"],
        "results": [
            {
                "task_id": "t1",
                "agent_name": "orch-t1",
                "status": "success",
                "output": "done",
            }
        ],
        "phase": "done",
        "error": None,
    }

    mock_graph = MagicMock()
    mock_graph.invoke.return_value = final_state

    with patch("yaam.orchestrator.graph.build_graph", return_value=mock_graph):
        result = runner.invoke(app, ["run", "add health check"])

    assert result.exit_code == 0
    assert "orch-t1" in result.output


def test_run_command_handles_graph_error():
    from typer.testing import CliRunner

    from yaam.cli import app

    runner = CliRunner()

    mock_graph = MagicMock()
    mock_graph.invoke.side_effect = RuntimeError("graph exploded")

    with patch("yaam.orchestrator.graph.build_graph", return_value=mock_graph):
        result = runner.invoke(app, ["run", "add health check"])

    assert result.exit_code == 1
    assert "failed" in result.output.lower()

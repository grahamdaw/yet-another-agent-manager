"""State models for the multi-agent orchestrator."""

from __future__ import annotations

from typing import Annotated, Literal

from typing_extensions import TypedDict


class Task(TypedDict):
    """A single unit of work dispatched to a worker agent."""

    id: str
    description: str
    profile: str  # profile name to spawn for this task


class TaskResult(TypedDict):
    """Result produced by a worker agent."""

    task_id: str
    agent_name: str
    status: Literal["success", "failure", "timeout"]
    output: str


class OrchestratorState(TypedDict):
    """Shared state threaded through the orchestrator graph."""

    goal: str
    tasks: Annotated[list[Task], "planned tasks"]
    agents: Annotated[list[str], "agent session names spawned"]
    results: Annotated[list[TaskResult], "collected results"]
    phase: Literal["planning", "executing", "reviewing", "done"]
    error: str | None

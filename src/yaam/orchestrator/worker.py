"""Worker agent — runs inside an agent session and writes a result file.

Each worker agent process:
1. Receives its task description via the ``AGENT_TASK`` environment variable
2. Executes the task (placeholder: prints and sleeps)
3. Writes ``results/<session_name>.json`` with its outcome

The supervisor (``graph.py``) polls the result file to detect completion.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path


def run(session_name: str, results_dir: Path) -> None:
    """Execute the task and write a result file.

    This is the entry point called from within a spawned agent pane.
    In production, replace the placeholder body with real agent logic.
    """
    task_description = os.environ.get("AGENT_TASK", "(no task provided)")
    results_dir.mkdir(parents=True, exist_ok=True)
    result_file = results_dir / f"{session_name}.json"

    try:
        # Placeholder: real implementation would invoke an LLM / run a script
        output = f"Completed task: {task_description}"
        status = "success"
    except Exception as exc:
        output = str(exc)
        status = "failure"

    result = {
        "session_name": session_name,
        "task": task_description,
        "status": status,
        "output": output,
        "completed_at": datetime.now(UTC).isoformat(),
    }
    result_file.write_text(json.dumps(result, indent=2))


def main() -> None:
    """CLI entry point: ``yaam-worker <session_name> [results_dir]``."""
    if len(sys.argv) < 2:
        print("Usage: yaam-worker <session_name> [results_dir]", file=sys.stderr)
        sys.exit(1)

    session_name = sys.argv[1]
    results_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("results")
    run(session_name, results_dir)

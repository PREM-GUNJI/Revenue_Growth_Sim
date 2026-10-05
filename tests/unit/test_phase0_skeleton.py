"""Phase 0 acceptance check: the repo skeleton imports and the task runner works.

This is intentionally the only test until Phase 1 adds real feature code —
it exists so CI has something to run and is green on the empty skeleton.
"""

import subprocess
import sys


def test_tasks_module_lists_targets():
    result = subprocess.run(
        [sys.executable, "-m", "tasks"], capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "usage: uv run python -m tasks" in result.stdout


def test_tasks_bootstrap_target_is_registered():
    import tasks

    assert "bootstrap" in tasks.TARGETS
    assert "test" in tasks.TARGETS

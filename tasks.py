"""Cross-platform task runner so Windows (no `make`) and CI share one entry point.

Usage: uv run python -m tasks <target>
The Makefile just forwards to this file, so `make <target>` and the command
above always do the same thing.
"""

from __future__ import annotations

import subprocess
import sys

TARGETS: dict[str, list[str] | None] = {}


def register(name: str):
    def deco(fn):
        TARGETS[name] = fn
        return fn

    return deco


def run(cmd: list[str]) -> int:
    # On Windows, npm/npx ship as .cmd shims that CreateProcess can't exec
    # directly without going through the shell.
    if sys.platform == "win32" and cmd and cmd[0] in {"npm", "npx"}:
        cmd = [cmd[0] + ".cmd", *cmd[1:]]
    print(f"+ {' '.join(cmd)}")
    return subprocess.call(cmd)


@register("bootstrap")
def bootstrap() -> int:
    return run(["uv", "sync", "--extra", "dev"])


@register("lint")
def lint() -> int:
    return run(["uv", "run", "ruff", "check", "."])


@register("test")
def test() -> int:
    return run(["uv", "run", "pytest", "-q"])


@register("generate")
def generate() -> int:
    code = run(["uv", "run", "python", "-m", "backend.data.generator", "42", "data"])
    if code:
        return code
    return run(["uv", "run", "python", "-m", "backend.data.eda", "42"])


@register("backtest")
def backtest() -> int:
    return run(["uv", "run", "python", "-m", "backend.model.backtest"])


@register("bench")
def bench() -> int:
    return run(["uv", "run", "python", "benchmarks/bench_engine.py"])


@register("evaluate")
def evaluate() -> int:
    print("not yet: Phase 14 adds reports/metrics.md")
    return 0


@register("eval-agent")
def eval_agent() -> int:
    """Phase 14: ~40 scripted agent evals against the deterministic oracle.
    Use --live (forwarded) to draft answers with the configured OpenAI model
    instead of the scripted fake LLM."""
    return run(["uv", "run", "python", "-m", "agent_evals.run_evals", *sys.argv[2:]])


@register("replay")
def replay() -> int:
    print("not yet: Phase 13 adds agent trace replay")
    return 0


@register("serve")
def serve() -> int:
    # Phase 3 only wires up GET /assumptions; Phase 6 adds the rest of the API.
    return run(["uv", "run", "uvicorn", "backend.api.main:app", "--reload"])


@register("demo")
def demo() -> int:
    """Phase 16 (AC-025): clean-clone demo entry point for local dev.

    Two documented commands bring up the full demo from a fresh clone:
      1) `uv run python -m tasks demo`            (this: syncs deps, serves the API)
      2) `npm --prefix frontend install && npm --prefix frontend run dev`  (the UI)
    """
    code = run(["uv", "sync", "--extra", "dev"])
    if code:
        return code
    return serve()


@register("demo-check")
def demo_check() -> int:
    """Phase 17 (AC-025): headless, non-interactive proof that the clean-clone
    demo actually comes up. Starts the API in the background, polls /healthz,
    hits GET /assumptions, builds the frontend production bundle (no dev
    server, so this is safe and bounded in CI), then stops the API.
    """
    import time
    import urllib.error
    import urllib.request

    proc = subprocess.Popen(
        ["uv", "run", "uvicorn", "backend.api.main:app", "--host", "127.0.0.1", "--port", "8000"]
    )
    try:
        deadline = time.time() + 30
        ok = False
        while time.time() < deadline:
            try:
                with urllib.request.urlopen("http://127.0.0.1:8000/healthz", timeout=2) as resp:
                    if resp.status == 200:
                        ok = True
                        break
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(1)
        if not ok:
            print("demo-check: API never became healthy")
            return 1
        with urllib.request.urlopen("http://127.0.0.1:8000/assumptions", timeout=5) as resp:
            if resp.status != 200:
                print(f"demo-check: GET /assumptions returned {resp.status}")
                return 1
        print("demo-check: API is up, /healthz and /assumptions OK")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    code = run(["npm", "--prefix", "frontend", "ci"])
    if code:
        return code
    code = run(["npm", "--prefix", "frontend", "run", "build"])
    if code:
        return code
    print("demo-check: frontend production build OK")
    return 0


@register("smoke")
def smoke() -> int:
    print("not yet: Phase 19 adds the post-deploy smoke test")
    return 0


@register("rollback")
def rollback() -> int:
    print("not yet: Phase 19 adds deploy/rollback.sh")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in TARGETS:
        print(f"usage: uv run python -m tasks <{'|'.join(TARGETS)}>")
        return 1
    return TARGETS[argv[0]]()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

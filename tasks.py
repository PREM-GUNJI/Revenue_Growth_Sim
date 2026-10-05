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
    print("not yet: Phase 1 adds backend/data/generator.py")
    return 0


@register("backtest")
def backtest() -> int:
    print("not yet: Phase 2 adds reports/model_backtest.md")
    return 0


@register("bench")
def bench() -> int:
    print("not yet: Phase 7 adds benchmarks/bench_engine.py")
    return 0


@register("evaluate")
def evaluate() -> int:
    print("not yet: Phase 14 adds reports/metrics.md")
    return 0


@register("replay")
def replay() -> int:
    print("not yet: Phase 13 adds agent trace replay")
    return 0


@register("serve")
def serve() -> int:
    print("not yet: Phase 6/8 add backend/api + frontend/")
    return 0


@register("demo")
def demo() -> int:
    print("not yet: Phase 16 adds the clean-clone demo")
    return 0


@register("demo-check")
def demo_check() -> int:
    print("not yet: Phase 17 adds the headless demo-check")
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

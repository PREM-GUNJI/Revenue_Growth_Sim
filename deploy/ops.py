"""Build, deploy, roll back, and smoke-test the local non-production stack."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

COMPOSE = ["docker", "compose", "-f", "deploy/compose.yml", "-p", "revenue-growth-sim"]
BASE_URL = os.getenv("DEPLOY_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
BASELINE_HASH = "bec3624aea61082843d5b77cf204c19ea729d490c3e125ebc9552ade48031710"


def command(args: list[str], env: dict[str, str] | None = None) -> None:
    print("+", " ".join(args))
    subprocess.run(args, check=True, env=env)


def image_env(tag: str) -> dict[str, str]:
    return {**os.environ, "IMAGE_TAG": tag}


def get_json(path: str, *, method: str = "GET", payload: dict | None = None) -> dict | list:
    request = urllib.request.Request(
        BASE_URL + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def smoke() -> None:
    deadline = time.monotonic() + 45
    while True:
        try:
            health = get_json("/api/healthz")
            ready = get_json("/api/readyz")
            if health.get("status") == "ok" and ready.get("status") == "ready":
                break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if time.monotonic() >= deadline:
                raise RuntimeError("deployment did not become healthy") from None
            time.sleep(1)

    baseline = get_json(
        "/api/scenarios/evaluate", method="POST",
        payload={"scenarios": [{"schema_version": 1, "name": "Baseline", "levers": {}, "cost_shock": {"aluminium_pct": 0, "pet_resin_pct": 0, "sugar_pct": 0}}], "k": 200, "seed": 42},
    )[0]
    if baseline["status"] != "SUPPORTED" or baseline["result_hash"] != BASELINE_HASH:
        raise RuntimeError("baseline smoke result did not match the fixed supported hash")

    refusal = get_json(
        "/api/scenarios/evaluate", method="POST",
        payload={"scenarios": [{"schema_version": 1, "name": "Unsupported", "levers": {"Aurora-can_330ml": {"price_index": 1.5, "promo_depth_pct": 0, "mechanic": "none", "promo_weeks_per_month": 0}}, "cost_shock": {"aluminium_pct": 0, "pet_resin_pct": 0, "sugar_pct": 0}}], "k": 0, "seed": 42},
    )[0]
    if refusal["status"] != "REFUSED" or refusal["portfolio_gp"] is not None:
        raise RuntimeError("unsupported scenario did not refuse without numeric output")
    print("smoke: health, fixed baseline hash, and refusal behaviour passed")


def deploy(tag: str, *, build: bool) -> None:
    if build:
        command(["docker", "build", "--tag", f"revenue-growth-api:{tag}", "--file", "deploy/Dockerfile.api", "."])
        command(["docker", "build", "--tag", f"revenue-growth-web:{tag}", "--file", "deploy/Dockerfile.web", "."])
    command([*COMPOSE, "up", "--detach", "--wait", "--remove-orphans"], image_env(tag))
    smoke()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("deploy", "rollback", "smoke"))
    parser.add_argument("tag", nargs="?", default="dev")
    args = parser.parse_args()
    try:
        if args.action == "smoke":
            smoke()
        else:
            deploy(args.tag, build=args.action == "deploy")
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"{args.action} failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

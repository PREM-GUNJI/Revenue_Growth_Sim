#!/usr/bin/env python3
"""PostToolUse hook on Write|Edit: runs ruff check --fix and ruff format on the touched file.

Reads the standard hook JSON from stdin. Only acts on .py files; anything
else is a silent no-op so the hook is safe to attach broadly.
"""

import json
import subprocess
import sys


def main() -> int:
    payload = json.load(sys.stdin)
    file_path = payload.get("tool_input", {}).get("file_path") or payload.get(
        "tool_response", {}
    ).get("filePath")

    if not file_path or not file_path.endswith(".py"):
        return 0

    subprocess.run(["uv", "run", "ruff", "check", "--fix", file_path], check=False)
    subprocess.run(["uv", "run", "ruff", "format", file_path], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

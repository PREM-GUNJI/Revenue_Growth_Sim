#!/usr/bin/env python3
"""PreToolUse hook on Bash: blocks force-push and rm -rf outside the repo or on .git.

Reads the standard hook JSON from stdin. Exit 2 blocks the tool call and
feeds stderr back to Claude as the reason; exit 0 allows it.
"""

import json
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

FORCE_PUSH = re.compile(r"\bgit\s+push\b.*(--force\b|(?<!--)-f\b)")
RM_RF = re.compile(r"\brm\s+(-\w*r\w*f\w*|-\w*f\w*r\w*)\s+(.+)")


def is_outside_repo_or_git(path: str) -> bool:
    cleaned = path.strip().strip("'\"")
    if not cleaned or cleaned.startswith("-"):
        return False
    if ".git" in cleaned.replace("\\", "/").split("/"):
        return True
    abs_path = os.path.abspath(os.path.join(REPO_ROOT, cleaned))
    return os.path.commonpath([REPO_ROOT, abs_path]) != REPO_ROOT


def main() -> int:
    payload = json.load(sys.stdin)
    command = payload.get("tool_input", {}).get("command", "")

    if FORCE_PUSH.search(command):
        print("blocked: force-push is not allowed by project policy", file=sys.stderr)
        return 2

    rm_match = RM_RF.search(command)
    if rm_match:
        targets = rm_match.group(2).split()
        if any(is_outside_repo_or_git(t) for t in targets):
            print(
                "blocked: rm -rf targeting a path outside the repo or .git is not allowed",
                file=sys.stderr,
            )
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

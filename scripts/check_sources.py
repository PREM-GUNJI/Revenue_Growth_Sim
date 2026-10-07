"""Check that every external source cited in the app still resolves: `uv run python scripts/check_sources.py`.

Network-dependent, so it is a manual/scheduled check and not part of the test suite. A 403 from a site that
blocks scripted clients is reported as BLOCKED (open it in a browser), anything else non-2xx as BROKEN.
"""

from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request

from backend.ai_pricing import SOURCE_URL
from backend.assumptions.assumptions import ASSUMPTIONS

CITED = [u for a in ASSUMPTIONS.values() for u in re.findall(r"https?://[^\s)]+", a.reference or "")]
URLS = sorted({SOURCE_URL, *CITED})


def status(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return "OK" if 200 <= response.status < 300 else f"BROKEN {response.status}"
    except urllib.error.HTTPError as exc:
        return "BLOCKED 403 (check in a browser)" if exc.code == 403 else f"BROKEN {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return "BROKEN " + type(exc).__name__


if __name__ == "__main__":
    results = {url: status(url) for url in URLS}
    for url, result in results.items():
        print(f"{result:34} {url}")
    sys.exit(any(r.startswith("BROKEN") for r in results.values()))

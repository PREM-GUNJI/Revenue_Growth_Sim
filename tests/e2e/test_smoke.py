"""Browser smoke for the comparison board's refusal and loser states (AC-024)."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
API_URL = "http://127.0.0.1:8000/healthz"
UI_URL = "http://127.0.0.1:5173"


def wait_for(url: str, process: subprocess.Popen[bytes], label: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{label} exited early with code {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.25)
    raise TimeoutError(f"{label} did not start at {url}")


def stop_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@pytest.fixture(scope="module")
def ui_url() -> Iterator[str]:
    env = os.environ.copy()
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.api.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    ui = subprocess.Popen(
        ["npm.cmd", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
        cwd=ROOT / "frontend",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_for(API_URL, api, "API")
        wait_for(UI_URL, ui, "frontend")
        yield UI_URL
    finally:
        for process in (ui, api):
            stop_process_tree(process)


def test_ac024_loser_and_refusal_render_with_nearest_action(ui_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page: Page = browser.new_page()
        page.goto(ui_url, wait_until="networkidle")
        page.get_by_text("worse than baseline", exact=False).first.wait_for(timeout=30_000)
        assert page.get_by_text("REFUSED", exact=False).count() >= 1
        nearest = page.get_by_role("button", name="Use nearest supported scenario")
        assert nearest.count() == 1
        nearest.click()
        page.get_by_text("Nearest supported to Out-of-range price").wait_for(timeout=30_000)
        page.get_by_role("tab", name="Analytics").click()
        page.get_by_text("Trade-off plane").wait_for()
        page.get_by_text("Margin waterfall").wait_for()
        page.get_by_text("Price × promotion sweep").wait_for()
        page.get_by_role("button", name="Generate heatmap").click()
        page.get_by_role("button", name="Refresh heatmap").wait_for(timeout=30_000)
        browser.close()

"""Browser smoke: the Situation baseline, the comparison board's refusal and loser states (AC-024), audit and export."""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.auth import hash_password
from backend.db import User
from backend.migrations.runner import upgrade_database

ROOT = Path(__file__).resolve().parents[2]
API_URL = "http://127.0.0.1:8000/healthz"
UI_URL = "http://127.0.0.1:5173"
TEST_EMAIL, TEST_PASSWORD = "e2e@example.com", "e2e-password-1"


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


def require_free_port(port: int) -> None:
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            pytest.fail(f"Port {port} is already in use; stop the running dev server before the e2e smoke test.")


@pytest.fixture(scope="module")
def ui_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    for port in (8000, 5173):
        require_free_port(port)
    # The API under test gets its own throwaway database so no test user ever lands in a real one.
    database_url = f"sqlite:///{tmp_path_factory.mktemp('e2e') / 'e2e.db'}"
    engine = create_engine(database_url)
    upgrade_database(engine)
    with Session(engine) as session:
        session.add(User(id="e2e-user", email=TEST_EMAIL, display_name="E2E User",
                         password_hash=hash_password(TEST_PASSWORD), is_active=True))
        session.commit()
    engine.dispose()
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["AUTH_SECRET_KEY"] = "e2e-secret-key"
    env["VITE_API_TARGET"] = "http://127.0.0.1:8000"
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
        page.get_by_label("Email address").fill(TEST_EMAIL)
        page.get_by_label("Password", exact=True).fill(TEST_PASSWORD)
        page.get_by_role("button", name="Sign In").click()
        page.get_by_label("Name", exact=True).fill("E2E case")  # a fresh database lands on the empty homepage
        page.get_by_label("Business question", exact=False).fill("Which pack should take price?")
        page.get_by_role("button", name="Create case").click()
        # Step 1 is the Situation: a baseline P&L in rupees, not a bare percentage.
        page.get_by_role("heading", name="Where Aurora stands today").wait_for(timeout=30_000)
        page.get_by_text("Which pack should take price?").first.wait_for()
        page.get_by_role("heading", name="Weekly profit and loss by pack").wait_for()
        page.get_by_role("cell", name="Aurora total").wait_for(timeout=30_000)
        assert page.get_by_text("₹").count() > 10
        compare = page.get_by_role("link", name=re.compile("Compare")).first
        compare.click()
        page.wait_for_url("**/board")
        page.get_by_text("worse than baseline", exact=False).first.wait_for(timeout=30_000)
        page.get_by_role("columnheader", name=re.compile("Gross profit")).first.wait_for()  # the absolute table
        assert page.get_by_text("Rests on", exact=False).count() >= 1  # each result names the assumptions it depends on
        assert page.get_by_text("REFUSED", exact=False).count() >= 1
        nearest = page.get_by_role("button", name="Use nearest supported scenario")
        assert nearest.count() == 1
        with page.expect_response(lambda r: r.request.method == "PUT" and r.url.endswith("/scenarios"), timeout=30_000) as saved:
            nearest.click()  # the edit autosaves to the workspace one second later
        assert saved.value.status == 200
        page.get_by_text("Nearest supported to Out-of-range can price").first.wait_for(timeout=30_000)
        page.get_by_role("tab", name="Analytics").click()
        page.get_by_text("Trade-off plane").wait_for()
        page.get_by_text("Why gross profit moved").wait_for()
        page.get_by_text("Price × promotion sweep").wait_for()
        page.get_by_role("button", name="Generate heatmap").click()
        page.get_by_role("button", name="Refresh heatmap").wait_for(timeout=30_000)
        # The case autosaves: a reload on the deep link comes back with the scenario we added.
        page.reload(wait_until="networkidle")
        page.get_by_role("tab", name="Comparison board").click()
        page.get_by_text("Nearest supported to Out-of-range can price").first.wait_for(timeout=30_000)
        browser.close()


def sign_in(page: Page, ui_url: str) -> None:
    page.goto(ui_url, wait_until="networkidle")
    page.get_by_label("Email address").fill(TEST_EMAIL)
    page.get_by_label("Password", exact=True).fill(TEST_PASSWORD)
    page.get_by_role("button", name="Sign In").click()
    page.get_by_role("heading", name="Cases").wait_for(timeout=30_000)


def test_hub_audit_export_and_sign_out(ui_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        sign_in(page, ui_url)

        # The homepage lists the case but carries no audit rows, cost figures or status tiles.
        page.get_by_role("heading", name="E2E case").wait_for()
        assert page.locator("table").count() == 0 and page.get_by_text("rate not set").count() == 0

        # Audit page: the sign-in above is on the log, and AI usage starts empty rather than showing $0.
        page.get_by_role("link", name="Audit and AI usage").click()
        page.get_by_role("cell", name="Signed in").first.wait_for(timeout=30_000)
        page.get_by_role("tab", name="AI usage and cost").click()
        page.get_by_text("No AI usage recorded").wait_for()
        page.get_by_role("link", name="Agent runs").click()
        page.get_by_text("No agent runs yet").wait_for()

        # Export the case as a deck.
        page.get_by_role("link", name="C5i home").click()
        page.get_by_role("link", name="Open").first.click()
        page.get_by_text("All changes saved").wait_for()
        with page.expect_download(timeout=60_000) as download:
            page.get_by_role("button", name="Export deck").click()
        assert download.value.suggested_filename.endswith(".pptx")

        # Sign out returns to the sign-in page and the app is locked again.
        page.get_by_role("button", name="Sign out").click()
        page.get_by_label("Email address").wait_for()
        page.goto(ui_url + "/audit", wait_until="networkidle")
        page.get_by_label("Email address").wait_for()
        browser.close()

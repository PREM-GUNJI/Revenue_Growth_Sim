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
# Overridable so the smoke test can run beside a developer's own servers on the default ports.
API_PORT = int(os.environ.get("E2E_API_PORT", "8000"))
UI_PORT = int(os.environ.get("E2E_UI_PORT", "5173"))
API_URL = f"http://127.0.0.1:{API_PORT}/healthz"
UI_URL = f"http://127.0.0.1:{UI_PORT}"
TEST_EMAIL, TEST_PASSWORD = "e2e@example.com", "e2e-password-1"
VIEWER_EMAIL = "viewer@example.com"


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
    for port in (API_PORT, UI_PORT):
        require_free_port(port)
    # The API under test gets its own throwaway database so no test user ever lands in a real one.
    database_url = f"sqlite:///{tmp_path_factory.mktemp('e2e') / 'e2e.db'}"
    engine = create_engine(database_url)
    upgrade_database(engine)
    with Session(engine) as session:
        session.add(User(id="e2e-user", email=TEST_EMAIL, display_name="E2E User",
                         password_hash=hash_password(TEST_PASSWORD), is_active=True, role="admin"))
        session.add(User(id="e2e-viewer", email=VIEWER_EMAIL, display_name="E2E Viewer",
                         password_hash=hash_password(TEST_PASSWORD), is_active=True, role="viewer"))
        session.commit()
    engine.dispose()
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["AUTH_SECRET_KEY"] = "e2e-secret-key"
    env["VITE_API_TARGET"] = f"http://127.0.0.1:{API_PORT}"
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.api.main:app", "--host", "127.0.0.1", "--port", str(API_PORT)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    ui = subprocess.Popen(
        ["npm.cmd", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(UI_PORT), "--strictPort"],
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


def finish_new_case(page: Page, name: str, question: str) -> None:
    """New case is Market → Decision → Details; advance then create."""
    page.get_by_role("button", name="Continue").click()
    page.get_by_role("button", name="Continue").click()
    page.get_by_label("Name", exact=True).fill(name)
    page.get_by_label("Business question", exact=False).fill(question)
    page.get_by_role("button", name="Create case").click()


def test_ac024_loser_and_refusal_render_with_nearest_action(ui_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page: Page = browser.new_page()
        page.goto(ui_url, wait_until="networkidle")
        page.get_by_label("Email address").fill(TEST_EMAIL)
        page.get_by_label("Password", exact=True).fill(TEST_PASSWORD)
        page.get_by_role("button", name="Sign In").click()
        # Fresh DB lands on the empty homepage with the new-case wizard already open.
        finish_new_case(page, "E2E case", "Which pack should take price?")
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
        page.get_by_role("tab", name="Advanced charts").click()
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

        # Export the case as a deck, then open the executive brief boardroom view.
        page.get_by_role("link", name="C5i home").click()
        page.get_by_role("link", name="Open").first.click()
        page.get_by_text("All changes saved").wait_for()
        with page.expect_download(timeout=60_000) as download:
            page.get_by_role("button", name="Export deck").click()
        assert download.value.suggested_filename.endswith(".pptx")
        page.get_by_role("link", name="Executive brief").first.click()
        page.wait_for_url("**/executive")
        page.get_by_role("region", name="Recommendation").wait_for(timeout=30_000)
        page.get_by_text("Decision brief", exact=False).first.wait_for()
        page.get_by_role("heading", name="Options at a glance").wait_for()

        # Sign out returns to the sign-in page and the app is locked again.
        page.get_by_role("button", name="Sign out").click()
        page.get_by_label("Email address").wait_for()
        page.goto(ui_url + "/audit", wait_until="networkidle")
        page.get_by_label("Email address").wait_for()
        browser.close()


def test_us_market_shows_dollar_currency(ui_url: str) -> None:
    """AC-024 companion: a United States case formats money in USD, not rupees."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        sign_in(page, ui_url)
        page.get_by_role("button", name="New case").click()
        page.get_by_role("radio", name=re.compile("United States")).check()
        finish_new_case(page, "US currency case", "Does the US market show dollars?")
        page.get_by_role("heading", name="Where Aurora stands today").wait_for(timeout=30_000)
        page.get_by_role("heading", name="Weekly profit and loss by pack").wait_for()
        assert page.get_by_text("$").count() > 5
        assert page.get_by_text("₹").count() == 0
        browser.close()


def test_take_price_template_shows_a_loser_and_a_refusal(ui_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        sign_in(page, ui_url)
        page.get_by_role("button", name="New case").click()
        page.get_by_role("button", name="Continue").click()  # market → decision
        page.get_by_role("radio", name=re.compile("Should we take price")).check()
        page.get_by_label("Pack", exact=True).select_option("bottle_1500ml")
        page.get_by_role("button", name="Continue").click()  # decision → details
        # The template fills the name and question; the user can still change them.
        assert page.get_by_label("Name", exact=True).input_value() == "Price rise on the 1.5 L"
        assert "1.5 L bottle" in page.get_by_label("Business question", exact=False).input_value()
        page.get_by_role("button", name="Create case").click()
        page.get_by_role("heading", name="Where Aurora stands today").wait_for(timeout=30_000)
        page.get_by_role("link", name=re.compile("Compare")).first.click()
        page.wait_for_url("**/board")
        page.get_by_text("worse than baseline", exact=False).first.wait_for(timeout=30_000)
        page.get_by_text("1.5 L +50%").first.wait_for()
        assert page.get_by_text("REFUSED", exact=False).count() >= 1
        browser.close()


def test_viewer_reads_the_brief_but_cannot_edit(ui_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(ui_url, wait_until="networkidle")
        page.get_by_label("Email address").fill(VIEWER_EMAIL)
        page.get_by_label("Password", exact=True).fill(TEST_PASSWORD)
        page.get_by_role("button", name="Sign In").click()
        page.get_by_role("heading", name="Cases").wait_for(timeout=30_000)
        page.get_by_role("heading", name="E2E case").wait_for()
        assert page.get_by_role("button", name="New case").count() == 0
        assert page.get_by_role("link", name="Audit and AI usage").count() == 0

        page.get_by_role("link", name="Open brief").first.click()
        page.wait_for_url("**/executive")
        page.get_by_role("region", name="Recommendation").wait_for(timeout=30_000)
        assert page.get_by_role("link", name=re.compile("workbench", re.IGNORECASE)).count() == 0
        assert page.get_by_role("button", name="Export deck").count() == 1

        # A viewer who deep-links to the workbench is sent back to the brief.
        page.goto(page.url.replace("/executive", "/board"), wait_until="networkidle")
        page.wait_for_url("**/executive")
        browser.close()

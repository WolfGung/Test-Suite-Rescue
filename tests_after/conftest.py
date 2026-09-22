"""Fixtures of the cured suite: a live app, a clean board per test, unique data.

Every fixture here answers one disease of the sick suite. The app is our own
— started by the suite on a free port unless `APP_URL` says otherwise — so no
test depends on a terminal somebody opened and no test shares its board with
a stranger's; the board is reset before every test, so no test depends on
what another one left behind; titles are unique per test, so a rerun cannot
collide with itself.
"""
from __future__ import annotations

import os
import socket
import threading
import time
import uuid
from collections.abc import Iterator
from urllib.request import urlopen

import httpx
import pytest

from tests_after.ui.browser import Browser


def _answers(url: str, timeout: float = 1.0) -> bool:
    try:
        with urlopen(f"{url}/healthz", timeout=timeout):
            return True
    except Exception:
        return False


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def app_url() -> Iterator[str]:
    """The app under test.

    `APP_URL` set: use it exactly as given and start nothing — CI, a Docker
    stand, or a developer pointing the suite at an app already running.
    `APP_URL` unset: always start our own app in-process, on a free port,
    and yield that. Reusing "whatever already answers on a fixed port" was
    tried and dropped — anything listening there is not necessarily ours,
    and a board that a stranger resets in the middle of a test is exactly
    the class of failure this suite exists to cure.
    """
    configured = os.environ.get("APP_URL")
    if configured:
        yield configured.rstrip("/")
        return

    import uvicorn

    from app.main import create_app

    port = free_port()
    url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True, name="task-board")
    thread.start()
    deadline = time.monotonic() + 15
    while not _answers(url, timeout=0.5):
        if time.monotonic() > deadline or not thread.is_alive():
            raise RuntimeError(f"the app did not start on {url} within 15 s")
        time.sleep(0.1)
    yield url
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def api(app_url: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=app_url, timeout=10.0) as client:
        yield client


@pytest.fixture(autouse=True)
def clean_board(api: httpx.Client) -> None:
    """Every test starts from an empty board — isolation by construction, not by luck."""
    response = api.post("/api/reset")
    assert response.status_code == 204, f"reset failed: HTTP {response.status_code} {response.text}"


@pytest.fixture
def unique_title() -> str:
    """A title no earlier run and no other test can have used."""
    return f"Write the report {uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    """One browser per session, engine from UI_DRIVER (playwright by default, or selenium)."""
    from tests_after.ui.browser import open_browser

    instance = open_browser()
    yield instance
    instance.close()


@pytest.fixture
def board(browser: Browser, app_url: str):
    from tests_after.ui.board import BoardPage

    return BoardPage(browser, app_url)

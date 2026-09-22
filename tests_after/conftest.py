"""Fixtures of the cured suite: a live app, a clean board per test, unique data.

Every fixture here answers one disease of the sick suite. The app is started
by the suite (or found already running), so no test depends on a terminal
somebody opened; the board is reset before every test, so no test depends on
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
from urllib.parse import urlsplit
from urllib.request import urlopen

import httpx
import pytest

DEFAULT_APP_URL = "http://127.0.0.1:8100"


def _answers(url: str, timeout: float = 1.0) -> bool:
    try:
        with urlopen(f"{url}/healthz", timeout=timeout):
            return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def app_url() -> Iterator[str]:
    """The app under test: `APP_URL` when set, otherwise started here on port 8100."""
    url = os.environ.get("APP_URL", DEFAULT_APP_URL).rstrip("/")
    parts = urlsplit(url)
    if _answers(url) or parts.hostname not in {"127.0.0.1", "localhost"}:
        yield url
        return
    import uvicorn

    from app.main import create_app

    server = uvicorn.Server(uvicorn.Config(create_app(), host=parts.hostname, port=parts.port, log_level="warning"))
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


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]

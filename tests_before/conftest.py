"""The sick suite's fixtures — or rather, its lack of them.

One browser and one page for the whole module, shared by every test (disease:
shared state); a module-level list that later tests read (disease: order
dependence); no reset of the board, ever (disease: no cleanup). The app is
expected to be running already on APP_URL; `tools/measure.py` starts it.
"""
from __future__ import annotations

import os

import httpx
import pytest
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("APP_URL", "http://127.0.0.1:8100").rstrip("/")

#: Ids of the tasks created so far, read by the tests that come "after" — which
#: only works when pytest runs the file top to bottom and nothing failed.
created_ids: list[int] = []


@pytest.fixture(scope="session")
def api() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=10.0)


@pytest.fixture(scope="session")
def page():
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=os.environ.get("HEADLESS", "true").lower() != "false")
    page = browser.new_page()
    yield page
    browser.close()
    playwright.stop()

"""The page object of the task board: the flows, expressed in test ids and waits.

Every read of the list first waits for `data-loaded="true"` — the board's own
statement that its script has rendered. That single line is the cure for the
race the sick suite sleeps through.
"""
from __future__ import annotations

from tests_after.ui.browser import Browser


class BoardPage:
    def __init__(self, browser: Browser, base_url: str) -> None:
        self._browser = browser
        self._base_url = base_url.rstrip("/")

    def create(self, title: str, owner: str, *, expect_error: bool = False) -> None:
        self._browser.goto(f"{self._base_url}/")
        self._browser.fill("title-input", title)
        self._browser.fill("owner-input", owner)
        self._browser.click("create-button")
        if expect_error:
            self._browser.wait_for_attribute("form-error", "data-testid", "form-error")
        else:
            self._wait_loaded()

    def form_error(self) -> str:
        return self._browser.text("form-error")

    def open_board(self) -> None:
        self._browser.goto(f"{self._base_url}/board")
        self._wait_loaded()

    def titles(self) -> list[str]:
        self._wait_loaded()
        return self._browser.texts("task-title")

    def owners(self) -> list[str]:
        self._wait_loaded()
        return self._browser.texts("task-owner")

    def toggle_first(self) -> None:
        self._wait_loaded()
        self._browser.click("task-toggle")
        self._wait_loaded()

    def first_toggle_label(self) -> str:
        self._wait_loaded()
        return self._browser.text("task-toggle")

    def _wait_loaded(self) -> None:
        self._browser.wait_for_attribute("task-list", "data-loaded", "true")

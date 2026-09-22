"""The page object of the task board: the flows, expressed in test ids and waits.

Two waits, two reasons. A page's first render — after navigating to `/` or to
`/board` — is announced by `data-loaded="true"`: nothing came before it on
that page, so "true" cannot mean anything but "the render happened". The
render after an action on an already-loaded page is different: `data-loaded`
was already `"true"` before the click, so waiting for it again races the
click's own handler and can pass on the old value before the new render ever
runs. For that case we read `data-render`, a counter that moves forward by
exactly one per render, before the click, and wait for it to become
`before + 1` — a value the page cannot have already had.
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
        before = int(self._browser.attribute("task-list", "data-render"))
        self._browser.click("task-toggle")
        self._browser.wait_for_attribute("task-list", "data-render", str(before + 1))

    def first_toggle_label(self) -> str:
        self._wait_loaded()
        return self._browser.text("task-toggle")

    def _wait_loaded(self) -> None:
        self._browser.wait_for_attribute("task-list", "data-loaded", "true")

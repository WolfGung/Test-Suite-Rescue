"""What a UI test needs from a browser, and nothing an engine-specific API offers.

Both drivers locate elements by `data-testid` only. That is the cure for
brittle selectors: an attribute that exists for the tests does not move when
a class is renamed or a heading is reworded, and a test that reads
`task-title` reads the same thing on either engine.
"""
from __future__ import annotations

import os
from typing import Protocol


class Browser(Protocol):
    def goto(self, url: str) -> None: ...
    def fill(self, test_id: str, text: str) -> None: ...
    def click(self, test_id: str) -> None: ...
    def text(self, test_id: str) -> str: ...
    def texts(self, test_id: str) -> list[str]: ...
    def attribute(self, test_id: str, name: str) -> str: ...
    def wait_for_attribute(self, test_id: str, name: str, value: str, timeout_s: float = 10.0) -> None: ...
    def wait_for_present(self, test_id: str, timeout_s: float = 10.0) -> None: ...
    def close(self) -> None: ...


def selector(test_id: str) -> str:
    return f"[data-testid='{test_id}']"


def open_browser(name: str | None = None, headless: bool | None = None) -> Browser:
    """The driver named by `UI_DRIVER` (or `name`): `playwright` by default, or `selenium`."""
    name = (name or os.environ.get("UI_DRIVER", "playwright")).lower()
    if headless is None:
        headless = os.environ.get("HEADLESS", "true").lower() != "false"
    if name == "playwright":
        from tests_after.ui.playwright_driver import PlaywrightBrowser

        return PlaywrightBrowser(headless=headless)
    if name == "selenium":
        from tests_after.ui.selenium_driver import SeleniumBrowser

        return SeleniumBrowser(headless=headless)
    raise ValueError(f"UI_DRIVER must be 'playwright' or 'selenium', got {name!r}")

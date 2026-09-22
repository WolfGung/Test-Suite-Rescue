"""The Playwright implementation of `Browser`: one Chromium, one page, explicit waits."""
from __future__ import annotations

from playwright.sync_api import expect, sync_playwright

from tests_after.ui.browser import selector


class PlaywrightBrowser:
    def __init__(self, headless: bool = True) -> None:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=headless)
        self._page = self._browser.new_page()
        self._page.set_default_timeout(10_000)

    def goto(self, url: str) -> None:
        self._page.goto(url, wait_until="domcontentloaded")

    def fill(self, test_id: str, text: str) -> None:
        self._page.locator(selector(test_id)).fill(text)

    def click(self, test_id: str) -> None:
        self._page.locator(selector(test_id)).first.click()

    def text(self, test_id: str) -> str:
        return self._page.locator(selector(test_id)).first.inner_text().strip()

    def texts(self, test_id: str) -> list[str]:
        return [item.strip() for item in self._page.locator(selector(test_id)).all_inner_texts()]

    def wait_for_attribute(self, test_id: str, name: str, value: str, timeout_s: float = 10.0) -> None:
        expect(self._page.locator(selector(test_id))).to_have_attribute(name, value, timeout=timeout_s * 1000)

    def wait_for_text(self, test_id: str, text: str, timeout_s: float = 10.0) -> None:
        expect(self._page.locator(selector(test_id)).first).to_have_text(text, timeout=timeout_s * 1000)

    def close(self) -> None:
        self._browser.close()
        self._playwright.stop()

"""The Selenium implementation of `Browser`: Chrome through Selenium Manager, explicit waits.

Selenium 4 finds or downloads a matching chromedriver on its own, so nothing
here names a driver path. Every read that can race the page goes through
`WebDriverWait`, never through a sleep.
"""
from __future__ import annotations

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from tests_after.ui.browser import selector


class SeleniumBrowser:
    def __init__(self, headless: bool = True) -> None:
        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1280,900")
        options.add_argument("--no-sandbox")
        self._driver = webdriver.Chrome(options=options)
        self._driver.set_page_load_timeout(20)

    def _find(self, test_id: str):
        return WebDriverWait(self._driver, 10).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, selector(test_id)) or None
        )

    def goto(self, url: str) -> None:
        self._driver.get(url)

    def fill(self, test_id: str, text: str) -> None:
        element = self._find(test_id)[0]
        element.clear()
        element.send_keys(text)

    def click(self, test_id: str) -> None:
        self._find(test_id)[0].click()

    def text(self, test_id: str) -> str:
        return self._find(test_id)[0].text.strip()

    def texts(self, test_id: str) -> list[str]:
        return [element.text.strip() for element in self._driver.find_elements(By.CSS_SELECTOR, selector(test_id))]

    def attribute(self, test_id: str, name: str) -> str:
        return self._find(test_id)[0].get_attribute(name) or ""

    def wait_for_attribute(self, test_id: str, name: str, value: str, timeout_s: float = 10.0) -> None:
        WebDriverWait(self._driver, timeout_s).until(
            lambda d: any(e.get_attribute(name) == value for e in d.find_elements(By.CSS_SELECTOR, selector(test_id)))
        )

    def wait_for_present(self, test_id: str, timeout_s: float = 10.0) -> None:
        WebDriverWait(self._driver, timeout_s).until(
            lambda d: bool(d.find_elements(By.CSS_SELECTOR, selector(test_id)))
        )

    def close(self) -> None:
        self._driver.quit()

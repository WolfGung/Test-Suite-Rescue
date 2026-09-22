"""Browser tests that pass on a quiet afternoon and fail in CI."""
from __future__ import annotations

import time

import pytest

from tests_before.conftest import BASE_URL

pytestmark = pytest.mark.sick


def test_form_creates_task(page) -> None:
    """Disease: hard-coded data, brittle selector, fixed sleep — the same title every run, inputs by XPath index, a sleep instead of a wait."""
    page.goto(f"{BASE_URL}/")
    page.locator("xpath=//form//input[1]").fill("Write the report")
    page.locator("xpath=//form//input[2]").fill("pavel")
    page.locator("text=Create").click()
    time.sleep(1.0)
    assert "Write the report" in page.content()


def test_board_lists_the_task(page) -> None:
    """Disease: render race, fixed sleep — reads the list after a fixed pause shorter than the board's render delay can be."""
    page.goto(f"{BASE_URL}/board")
    time.sleep(0.6)
    assert page.locator("ul.task-list li").count() >= 1


def test_board_shows_owner_in_second_column(page) -> None:
    """Disease: brittle selector, render race, order dependence — the owner is the second span of the first item, read after a sleep, of a task another test created."""
    page.goto(f"{BASE_URL}/board")
    time.sleep(0.6)
    assert page.locator("xpath=//ul/li[1]/span[2]").inner_text() == "pavel"


def test_toggle_marks_done(page) -> None:
    """Disease: brittle selector, fixed sleep — finds the button by its label, sleeps through the re-render."""
    page.goto(f"{BASE_URL}/board")
    time.sleep(0.6)
    page.locator("text=Done").first.click()
    time.sleep(0.3)
    assert "Undo" in page.content()


def test_nothing_else_on_the_board(page) -> None:
    """Disease: no cleanup, render race — expects exactly one task on a board nobody ever clears."""
    page.goto(f"{BASE_URL}/board")
    time.sleep(0.6)
    assert page.locator("ul.task-list li").count() == 1

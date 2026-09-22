"""Browser tests that pass on a quiet afternoon and fail in CI."""
from __future__ import annotations

import random
import time

import pytest

from tests_before.conftest import BASE_URL

pytestmark = pytest.mark.sick

#: Computed once at import, so every test in this run's process sees the same
#: value — and every run picks a new one, so the title never collides with an
#: earlier run's, only with this run's own leftovers (disease: no cleanup).
FORM_TITLE = f"Write the report {random.randint(1000, 9999)}"


def test_form_creates_task(page) -> None:
    """Disease: brittle selector, fixed sleep, no cleanup — inputs by XPath index, a sleep instead of a wait, and a task this run creates and never removes."""
    page.goto(f"{BASE_URL}/")
    page.locator("xpath=//form//input[1]").fill(FORM_TITLE)
    page.locator("xpath=//form//input[2]").fill("pavel")
    page.locator("text=Create").click()
    time.sleep(2.0)
    assert FORM_TITLE in page.content()


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
    time.sleep(2.0)
    assert "Undo" in page.content()


def test_nothing_else_on_the_board(page) -> None:
    """Disease: no cleanup, render race — expects exactly the two tasks this run created, on a board nobody ever clears, read after a fixed sleep."""
    page.goto(f"{BASE_URL}/board")
    time.sleep(0.6)
    assert page.locator("ul.task-list li").count() == 2

"""The board through a browser — the same checks on Playwright and on Selenium.

`UI_DRIVER=playwright` (default) or `UI_DRIVER=selenium` picks the engine; the
tests do not know which one they got, because they talk to a `Browser`
interface and a page object, never to a driver.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.ui


def test_the_form_creates_a_task_that_the_board_then_shows(board, unique_title) -> None:
    board.create(unique_title, "pavel")
    assert board.titles() == [unique_title], (
        f"the board should show exactly the task just created, it shows {board.titles()}"
    )


def test_the_board_names_the_owner_next_to_the_title(board, unique_title) -> None:
    board.create(unique_title, "pavel")
    assert board.owners() == ["pavel"], (
        f"the owner column should read the owner given on the form, it reads {board.owners()}"
    )


def test_toggling_marks_the_task_done_and_offers_undo(board, unique_title) -> None:
    board.create(unique_title, "pavel")
    board.toggle_first()
    assert board.first_toggle_label() == "Undo", "after marking a task done its button must offer to undo"


def test_a_task_created_through_the_api_appears_on_the_board(board, api, unique_title) -> None:
    api.post("/api/tasks", json={"title": unique_title, "owner": "api"})
    board.open_board()
    assert board.titles() == [unique_title], (
        f"the board should show the task created through the API, it shows {board.titles()}"
    )


def test_the_board_is_empty_when_nothing_was_created(board) -> None:
    board.open_board()
    assert board.titles() == [], f"a reset board must list nothing, it lists {board.titles()}"


def test_a_duplicate_title_is_refused_on_the_form(board, unique_title) -> None:
    board.create(unique_title, "pavel")
    board.create(unique_title, "pavel", expect_error=True)
    assert "already exists" in board.form_error(), (
        f"the form should explain the refusal, it says {board.form_error()!r}"
    )

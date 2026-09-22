"""The REST API of the task board, each check independent and self-explaining."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.api


def test_a_task_can_be_created(api, unique_title) -> None:
    response = api.post("/api/tasks", json={"title": unique_title, "owner": "pavel"})
    assert response.status_code == 201, f"expected 201 Created, got {response.status_code}: {response.text}"
    task = response.json()
    assert task["title"] == unique_title and task["owner"] == "pavel" and task["done"] is False, task


def test_a_duplicate_title_is_refused_with_409(api, unique_title) -> None:
    api.post("/api/tasks", json={"title": unique_title, "owner": "pavel"})
    response = api.post("/api/tasks", json={"title": unique_title, "owner": "someone else"})
    assert response.status_code == 409, f"a second task with the same title must be refused, got {response.status_code}"
    assert "already exists" in response.json()["detail"], response.json()


def test_the_list_holds_exactly_what_this_test_created(api, unique_title) -> None:
    created = api.post("/api/tasks", json={"title": unique_title, "owner": "pavel"}).json()
    tasks = api.get("/api/tasks").json()
    assert [task["id"] for task in tasks] == [created["id"]], (
        f"the board should hold this test's one task, it holds {tasks}"
    )


def test_toggling_marks_a_task_done_and_back(api, unique_title) -> None:
    created = api.post("/api/tasks", json={"title": unique_title, "owner": "pavel"}).json()
    done = api.patch(f"/api/tasks/{created['id']}").json()
    assert done["done"] is True, f"the first toggle must mark the task done: {done}"
    undone = api.patch(f"/api/tasks/{created['id']}").json()
    assert undone["done"] is False, f"the second toggle must mark it not done: {undone}"


def test_a_missing_task_answers_404(api) -> None:
    assert api.patch("/api/tasks/999999").status_code == 404, "toggling a task that does not exist must be a 404"
    assert api.delete("/api/tasks/999999").status_code == 404, "deleting a task that does not exist must be a 404"


def test_deleting_removes_the_task(api, unique_title) -> None:
    created = api.post("/api/tasks", json={"title": unique_title, "owner": "pavel"}).json()
    assert api.delete(f"/api/tasks/{created['id']}").status_code == 204
    assert api.get("/api/tasks").json() == [], "the board must be empty after its only task is deleted"


def test_the_form_creates_a_task_and_lands_on_the_board(api, unique_title) -> None:
    response = api.post("/tasks", data={"title": unique_title, "owner": "pavel"}, follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"].startswith("/board"), (
        f"the form must redirect to the board, got {response.status_code} {response.headers.get('location')}"
    )
    assert [task["title"] for task in api.get("/api/tasks").json()] == [unique_title]

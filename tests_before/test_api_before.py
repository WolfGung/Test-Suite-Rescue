"""API tests as they are often found: they work once, on one machine, in one order."""
from __future__ import annotations

import pytest

from tests_before.conftest import created_ids

pytestmark = pytest.mark.sick


def test_health(api) -> None:
    """Disease: silent assert — a bare comparison that says nothing when it fails."""
    assert api.get("/healthz").status_code == 200


def test_create_task(api) -> None:
    """Disease: hard-coded data, silent assert — the same title on every run, refused with 409 from the second run on."""
    response = api.post("/api/tasks", json={"title": "Write the report", "owner": "pavel"})
    assert response.status_code == 201
    created_ids.append(response.json()["id"])


def test_list_contains_created_task(api) -> None:
    """Disease: order dependence, shared state — reads what test_create_task left in a module-level list."""
    tasks = api.get("/api/tasks").json()
    assert any(task["id"] == created_ids[0] for task in tasks)


def test_toggle_marks_done(api) -> None:
    """Disease: order dependence — toggles the id the previous test created, and assumes it is still not done."""
    response = api.patch(f"/api/tasks/{created_ids[0]}")
    assert response.json()["done"] is True


def test_board_has_exactly_one_task(api) -> None:
    """Disease: no cleanup — counts every task on the board and expects only its own."""
    assert len(api.get("/api/tasks").json()) == 1

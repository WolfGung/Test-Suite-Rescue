"""The task board's state: an in-memory store with one rule, titles are unique.

The rule is what a test with a hard-coded title runs into on its second run —
which is one of the diseases the sick suite is there to show.
"""
from __future__ import annotations

from itertools import count


class DuplicateTitle(ValueError):
    pass


class TaskStore:
    def __init__(self) -> None:
        self._tasks: dict[int, dict] = {}
        self._ids = count(1)

    def add(self, title: str, owner: str) -> dict:
        title = title.strip()
        if not title:
            raise ValueError("title must not be blank")
        if any(task["title"] == title for task in self._tasks.values()):
            raise DuplicateTitle(f"a task titled {title!r} already exists")
        task = {"id": next(self._ids), "title": title, "owner": owner.strip(), "done": False}
        self._tasks[task["id"]] = task
        return dict(task)

    def list(self) -> list[dict]:
        return [dict(task) for task in self._tasks.values()]

    def get(self, task_id: int) -> dict | None:
        task = self._tasks.get(task_id)
        return dict(task) if task else None

    def toggle(self, task_id: int) -> dict | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        task["done"] = not task["done"]
        return dict(task)

    def delete(self, task_id: int) -> bool:
        return self._tasks.pop(task_id, None) is not None

    def reset(self) -> None:
        self._tasks.clear()
        self._ids = count(1)

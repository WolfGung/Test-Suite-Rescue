"""A small task board: a form, a list rendered by a script after a delay, and a REST API.

The delay is the one deliberate feature. `GET /board` serves an empty list and
a script that fetches the tasks after a random pause between
RENDER_DELAY_MIN_MS and RENDER_DELAY_MAX_MS (100–700 by default) and then sets
`data-loaded="true"` on the list. A test that waits for that attribute is
stable; a test that sleeps a fixed time is right only when the pause happens
to be shorter — which is exactly the kind of flakiness the sick suite shows
and the cured suite removes. Everything else is deterministic.
"""
from __future__ import annotations

import os
import random
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.store import DuplicateTitle, TaskStore

HERE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(HERE / "templates"))

#: The render delay range, in milliseconds, when the environment names none.
#: One definition for the whole repository: `tools/measure.py` imports it to
#: start the app the same way and to record the range in the measurement.
RENDER_DELAY_DEFAULT_MS = (100, 700)


class TaskIn(BaseModel):
    title: str
    owner: str = ""


def _render_delay_ms() -> int:
    default_low, default_high = RENDER_DELAY_DEFAULT_MS
    low = int(os.environ.get("RENDER_DELAY_MIN_MS", default_low))
    high = int(os.environ.get("RENDER_DELAY_MAX_MS", default_high))
    return random.randint(min(low, high), max(low, high))


def create_app(store: TaskStore | None = None) -> FastAPI:
    app = FastAPI(title="Task board", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store or TaskStore()
    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return templates.TemplateResponse(request, "index.html", {"error": None, "title": "", "owner": ""})

    @app.post("/tasks", response_class=HTMLResponse)
    async def create_from_form(request: Request):
        form = await request.form()
        title, owner = str(form.get("title", "")), str(form.get("owner", ""))
        try:
            task = app.state.store.add(title, owner)
        except (DuplicateTitle, ValueError) as exc:
            return templates.TemplateResponse(
                request, "index.html", {"error": str(exc), "title": title, "owner": owner}, status_code=400
            )
        return RedirectResponse(f"/board?created={task['id']}", status_code=303)

    @app.get("/board", response_class=HTMLResponse)
    async def board(request: Request):
        return templates.TemplateResponse(request, "board.html", {"delay_ms": _render_delay_ms()})

    @app.get("/api/tasks")
    async def list_tasks() -> list[dict]:
        return app.state.store.list()

    @app.post("/api/tasks", status_code=201)
    async def create_task(body: TaskIn):
        try:
            return app.state.store.add(body.title, body.owner)
        except DuplicateTitle as exc:
            return JSONResponse(status_code=409, content={"detail": f"title already exists: {exc}"})
        except ValueError as exc:
            return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.patch("/api/tasks/{task_id}")
    async def toggle_task(task_id: int):
        task = app.state.store.toggle(task_id)
        if task is None:
            return JSONResponse(status_code=404, content={"detail": "no such task"})
        return task

    @app.delete("/api/tasks/{task_id}", status_code=204)
    async def delete_task(task_id: int):
        if not app.state.store.delete(task_id):
            return JSONResponse(status_code=404, content={"detail": "no such task"})
        return Response(status_code=204)

    @app.post("/api/reset", status_code=204)
    async def reset():
        app.state.store.reset()
        return Response(status_code=204)

    return app


app = create_app()

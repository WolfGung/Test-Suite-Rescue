# tests_repo/test_ci_shape.py
"""The pipeline runs the cured suite on both engines and lets the sick suite fail in public."""
from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW_PATH = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
WORKFLOW = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
JOBS = WORKFLOW["jobs"]


def test_the_cured_suite_runs_on_both_drivers() -> None:
    assert JOBS["after"]["strategy"]["matrix"]["driver"] == ["playwright", "selenium"]


def test_the_sick_suite_is_allowed_to_fail_but_still_runs() -> None:
    assert JOBS["before"]["continue-on-error"] is True
    assert any("tests_before" in step.get("run", "") for step in JOBS["before"]["steps"])


def test_the_measurement_job_is_scheduled_and_manual() -> None:
    assert "schedule" in WORKFLOW[True] if True in WORKFLOW else "schedule" in WORKFLOW["on"]
    assert "measure" in JOBS and any("tools.measure" in step.get("run", "") for step in JOBS["measure"]["steps"])

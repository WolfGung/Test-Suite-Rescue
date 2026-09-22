# tests_repo/test_ci_shape.py
"""The pipeline runs the cured suite on both engines and lets the sick suite fail in public."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
WORKFLOW = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
JOBS = WORKFLOW["jobs"]


def test_the_cured_suite_runs_on_both_drivers() -> None:
    assert JOBS["after"]["strategy"]["matrix"]["driver"] == ["playwright", "selenium"]


def test_the_sick_suite_is_allowed_to_fail_but_still_runs() -> None:
    assert JOBS["before"]["continue-on-error"] is True
    assert any("tests_before" in step.get("run", "") for step in JOBS["before"]["steps"])


def test_the_measurement_job_is_scheduled_and_manual() -> None:
    # YAML reads the key `on:` as the boolean True, so the triggers live under
    # WORKFLOW[True] in every parser that follows the spec.
    triggers = WORKFLOW[True] if True in WORKFLOW else WORKFLOW["on"]
    assert "schedule" in triggers, triggers
    assert "measure" in JOBS and any("tools.measure" in step.get("run", "") for step in JOBS["measure"]["steps"])
    condition = JOBS["measure"]["if"]
    assert "schedule" in condition and "workflow_dispatch" in condition, condition
    assert "push" not in condition, condition


def test_the_measurement_job_says_the_numbers_came_from_the_runner() -> None:
    """The README promises a provenance line reading `github-runner`; the job is what writes it."""
    step = next(step for step in JOBS["measure"]["steps"] if "tools.measure" in step.get("run", ""))
    assert "--taken-on github-runner" in step["run"], step["run"]


def test_the_lint_job_covers_every_tests_directory_that_exists() -> None:
    """A new `tests_*` package must not silently fall outside ruff's scope."""
    test_dirs = sorted(p.name for p in REPO_ROOT.glob("tests_*") if p.is_dir())
    lint_step = next(step for step in JOBS["lint"]["steps"] if "ruff check" in step.get("run", ""))
    covered = lint_step["run"].split()
    missing = [name for name in test_dirs if name not in covered]
    assert not missing, f"{missing} exist on disk but are missing from the lint job's ruff line: {lint_step['run']!r}"

# tests_repo/test_ci_shape.py
"""The pipeline runs the cured suite on both engines and lets the sick suite fail in public.

Two workflow files, on purpose: `ci.yml` runs on what a commit decides and is
what the README badge follows; `measure.yml` takes the README's measurement
again every week and on request, so a measurement that moved never colours
the badge.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
WORKFLOW = yaml.safe_load((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))
MEASURE = yaml.safe_load((WORKFLOWS / "measure.yml").read_text(encoding="utf-8"))
JOBS = WORKFLOW["jobs"]


def _triggers(workflow: dict) -> dict:
    # YAML reads the key `on:` as the boolean True, so the triggers live under
    # workflow[True] in every parser that follows the spec.
    return workflow[True] if True in workflow else workflow["on"]


def _step(workflow: dict, job: str, text: str) -> dict:
    return next(step for step in workflow["jobs"][job]["steps"] if text in step.get("run", ""))


def test_the_cured_suite_runs_on_both_drivers() -> None:
    assert JOBS["after"]["strategy"]["matrix"]["driver"] == ["playwright", "selenium"]


def test_the_sick_suite_is_allowed_to_fail_but_still_runs() -> None:
    assert JOBS["before"]["continue-on-error"] is True
    assert any("tests_before" in step.get("run", "") for step in JOBS["before"]["steps"])


def test_ci_runs_on_pushes_and_pull_requests_only() -> None:
    """No schedule and no hand-started runs: the badge must read a verdict on a commit, nothing else."""
    assert set(_triggers(WORKFLOW)) == {"push", "pull_request"}, _triggers(WORKFLOW)
    assert not any("tools.measure" in step.get("run", "") for job in JOBS.values() for step in job["steps"])


def test_the_measurement_has_a_workflow_of_its_own_weekly_and_on_request() -> None:
    triggers = _triggers(MEASURE)
    assert set(triggers) == {"schedule", "workflow_dispatch"}, triggers
    assert [entry["cron"].split()[4] for entry in triggers["schedule"]] == ["1"], "once a week, on Mondays"
    assert list(MEASURE["jobs"]) == ["measure"]


def test_the_readme_says_where_and_when_the_measurement_runs() -> None:
    """The README promises a run every Monday from measure.yml; the schedule above is what keeps that true."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "every Monday" in readme and ".github/workflows/measure.yml" in readme


def test_the_measurement_job_says_the_numbers_came_from_the_runner() -> None:
    """The README promises a provenance line reading `github-runner`; the job is what writes it."""
    step = _step(MEASURE, "measure", "tools.measure")
    assert "--taken-on github-runner" in step["run"], step["run"]


def test_the_measurement_takes_as_many_runs_as_the_committed_file() -> None:
    """compare.py refuses a different number of runs, so the job must take exactly the committed count."""
    runs = json.loads((REPO_ROOT / "measurements" / "latest.json").read_text(encoding="utf-8"))["runs"]
    step = _step(MEASURE, "measure", "tools.measure")
    assert f"--runs {runs} " in step["run"], step["run"]


def test_the_measurement_is_compared_with_the_committed_file_and_kept() -> None:
    _step(MEASURE, "measure", "tools.compare measurements/latest.json measurements/ci-latest.json")
    upload = next(step for step in MEASURE["jobs"]["measure"]["steps"] if "upload-artifact" in step.get("uses", ""))
    assert upload["if"] == "always()" and upload["with"]["name"] == "measurements", upload
    assert "measurements/ci-latest.json" in upload["with"]["path"], upload


def test_every_job_pins_its_runner_image() -> None:
    """`ubuntu-latest` moves under a workflow without a commit; a pinned image moves only when this file does."""
    images = {
        f"{name}:{job_id}": job["runs-on"]
        for name, workflow in (("ci.yml", WORKFLOW), ("measure.yml", MEASURE))
        for job_id, job in workflow["jobs"].items()
    }
    assert set(images.values()) == {"ubuntu-24.04"}, images


def test_the_lint_job_covers_every_tests_directory_that_exists() -> None:
    """A new `tests_*` package must not silently fall outside ruff's scope."""
    test_dirs = sorted(p.name for p in REPO_ROOT.glob("tests_*") if p.is_dir())
    lint_step = _step(WORKFLOW, "lint", "ruff check")
    covered = lint_step["run"].split()
    missing = [name for name in test_dirs if name not in covered]
    assert not missing, f"{missing} exist on disk but are missing from the lint job's ruff line: {lint_step['run']!r}"

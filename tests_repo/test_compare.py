"""The gate that decides whether a fresh measurement still describes this suite.

`tools/compare.py` runs on a GitHub runner against a measurement the runner has
just taken and the one this repository committed. It has to let a runner be
slower than a laptop and a flaky test be flaky, and it has to stop the day the
counts or the failures really move — so both halves of that judgement get a
case here: what only a change in the code could move is refused, what the
runner or the coin toss moves is reported and accepted.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.compare import main

STUCK = ["m::board", "m::count", "m::create", "m::list", "m::toggle"]


def _sick(**changes: object) -> dict:
    """The sick suite as the committed file has it: five tests stuck after the first run, one flaky."""
    suite = {
        "runs": 20,
        "tests_per_run": 7,
        "total_seconds": 146.0,
        "failing_runs": 20,
        "always_failing": [],
        "broken_after_first_run": STUCK,
        "flaky": ["m::race"],
        "failure_counts": {**dict.fromkeys(STUCK, 19), "m::race": 2, "m::health": 0},
    }
    return {**suite, **changes}


def _cured(**changes: object) -> dict:
    suite = {
        "runs": 20,
        "tests_per_run": 2,
        "total_seconds": 118.9,
        "failing_runs": 0,
        "always_failing": [],
        "broken_after_first_run": [],
        "flaky": [],
        "failure_counts": {"m::a": 0, "m::b": 0},
    }
    return {**suite, **changes}


def _files(tmp_path: Path, fresh_before: dict, fresh_after: dict) -> list[str]:
    """The committed file and a fresh one, written where compare.py can read them."""
    committed, fresh = tmp_path / "latest.json", tmp_path / "ci-latest.json"
    committed.write_text(json.dumps({"suites": {"before": _sick(), "after": _cured()}}), encoding="utf-8")
    fresh.write_text(json.dumps({"suites": {"before": fresh_before, "after": fresh_after}}), encoding="utf-8")
    return [str(committed), str(fresh)]


def test_the_same_measurement_is_accepted(tmp_path: Path) -> None:
    assert main(_files(tmp_path, _sick(), _cured())) == 0


def test_a_slower_runner_is_reported_and_never_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Two locator timeouts and a slow machine move the times a long way; the suite is the same suite."""
    files = _files(tmp_path, _sick(total_seconds=400.0), _cured(total_seconds=300.0))
    assert main(files) == 0, "time depends on the runner, so it is printed, not judged"
    out = capsys.readouterr().out
    assert "146.0 s → 400.0 s, +174 % (reported only)" in out, out
    assert "118.9 s → 300.0 s, +152 % (reported only)" in out, out


def test_a_sick_series_whose_first_run_got_lucky_is_accepted(tmp_path: Path) -> None:
    """The first run is the only one luck decides: 19 failing runs of 20 against a committed 20 is the same suite."""
    fresh = _sick(failing_runs=19, flaky=[], failure_counts={**dict.fromkeys(STUCK, 19), "m::race": 0, "m::health": 0})
    assert main(_files(tmp_path, fresh, _cured())) == 0


def test_a_stuck_test_that_also_lost_the_first_run_is_still_the_same_test(tmp_path: Path) -> None:
    """A render race in run 1 moves a test from 'fails every run after the first' to 'fails every run'."""
    fresh = _sick(always_failing=["m::board"], broken_after_first_run=STUCK[1:])
    assert main(_files(tmp_path, fresh, _cured())) == 0


def test_a_different_set_of_flaky_tests_is_reported_and_accepted(tmp_path: Path) -> None:
    """Which of the sick suite's coin tosses a series catches is what the flaky row counts, not a change."""
    fresh = _sick(flaky=["m::race", "m::health"], failure_counts={**_sick()["failure_counts"], "m::health": 1})
    assert main(_files(tmp_path, fresh, _cured())) == 0


def test_one_failing_run_of_the_cured_suite_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fresh = _cured(failing_runs=1, flaky=["m::a"], failure_counts={"m::a": 1, "m::b": 0})
    assert main(_files(tmp_path, _sick(), fresh)) == 1, "a cured suite that fails one run in twenty is flaky again"
    assert "after: 1 of 20 runs failed" in capsys.readouterr().err


def test_a_sick_suite_that_fails_two_runs_fewer_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Every run after the first fails on purpose; luck can spare the first run, never a second one."""
    assert main(_files(tmp_path, _sick(failing_runs=18), _cured())) == 1
    assert "before: 18 of 20 runs failed" in capsys.readouterr().err


def test_a_test_that_stops_failing_after_the_first_run_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """State left behind is not luck: if one of those tests now passes, the disease it carried is gone."""
    fresh = _sick(broken_after_first_run=STUCK[1:], failure_counts={**_sick()["failure_counts"], "m::board": 0})
    assert main(_files(tmp_path, fresh, _cured())) == 1
    assert "tests failing every run after the first differ" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("runs", 10, "before: runs 20 committed vs 10 fresh"),
        ("tests_per_run", 8, "before: tests per run 7 committed vs 8 fresh"),
    ],
)
def test_a_different_count_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], field: str, value: int, message: str
) -> None:
    """A count is a count on any machine: a different one means a different suite, or a different measurement."""
    assert main(_files(tmp_path, _sick(**{field: value}), _cured())) == 1
    assert message in capsys.readouterr().err


def test_a_renamed_test_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fresh = _cured(failure_counts={"m::a": 0, "m::renamed": 0})
    assert main(_files(tmp_path, _sick(), fresh)) == 1
    assert "after: measured tests differ" in capsys.readouterr().err


def test_a_missing_fresh_file_says_where_it_comes_from(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    committed = tmp_path / "latest.json"
    committed.write_text(json.dumps({"suites": {"before": _sick(), "after": _cured()}}), encoding="utf-8")
    assert main([str(committed), str(tmp_path / "ci-latest.json")]) == 2
    assert "`measurements` artifact" in capsys.readouterr().err


def test_on_github_the_comparison_lands_on_the_run_page_as_a_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert main(_files(tmp_path, _sick(total_seconds=176.3), _cured())) == 0
    text = summary.read_text(encoding="utf-8")
    assert "| Suite | Runs | Tests per run | Failing runs |" in text, text
    assert "| before | 20 → 20 | 7 → 7 | 20 → 20 (±1) | 5 → 5 |" in text, text
    assert "agrees with the committed one" in text, text

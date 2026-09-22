"""The measurement tool's arithmetic, on junit files written by hand."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.measure
from tools.measure import (
    RunResult,
    main,
    parse_junit,
    render_block,
    render_table,
    summarise,
    update_readme,
)

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="3" failures="1" errors="0" time="2.500">
<testcase classname="tests_before.test_x" name="test_a" time="1.0"/>
<testcase classname="tests_before.test_x" name="test_b" time="1.0"><failure message="boom">boom</failure></testcase>
<testcase classname="tests_before.test_x" name="test_c" time="0.5"/>
</testsuite></testsuites>"""


def test_a_junit_file_is_read_into_counts_and_names(tmp_path: Path) -> None:
    path = tmp_path / "run.xml"
    path.write_text(JUNIT, encoding="utf-8")
    result = parse_junit(path)
    assert result == RunResult(
        tests=3, failures=1, errors=0, seconds=2.5,
        failed_names={"tests_before.test_x::test_b"},
        names={"tests_before.test_x::test_a", "tests_before.test_x::test_b", "tests_before.test_x::test_c"},
    )


def test_summary_tells_flaky_from_always_failing() -> None:
    names = {"m::a", "m::b", "m::c"}
    runs = [
        RunResult(3, 1, 0, 3.0, {"m::b"}, names),
        RunResult(3, 2, 0, 3.0, {"m::b", "m::c"}, names),
        RunResult(3, 1, 0, 3.0, {"m::b"}, names),
        RunResult(3, 0, 0, 3.0, set(), names),
    ]
    summary = summarise("before", runs)
    assert summary.runs == 4 and summary.tests_per_run == 3
    assert summary.total_seconds == 12.0 and summary.mean_test_seconds == 1.0
    assert summary.failing_runs == 3 and summary.failing_runs_share == 0.75
    assert summary.always_failing == [] and summary.flaky == ["m::b", "m::c"]
    assert summary.broken_after_first_run == []
    assert summary.failure_counts == {"m::a": 0, "m::b": 3, "m::c": 1}


def test_a_test_that_fails_every_run_is_not_flaky_it_is_broken() -> None:
    names = {"m::a"}
    runs = [RunResult(1, 1, 0, 1.0, {"m::a"}, names)] * 3
    summary = summarise("before", runs)
    assert summary.always_failing == ["m::a"] and summary.flaky == []
    assert summary.broken_after_first_run == []


def test_a_test_the_first_run_breaks_for_every_later_run_is_its_own_group() -> None:
    """Passing once and failing ever after is state left behind, not luck."""
    names = {"m::a", "m::b"}
    runs = [RunResult(2, 0, 0, 1.0, set(), names)] + [RunResult(2, 1, 0, 1.0, {"m::a"}, names)] * 4
    summary = summarise("before", runs)
    assert summary.broken_after_first_run == ["m::a"]
    assert summary.flaky == [], "a test the first run broke is not flaky"
    assert summary.always_failing == [], "it passed once, so it does not fail every run"
    assert summary.failure_counts == {"m::a": 4, "m::b": 0}


def test_the_table_counts_the_group_the_first_run_breaks_between_the_other_two() -> None:
    names = {"m::a"}
    runs = [RunResult(1, 0, 0, 1.0, set(), names)] + [RunResult(1, 1, 0, 1.0, {"m::a"}, names)] * 4
    before = summarise("before", runs)
    after = summarise("after", [RunResult(1, 0, 0, 0.5, set(), names)] * 5)
    table = render_table(before, after)
    assert "| Tests that fail every run after the first | 1 | 0 |" in table
    assert table.index("| Tests that fail every run |") < table.index("| Tests that fail every run after the first |")
    assert table.index("| Tests that fail every run after the first |") < table.index("(flaky)")


def test_the_table_states_both_suites_side_by_side() -> None:
    before = summarise("before", [RunResult(10, 3, 0, 40.0, {"m::x", "m::y", "m::z"}, {"m::x", "m::y", "m::z"})] * 2)
    after = summarise("after", [RunResult(13, 0, 0, 20.0, set(), {"m::x"})] * 2)
    table = render_table(before, after)
    assert "| Runs with at least one failure | 2 of 2 (100%) | 0 of 2 (0%) |" in table
    assert "| Total time for 2 runs | 80.0 s | 40.0 s |" in table


def test_two_runs_are_too_few_to_call_a_test_broken_by_the_first_one() -> None:
    """Passing once and failing once is luck until there are runs enough to tell."""
    names = {"m::a"}
    runs = [RunResult(1, 0, 0, 1.0, set(), names), RunResult(1, 1, 0, 1.0, {"m::a"}, names)]
    summary = summarise("before", runs)
    assert summary.broken_after_first_run == [], "two runs cannot distinguish state pollution from a flake"
    assert summary.flaky == ["m::a"], "until it can be told apart, an unexplained failure is flaky"


def _synthetic_payload() -> dict:
    """A measurement file as the tool writes one, small enough to read in a test."""
    from dataclasses import asdict

    names = {"tests_before.test_x::test_a"}
    before = summarise("before", [RunResult(1, 0, 0, 2.0, set(), names)] + [RunResult(1, 1, 0, 2.0, names, names)] * 4)
    after = summarise("after", [RunResult(2, 0, 0, 1.0, set(), {"tests_after.test_y::test_b"})] * 5)
    return {
        "taken_on": "a-laptop",
        "measured_at": "2026-09-23T10:00:00+00:00",
        "python": "3.12.14",
        "platform": "Linux-test",
        "render_delay_ms": [100, 700],
        "runs": 5,
        "suites": {"before": asdict(before), "after": asdict(after)},
    }


def test_the_block_carries_the_table_and_one_line_saying_where_it_came_from() -> None:
    block = render_block(_synthetic_payload())
    assert "| Tests per run | 1 | 2 |" in block
    assert block.rstrip("\n").endswith(
        "Measured on a-laptop — Linux-test, Python 3.12.14, 2026-09-23T10:00:00+00:00; "
        "render delay 100–700 ms; 5 runs of each suite."
    ), block


def test_render_writes_the_block_from_a_file_without_re_reading_a_single_junit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--render` is the hand-off: someone else's numbers in, README block out."""
    measurement = tmp_path / "ci-latest.json"
    measurement.write_text(json.dumps(_synthetic_payload()), encoding="utf-8")

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("--render must not read measurements/runs/")

    monkeypatch.setattr(tools.measure, "parse_junit", refuse)
    monkeypatch.setattr(tools.measure, "_summarise_runs", refuse)

    assert main(["--render", str(measurement)]) == 0
    printed = capsys.readouterr().out
    assert "| Tests per run | 1 | 2 |" in printed
    assert "Measured on a-laptop —" in printed
    assert "`tests_before/test_x.py::test_a` fails in 4 of 5 runs" in printed, printed


def test_the_readme_block_is_replaced_between_its_markers(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("intro\n<!-- measurements:start -->\nold\n<!-- measurements:end -->\noutro\n", encoding="utf-8")
    update_readme(readme, "| a | b |\n")
    expected = "intro\n<!-- measurements:start -->\n| a | b |\n<!-- measurements:end -->\noutro\n"
    assert readme.read_text(encoding="utf-8") == expected

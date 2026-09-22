"""The measurement tool's arithmetic, on junit files written by hand."""
from __future__ import annotations

from pathlib import Path

from tools.measure import RunResult, parse_junit, render_table, summarise, update_readme

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
    runs = [RunResult(2, 0, 0, 1.0, set(), names)] + [RunResult(2, 1, 0, 1.0, {"m::a"}, names)] * 3
    summary = summarise("before", runs)
    assert summary.broken_after_first_run == ["m::a"]
    assert summary.flaky == [], "a test the first run broke is not flaky"
    assert summary.always_failing == [], "it passed once, so it does not fail every run"
    assert summary.failure_counts == {"m::a": 3, "m::b": 0}


def test_the_table_counts_the_group_the_first_run_breaks_between_the_other_two() -> None:
    names = {"m::a"}
    runs = [RunResult(1, 0, 0, 1.0, set(), names)] + [RunResult(1, 1, 0, 1.0, {"m::a"}, names)] * 3
    before = summarise("before", runs)
    after = summarise("after", [RunResult(1, 0, 0, 0.5, set(), names)] * 4)
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


def test_the_readme_block_is_replaced_between_its_markers(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("intro\n<!-- measurements:start -->\nold\n<!-- measurements:end -->\noutro\n", encoding="utf-8")
    update_readme(readme, "| a | b |\n")
    expected = "intro\n<!-- measurements:start -->\n| a | b |\n<!-- measurements:end -->\noutro\n"
    assert readme.read_text(encoding="utf-8") == expected

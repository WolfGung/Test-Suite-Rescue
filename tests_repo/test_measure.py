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


PASS = frozenset()


def _run(names: set[str], failed: set[str] | frozenset = PASS, seconds: float = 1.0) -> RunResult:
    return RunResult(len(names), len(failed), 0, seconds, set(failed), set(names))


def test_summary_tells_flaky_from_always_failing() -> None:
    names = {"m::a", "m::b", "m::c"}
    runs = [
        RunResult(3, 2, 0, 3.0, {"m::b", "m::c"}, names),
        RunResult(3, 1, 0, 3.0, {"m::b"}, names),
        RunResult(3, 0, 0, 3.0, set(), names),
        RunResult(3, 1, 0, 3.0, {"m::b"}, names),
    ]
    summary = summarise("before", _run(names, {"m::b"}), runs)
    assert summary.runs == 4 and summary.tests_per_run == 3
    assert summary.total_seconds == 12.0 and summary.mean_test_seconds == 1.0
    assert summary.failing_runs == 3 and summary.failing_runs_share == 0.75
    assert summary.always_failing == [] and summary.flaky == ["m::b", "m::c"]
    assert summary.broken_after_first_run == []
    assert summary.failure_counts == {"m::a": 0, "m::b": 3, "m::c": 1}


def test_the_first_run_is_kept_out_of_every_count() -> None:
    """The run luck decides is not counted: runs, times, failing runs and failure counts are the runs after it."""
    names = {"m::a", "m::race"}
    summary = summarise("before", _run(names, {"m::race"}, seconds=9.0), [_run(names, {"m::a"})] * 4)
    assert summary.runs == 4 and summary.total_seconds == 4.0, "the first run's tests and time are not counted"
    assert summary.failing_runs == 4, "a coin toss in the first run cannot move the number of failing runs"
    assert summary.failure_counts == {"m::a": 4, "m::race": 0}
    assert summary.flaky == [], "a test that failed only the first run has no failure among the counted runs"


def test_a_test_that_fails_every_run_is_not_flaky_it_is_broken() -> None:
    names = {"m::a"}
    summary = summarise("before", _run(names, names), [_run(names, names)] * 3)
    assert summary.always_failing == ["m::a"] and summary.flaky == []
    assert summary.broken_after_first_run == []


def test_a_test_the_first_run_breaks_for_every_later_run_is_its_own_group() -> None:
    """Passing once and failing ever after is state left behind, not luck."""
    names = {"m::a", "m::b"}
    summary = summarise("before", _run(names), [_run(names, {"m::a"})] * 4)
    assert summary.broken_after_first_run == ["m::a"]
    assert summary.flaky == [], "a test the first run broke is not flaky"
    assert summary.always_failing == [], "it passed once, so it does not fail every run"
    assert summary.failure_counts == {"m::a": 4, "m::b": 0}


def test_the_table_counts_the_group_the_first_run_breaks_between_the_other_two() -> None:
    names = {"m::a"}
    before = summarise("before", _run(names), [_run(names, names)] * 4)
    after = summarise("after", _run(names, seconds=0.5), [_run(names, seconds=0.5)] * 4)
    table = render_table(before, after)
    assert "| Tests that fail every run after the first | 1 | 0 |" in table
    assert table.index("| Tests that fail every run |") < table.index("| Tests that fail every run after the first |")
    assert table.index("| Tests that fail every run after the first |") < table.index("(flaky)")


def test_the_table_states_both_suites_side_by_side() -> None:
    sick = RunResult(10, 3, 0, 40.0, {"m::x", "m::y", "m::z"}, {"m::x", "m::y", "m::z"})
    cured = RunResult(13, 0, 0, 20.0, set(), {"m::x"})
    table = render_table(summarise("before", sick, [sick] * 2), summarise("after", cured, [cured] * 2))
    assert "| Runs with at least one failure | 2 of 2 (100%) | 0 of 2 (0%) |" in table
    assert "| Total time for 2 runs | 80.0 s | 40.0 s |" in table


def test_two_runs_are_too_few_to_call_a_test_broken_by_the_first_one() -> None:
    """Passing once and failing once is luck until there are runs enough to tell."""
    names = {"m::a"}
    summary = summarise("before", _run(names), [_run(names, names)])
    assert summary.broken_after_first_run == [], "two runs cannot distinguish state pollution from a flake"
    assert summary.flaky == ["m::a"], "until it can be told apart, an unexplained failure is flaky"


def _fake_pytest(fail_after_first: str) -> object:
    """Stands in for subprocess.run: writes the junit file a run would, failing one test from the second run on."""
    calls: list[str] = []

    def run(command: list[str], **kwargs: object) -> None:
        junit = Path(next(arg for arg in command if arg.startswith("--junitxml="))[len("--junitxml="):])
        failing = '<failure message="409">409</failure>' if calls else ""
        calls.append(junit.name)
        junit.write_text(
            '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" tests="2" '
            f'failures="{1 if failing else 0}" errors="0" time="1.0">'
            f'<testcase classname="tests_before.test_x" name="{fail_after_first}" time="0.5">{failing}</testcase>'
            '<testcase classname="tests_before.test_x" name="test_health" time="0.5"/>'
            "</testsuite></testsuites>",
            encoding="utf-8",
        )

    run.calls = calls  # type: ignore[attr-defined]
    return run


def test_a_series_is_a_first_run_and_then_the_runs_it_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every series opens with one run against the fresh board, kept as -00.xml, and counts the runs after it."""
    fake = _fake_pytest("test_create_task")
    monkeypatch.setattr(tools.measure.subprocess, "run", fake)
    first, runs = tools.measure._run_suite("before", 3, "http://app", tmp_path)
    assert fake.calls == ["before-00.xml", "before-01.xml", "before-02.xml", "before-03.xml"]
    assert first.failed_names == set() and len(runs) == 3
    summary = summarise("before", first, runs)
    assert summary.failing_runs == 3, "every counted run comes after the first, so every one meets its leftovers"


def test_summarising_from_disk_takes_the_00_file_as_the_first_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tools.measure.subprocess, "run", _fake_pytest("test_create_task"))
    tools.measure._run_suite("before", 4, "http://app", tmp_path)
    summaries, first_failed = tools.measure._summarise_runs(["before"], tmp_path)
    assert summaries["before"].runs == 4 and summaries["before"].failing_runs == 4
    assert summaries["before"].broken_after_first_run == ["tests_before.test_x::test_create_task"]
    assert first_failed == {"before": []}


def test_runs_taken_without_a_first_run_are_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A series that counted its first run is a different measurement, not one to re-count silently."""
    monkeypatch.setattr(tools.measure.subprocess, "run", _fake_pytest("test_create_task"))
    tools.measure._run_suite("before", 2, "http://app", tmp_path)
    (tmp_path / "before-00.xml").unlink()
    with pytest.raises(SystemExit, match="no first run for tests_before"):
        tools.measure._summarise_runs(["before"], tmp_path)


def _synthetic_payload() -> dict:
    """A measurement file as the tool writes one, small enough to read in a test."""
    from dataclasses import asdict

    names = {"tests_before.test_x::test_a"}
    before = summarise("before", RunResult(1, 0, 0, 2.0, set(), names), [RunResult(1, 1, 0, 2.0, names, names)] * 4)
    cured = RunResult(2, 0, 0, 1.0, set(), {"tests_after.test_y::test_b"})
    after = summarise("after", cured, [cured] * 4)
    return {
        "taken_on": "a-laptop",
        "measured_at": "2026-09-23T10:00:00+00:00",
        "python": "3.12.14",
        "platform": "Linux-test",
        "render_delay_ms": [100, 700],
        "runs": 4,
        "first_run_failed": {"before": [], "after": []},
        "suites": {"before": asdict(before), "after": asdict(after)},
    }


def test_the_block_carries_the_table_and_one_line_saying_where_it_came_from() -> None:
    block = render_block(_synthetic_payload())
    assert "| Tests per run | 1 | 2 |" in block
    assert block.rstrip("\n").endswith(
        "Measured on a-laptop — Linux-test, Python 3.12.14, 2026-09-23T10:00:00+00:00; "
        "render delay 100–700 ms; 4 runs of each suite."
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
    assert "`tests_before/test_x.py::test_a` fails in 4 of 4 runs" in printed, printed


def test_the_readme_block_is_replaced_between_its_markers(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("intro\n<!-- measurements:start -->\nold\n<!-- measurements:end -->\noutro\n", encoding="utf-8")
    update_readme(readme, "| a | b |\n")
    expected = "intro\n<!-- measurements:start -->\n| a | b |\n<!-- measurements:end -->\noutro\n"
    assert readme.read_text(encoding="utf-8") == expected

# tools/compare.py
"""Compare a fresh measurement with the committed one: counts and failures strictly, times in the report only.

A runner can make a suite slower; it cannot make it run a different number of
tests or fail a different set of them. So the comparison fails on what only a
change in the code could move, and prints the rest:

- the number of runs, the tests per run and the tests measured must be the same;
- the tests that fail every run after the first — whether or not they also
  failed the first — must be the same tests, because that is state left
  behind, not luck;
- both suites must fail exactly as many runs as the committed file says: the
  cured suite none, the sick suite every one. tools/measure.py counts only the
  runs after a first run against the fresh board, and every one of those
  fails on the state the first run left behind; the first run, the one luck
  decides, is never counted, so there is no coin toss left in this number;
- total times are printed with their change and never fail the comparison:
  GitHub's runners are not the same machine from one week to the next, and a
  single locator timeout in the sick suite adds thirty seconds on its own.

Which tests a series catches being flaky is the coin toss the README's flaky
row counts, so the flaky lists are printed, not compared. A failure here means
the README describes a suite that no longer behaves that way: re-measure and
re-commit measurements/latest.json.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HEADER = (
    "Suite", "Runs", "Tests per run", "Failing runs", "Fail every run after the first", "Flaky tests", "Total time",
)


def _fail_every_run_after_the_first(summary: dict) -> set[str]:
    """The tests that fail from the second run on, whatever the first run did."""
    return set(summary["always_failing"]) | set(summary["broken_after_first_run"])


def compare_suite(suite: str, old: dict, new: dict) -> list[str]:
    """What differs beyond the rules between the committed and the fresh summary of one suite."""
    problems = []
    for key, label in (("runs", "runs"), ("tests_per_run", "tests per run")):
        if old[key] != new[key]:
            problems.append(f"{suite}: {label} {old[key]} committed vs {new[key]} fresh")
    old_names, new_names = set(old["failure_counts"]), set(new["failure_counts"])
    if old_names != new_names:
        problems.append(
            f"{suite}: measured tests differ — committed only {sorted(old_names - new_names)}, "
            f"fresh only {sorted(new_names - old_names)}"
        )
    old_stuck, new_stuck = _fail_every_run_after_the_first(old), _fail_every_run_after_the_first(new)
    if old_stuck != new_stuck:
        problems.append(
            f"{suite}: tests failing every run after the first differ — committed only "
            f"{sorted(old_stuck - new_stuck)}, fresh only {sorted(new_stuck - old_stuck)}"
        )
    if old["failing_runs"] != new["failing_runs"]:
        problems.append(
            f"{suite}: {new['failing_runs']} of {new['runs']} runs failed, the committed file says "
            f"{old['failing_runs']} of {old['runs']}"
        )
    return problems


def _time_change(old_seconds: float, new_seconds: float) -> str:
    if not old_seconds:
        return "no committed time"
    return f"{(new_seconds - old_seconds) / old_seconds * 100:+.0f} %"


def report_rows(committed: dict, fresh: dict) -> list[tuple[str, ...]]:
    """One row per suite, committed value → fresh value, for the log and the run's summary."""
    rows = []
    for suite in ("before", "after"):
        old, new = committed[suite], fresh[suite]
        rows.append((
            suite,
            f"{old['runs']} → {new['runs']}",
            f"{old['tests_per_run']} → {new['tests_per_run']}",
            f"{old['failing_runs']} → {new['failing_runs']}",
            f"{len(_fail_every_run_after_the_first(old))} → {len(_fail_every_run_after_the_first(new))}",
            f"{len(old['flaky'])} → {len(new['flaky'])} (reported only)",
            f"{old['total_seconds']} s → {new['total_seconds']} s, "
            f"{_time_change(old['total_seconds'], new['total_seconds'])} (reported only)",
        ))
    return rows


def _write_run_summary(rows: list[tuple[str, ...]], verdict: str) -> None:
    """On GitHub Actions, put the same comparison on the run's page as a table."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = ["### Fresh measurement against measurements/latest.json", ""]
    lines += ["| " + " | ".join(HEADER) + " |", "|" + " --- |" * len(HEADER)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    lines += ["", verdict, ""]
    with open(path, "a", encoding="utf-8") as summary:
        summary.write("\n".join(lines))


def main(argv: list[str]) -> int:
    missing = [name for name in argv[:2] if not Path(name).exists()]
    if missing:
        print(
            f"missing: {', '.join(missing)} — the second file is the `measurements` artifact of the weekly "
            "measurement (measurements/ci-latest.json); download it first",
            file=sys.stderr,
        )
        return 2
    committed = json.loads(Path(argv[0]).read_text(encoding="utf-8"))["suites"]
    fresh = json.loads(Path(argv[1]).read_text(encoding="utf-8"))["suites"]
    rows = report_rows(committed, fresh)
    for row in rows:
        details = "; ".join(f"{name.lower()} {value}" for name, value in zip(HEADER[1:], row[1:], strict=True))
        print(f"{row[0]}: {details}")
    problems = [
        problem for suite in ("before", "after") for problem in compare_suite(suite, committed[suite], fresh[suite])
    ]
    if problems:
        _write_run_summary(rows, "The fresh measurement differs from the committed one:\n\n" + "\n".join(
            f"- {problem}" for problem in problems
        ))
        print("\n".join(problems), file=sys.stderr)
        return 1
    verdict = "The fresh measurement agrees with the committed one: counts and failures match; times are reported only."
    _write_run_summary(rows, verdict)
    print(verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

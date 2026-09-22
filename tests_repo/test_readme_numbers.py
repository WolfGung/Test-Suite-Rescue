"""Every number in the README's before/after table is the one in measurements/latest.json."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from tools.measure import END, START, SuiteSummary, render_table

ROOT = Path(__file__).resolve().parents[1]


def _block(text: str) -> str:
    start, end = text.index(START) + len(START), text.index(END)
    return text[start:end].strip("\n") + "\n"


def test_the_table_in_the_readme_is_the_one_rendered_from_the_measurement_file() -> None:
    payload = json.loads((ROOT / "measurements" / "latest.json").read_text(encoding="utf-8"))
    before = SuiteSummary(**payload["suites"]["before"])
    after = SuiteSummary(**payload["suites"]["after"])
    expected = render_table(before, after)
    actual = _block((ROOT / "README.md").read_text(encoding="utf-8"))
    assert actual == expected, "README's measurement table differs from measurements/latest.json — run `make measure`"


def test_the_measurement_file_says_where_and_when_it_was_taken() -> None:
    payload = json.loads((ROOT / "measurements" / "latest.json").read_text(encoding="utf-8"))
    assert payload["runs"] >= 20 and payload["measured_at"] and payload["platform"], payload
    after_failing_runs = payload["suites"]["after"]["failing_runs"]
    assert after_failing_runs == 0, "the cured suite is published only from a run where it never failed"


def _live_collection_count(suite: str) -> int:
    """How many tests `tests_<suite>` collects right now, asked the same way pytest itself would."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", f"tests_{suite}", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    last_line = result.stdout.strip().splitlines()[-1]
    match = re.match(r"(\d+) tests? collected", last_line)
    assert match, f"could not read a test count from tests_{suite}'s collection output: {last_line!r}"
    return int(match.group(1))


def test_the_tests_per_run_count_matches_what_the_suite_collects_live() -> None:
    """A stale `tests_per_run` would mean the table was measured against a different suite."""
    payload = json.loads((ROOT / "measurements" / "latest.json").read_text(encoding="utf-8"))
    for suite in ("before", "after"):
        recorded = payload["suites"][suite]["tests_per_run"]
        live = _live_collection_count(suite)
        assert recorded == live, (
            f"measurements/latest.json says {suite}.tests_per_run={recorded}, but tests_{suite} "
            f"currently collects {live} tests — run `make measure`"
        )

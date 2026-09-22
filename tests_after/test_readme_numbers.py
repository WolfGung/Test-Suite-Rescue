"""Every number in the README's before/after table is the one in measurements/latest.json."""
from __future__ import annotations

import json
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

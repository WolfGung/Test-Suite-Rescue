"""Every number the documents state is the one in measurements/latest.json.

The README's block — the table and the line saying on what machine, with what
delay range and when the numbers were taken — is rendered from that file, and
the per-test counts the diagnosis quotes ("fails in 19 of 20 runs") are read
back out of it too, so a re-measurement that moves a number cannot leave a
document behind.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from tools.measure import END, START, render_block

ROOT = Path(__file__).resolve().parents[1]

#: `tests_before/test_api_before.py::test_create_task` … fails in 19 of 20 runs
CITATION = re.compile(r"`tests_before/(\w+)\.py::(test_\w+)`[^`]{0,240}?fails in (\d+) of (\d+) runs")
#: "Four of the sick suite's tests never fail at all" — the number is checked
NEVER_FAILS = re.compile(r"(\w+) of the sick suite's tests never fail at all")
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


def _payload() -> dict:
    return json.loads((ROOT / "measurements" / "latest.json").read_text(encoding="utf-8"))


def _block(text: str) -> str:
    start, end = text.index(START) + len(START), text.index(END)
    return text[start:end].strip("\n") + "\n"


def test_the_block_in_the_readme_is_the_one_rendered_from_the_measurement_file() -> None:
    """Table and provenance line both: the delay range and the machine are pinned too."""
    expected = render_block(_payload())
    actual = _block((ROOT / "README.md").read_text(encoding="utf-8"))
    assert actual == expected, (
        "README's measurement block differs from measurements/latest.json — run `make measure`, or "
        "`python3 -m tools.measure --render measurements/latest.json --update-readme`"
    )


def test_the_measurement_file_says_where_and_when_it_was_taken() -> None:
    payload = _payload()
    assert payload["runs"] >= 20 and payload["measured_at"] and payload["platform"], payload
    assert payload.get("taken_on"), "a measurement must name the machine it was taken on, so the README can say it"
    after_failing_runs = payload["suites"]["after"]["failing_runs"]
    assert after_failing_runs == 0, "the cured suite is published only from a run where it never failed"


def test_every_failure_count_the_diagnosis_cites_is_the_measured_one() -> None:
    """The diagnosis says how often each sick test failed; the measurement says the same."""
    before = _payload()["suites"]["before"]
    counts, runs = before["failure_counts"], before["runs"]
    citations = CITATION.findall((ROOT / "docs" / "diagnosis.md").read_text(encoding="utf-8"))
    assert citations, "docs/diagnosis.md should say how often a test fails, as `…::test_x` … fails in N of M runs"
    for module, test, fails, of in citations:
        name = f"tests_before.{module}::{test}"
        assert name in counts, f"docs/diagnosis.md cites {name}, which the measurement does not know"
        assert int(of) == runs, f"docs/diagnosis.md counts {test} over {of} runs, the measurement took {runs}"
        assert int(fails) == counts[name], (
            f"docs/diagnosis.md says {name} fails in {fails} of {of} runs, "
            f"measurements/latest.json says {counts[name]} — re-read the file or re-measure"
        )


def test_the_diagnosis_cites_every_sick_test_and_no_other() -> None:
    """A disease nobody quoted a number for is a disease nobody proved."""
    counts = _payload()["suites"]["before"]["failure_counts"]
    citations = CITATION.findall((ROOT / "docs" / "diagnosis.md").read_text(encoding="utf-8"))
    cited = [f"tests_before.{module}::{test}" for module, test, _, _ in citations]
    assert set(cited) == set(counts), (
        f"cited but not measured: {sorted(set(cited) - set(counts))}; "
        f"measured but never cited: {sorted(set(counts) - set(cited))}"
    )
    twice = sorted({name for name in cited if cited.count(name) > 1})
    assert not twice, f"docs/diagnosis.md quotes a failure count twice for {twice}; one citation per test"


def test_the_count_of_tests_that_never_fail_is_the_measured_one() -> None:
    """The sentence that closes the diagnosis states a number; the measurement decides it."""
    counts = _payload()["suites"]["before"]["failure_counts"]
    never = sorted(name for name, count in counts.items() if count == 0)
    doc = (ROOT / "docs" / "diagnosis.md").read_text(encoding="utf-8")
    match = NEVER_FAILS.search(doc)
    assert match, "docs/diagnosis.md should say how many sick tests never fail: '<N> of the sick suite's tests never…'"
    stated = WORDS.get(match.group(1).lower())
    assert stated is not None, f"the count in {match.group(0)!r} should be a word from one to ten"
    assert stated == len(never), (
        f"docs/diagnosis.md says {match.group(1)} tests never fail; the measurement has {len(never)}: {never}"
    )


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

"""The documents keep their promises: every disease explained, every link and test real.

`docs/diagnosis.md` is the repository's explanation of itself, and an
explanation drifts away from the code it describes unless something holds it
there. These checks are that something: the diagnosis has a section for every
disease the sick suite names in its own docstrings, every test it cites
exists, every relative link in the documents points at a file that is there,
every anchor the README's table links to is a heading that is there, the
seconds the diagnosis charges to sleeping are the seconds the sick suite
sleeps, and the README still tells a reader the virtualenv, the three
commands and the second engine.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISEASES = {
    "fixed sleep",
    "order dependence",
    "shared state",
    "brittle selector",
    "render race",
    "hard-coded data",
    "no cleanup",
    "silent assert",
}
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def _documents() -> list[Path]:
    return [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]


def _diseases_in_tests() -> set[str]:
    found: set[str] = set()
    for path in (ROOT / "tests_before").glob("test_*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.search(r"Disease:\s*(.+?)\s*—", line)
            if match:
                found |= {item.strip() for item in match.group(1).split(",")}
    return found


def test_every_disease_the_sick_suite_names_is_a_section_of_the_diagnosis() -> None:
    doc = (ROOT / "docs" / "diagnosis.md").read_text(encoding="utf-8")
    headings = {line[3:].strip().lower() for line in doc.splitlines() if line.startswith("## ")}
    diseases = _diseases_in_tests()
    assert diseases == DISEASES, f"the sick suite names {sorted(diseases)}, the plan names {sorted(DISEASES)}"
    missing = {d for d in DISEASES if d not in headings}
    assert not missing, f"diseases without a section in docs/diagnosis.md: {sorted(missing)}"


def test_every_test_the_diagnosis_cites_exists() -> None:
    doc = (ROOT / "docs" / "diagnosis.md").read_text(encoding="utf-8")
    cited = set(re.findall(r"`(tests_(?:before|after)/[\w/]+\.py)::(test_\w+)`", doc))
    assert cited, "the diagnosis should cite tests by `path::name`"
    for path, name in cited:
        text = (ROOT / path).read_text(encoding="utf-8")
        assert f"def {name}(" in text, f"{path}::{name} is cited but does not exist"


def test_every_relative_link_in_the_documents_points_at_something_that_is_there() -> None:
    """A dead link in a README is the first thing a reader finds and the last thing an author sees."""
    broken: list[str] = []
    for document in _documents():
        for target in LINK.findall(document.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path = (document.parent / target.split("#", 1)[0]).resolve()
            if not path.exists():
                broken.append(f"{document.relative_to(ROOT)} -> {target}")
    assert not broken, f"links pointing at nothing: {broken}"


def test_the_readme_states_the_three_commands_and_the_two_drivers() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for command in ("python3 -m venv .venv", "make install", "make test", "make measure", "UI_DRIVER=selenium"):
        assert command in readme, f"README must show {command}"


def _slug(heading: str) -> str:
    """GitHub's anchor for a heading: lowercase, punctuation dropped, spaces to hyphens."""
    kept = "".join(char for char in heading.lower() if char.isalnum() or char in " -_")
    return kept.strip().replace(" ", "-")


def test_every_anchor_the_readme_points_at_is_a_heading_of_the_diagnosis() -> None:
    """The table's eight links land on a section, not at the top of the page."""
    diagnosis = (ROOT / "docs" / "diagnosis.md").read_text(encoding="utf-8")
    anchors = {_slug(line[3:].strip()) for line in diagnosis.splitlines() if line.startswith("## ")}
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    wanted = re.findall(r"\(docs/diagnosis\.md#([\w-]+)\)", readme)
    assert len(wanted) == len(DISEASES), f"the README's table should link one section per disease, it links {wanted}"
    missing = [anchor for anchor in wanted if anchor not in anchors]
    assert not missing, f"README links to {missing}, which no `## ` heading of docs/diagnosis.md answers: {anchors}"


def test_the_seconds_the_diagnosis_charges_to_sleeping_are_the_ones_in_the_sick_suite() -> None:
    """`time.sleep(…)` is the one cost a reader can add up by hand — so it must add up."""
    slept = 0.0
    for path in sorted((ROOT / "tests_before").glob("*.py")):
        slept += sum(float(value) for value in re.findall(r"time\.sleep\(([\d.]+)\)", path.read_text(encoding="utf-8")))
    diagnosis = (ROOT / "docs" / "diagnosis.md").read_text(encoding="utf-8")
    match = re.search(r"the sleeps alone are ([\d.]+) s", diagnosis)
    assert match, "docs/diagnosis.md should say what the sleeps cost: 'the sleeps alone are <N> s'"
    assert float(match.group(1)) == round(slept, 3), (
        f"docs/diagnosis.md charges {match.group(1)} s to sleeping, tests_before sleeps {round(slept, 3)} s per run"
    )

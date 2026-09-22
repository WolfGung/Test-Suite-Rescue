"""Run both suites N times against one live app and write down what happened.

The app is started once and never restarted between runs: that is the
condition a shared staging environment gives a suite, and it is where two of
the sick suite's diseases show — a hard-coded title is refused from the
second run on, and a board nobody clears keeps growing. The board is reset
once before each suite's series, so the two suites start from the same state.

Every run writes a junit file under measurements/runs/; the summary of all of
them goes to measurements/latest.json and, with --update-readme, into the
README between the measurements markers. Nothing in the README is typed by
hand. With --summarise-only the summary is rebuilt from the junit files that
are already under measurements/runs/, so the same runs can be counted a new
way without measuring again.

Taking over someone else's numbers is two commands and no arithmetic. Download
the weekly `measure` job's artifact and then:

    cp ci-latest.json measurements/latest.json
    python3 -m tools.measure --render measurements/latest.json --update-readme

--render reads that one file, writes the README block from it — the table and
the provenance line naming the machine the numbers were taken on — and prints
the per-test sentences docs/diagnosis.md carries ("… fails in 19 of 20 runs")
in the exact form the citation pin reads, ready to paste. It reads no junit
file and runs no test.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import re
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.request import urlopen

# The tool may know the application it measures; it must not import either
# suite, or the measurement would depend on the thing being measured.
from app.main import RENDER_DELAY_DEFAULT_MS

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- measurements:start -->"
END = "<!-- measurements:end -->"
DEFAULT_TAKEN_ON = "developer-machine"


@dataclass(frozen=True)
class RunResult:
    tests: int
    failures: int
    errors: int
    seconds: float
    failed_names: set[str] = field(default_factory=set)
    names: set[str] = field(default_factory=set)

    @property
    def failed(self) -> bool:
        return self.failures + self.errors > 0


@dataclass
class SuiteSummary:
    suite: str
    runs: int
    tests_per_run: int
    total_seconds: float
    mean_test_seconds: float
    failing_runs: int
    failing_runs_share: float
    always_failing: list[str]
    broken_after_first_run: list[str]
    flaky: list[str]
    failure_counts: dict[str, int]


def parse_junit(path: Path) -> RunResult:
    root = ET.parse(path).getroot()
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    tests = failures = errors = 0
    seconds = 0.0
    failed: set[str] = set()
    names: set[str] = set()
    for suite in suites:
        tests += int(suite.get("tests", 0))
        failures += int(suite.get("failures", 0))
        errors += int(suite.get("errors", 0))
        seconds += float(suite.get("time", 0.0))
        for case in suite.findall("testcase"):
            name = f"{case.get('classname')}::{case.get('name')}"
            names.add(name)
            if case.find("failure") is not None or case.find("error") is not None:
                failed.add(name)
    return RunResult(tests, failures, errors, round(seconds, 3), failed, names)


#: Below this many runs, "passed once and failed ever after" is indistinguishable
#: from luck — at four runs a merely flaky test reaches that shape about once in
#: sixteen — so the group is only claimed from five runs on.
MIN_RUNS_FOR_BROKEN_AFTER_FIRST = 5


def summarise(suite: str, runs: list[RunResult]) -> SuiteSummary:
    """Count the runs into the four groups the README's table names.

    A test that passes the first run and fails every run after it is not flaky
    and not simply broken: the first run broke it for all the runs that follow,
    by leaving a task, a title or an id behind. It is the signature of state
    nobody cleans up, and it deserves its own group — but only when there are
    enough runs for the shape to mean anything. Under
    MIN_RUNS_FOR_BROKEN_AFTER_FIRST runs a flaky test that happened to pass
    first and fail afterwards has the same shape, so those tests stay in
    `flaky`, where an unexplained failure belongs until it is explained.
    """
    if not runs:
        raise ValueError(f"no runs to summarise for {suite}")
    total = sum(run.seconds for run in runs)
    tests = sum(run.tests for run in runs)
    failing_runs = sum(1 for run in runs if run.failed)
    names = sorted(set().union(*(run.names for run in runs)))
    counts = {name: sum(1 for run in runs if name in run.failed_names) for name in names}
    broken_after_first = [
        name
        for name in names
        if len(runs) >= MIN_RUNS_FOR_BROKEN_AFTER_FIRST
        and counts[name] == len(runs) - 1
        and name not in runs[0].failed_names
    ]
    return SuiteSummary(
        suite=suite,
        runs=len(runs),
        tests_per_run=round(tests / len(runs)),
        total_seconds=round(total, 1),
        mean_test_seconds=round(total / tests, 2) if tests else 0.0,
        failing_runs=failing_runs,
        failing_runs_share=round(failing_runs / len(runs), 2),
        always_failing=[name for name in names if counts[name] == len(runs)],
        broken_after_first_run=broken_after_first,
        flaky=[name for name in names if 0 < counts[name] < len(runs) and name not in broken_after_first],
        failure_counts=counts,
    )


def render_table(before: SuiteSummary, after: SuiteSummary) -> str:
    def share(summary: SuiteSummary) -> str:
        return f"{summary.failing_runs} of {summary.runs} ({round(summary.failing_runs_share * 100)}%)"

    rows = [
        ("Tests per run", str(before.tests_per_run), str(after.tests_per_run)),
        (f"Total time for {before.runs} runs", f"{before.total_seconds} s", f"{after.total_seconds} s"),
        ("Mean time per test", f"{before.mean_test_seconds} s", f"{after.mean_test_seconds} s"),
        ("Runs with at least one failure", share(before), share(after)),
        ("Tests that fail every run", str(len(before.always_failing)), str(len(after.always_failing))),
        (
            "Tests that fail every run after the first",
            str(len(before.broken_after_first_run)),
            str(len(after.broken_after_first_run)),
        ),
        ("Tests that fail some runs (flaky)", str(len(before.flaky)), str(len(after.flaky))),
    ]
    lines = ["| Measure | Before | After |", "| --- | --- | --- |"]
    lines += [f"| {name} | {b} | {a} |" for name, b, a in rows]
    return "\n".join(lines) + "\n"


def render_block(payload: dict) -> str:
    """The whole README block: the table, and one line saying where it came from.

    The provenance line is generated rather than typed, so the delay range and
    the machine the numbers were taken on are pinned by the same check that
    pins the table.
    """
    suites = payload["suites"]
    table = render_table(SuiteSummary(**suites["before"]), SuiteSummary(**suites["after"]))
    low, high = payload["render_delay_ms"]
    provenance = (
        f"Measured on {payload['taken_on']} — {payload['platform']}, Python {payload['python']}, "
        f"{payload['measured_at']}; render delay {low}–{high} ms; {payload['runs']} runs of each suite."
    )
    return f"{table}\n{provenance}\n"


def render_citations(payload: dict) -> list[str]:
    """One sentence per sick test, in the exact form docs/diagnosis.md's pin reads."""
    before = payload["suites"]["before"]
    lines = []
    for name, count in sorted(before["failure_counts"].items()):
        module, test = name.split("::")
        lines.append(f"`{module.replace('.', '/')}.py::{test}` fails in {count} of {before['runs']} runs")
    return lines


def update_readme(readme: Path, block: str) -> None:
    text = readme.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        raise ValueError(f"{readme} has no {START} … {END} block to update")
    readme.write_text(pattern.sub(lambda _: f"{START}\n{block}{END}", text), encoding="utf-8")


# free_port and _answers repeat tests_after/conftest.py on purpose: the tool
# that measures a suite must not import it, or a broken suite could take the
# measurement down with it.
def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _answers(url: str) -> bool:
    try:
        with urlopen(f"{url}/healthz", timeout=1):
            return True
    except Exception:
        return False


def _render_delay_ms() -> tuple[int, int]:
    """The delay range the app will draw from, so the measurement can record it."""
    low, high = RENDER_DELAY_DEFAULT_MS
    return (
        int(os.environ.get("RENDER_DELAY_MIN_MS", low)),
        int(os.environ.get("RENDER_DELAY_MAX_MS", high)),
    )


def _start_app(port: int) -> subprocess.Popen:
    low, high = _render_delay_ms()
    env = {**os.environ, "RENDER_DELAY_MIN_MS": str(low), "RENDER_DELAY_MAX_MS": str(high)}
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT, env=env,
    )
    deadline = time.monotonic() + 20
    while not _answers(f"http://127.0.0.1:{port}"):
        if time.monotonic() > deadline or process.poll() is not None:
            process.kill()
            raise RuntimeError("the app did not start")
        time.sleep(0.2)
    return process


def _reset(app_url: str) -> None:
    import httpx

    httpx.post(f"{app_url}/api/reset", timeout=10).raise_for_status()


def _run_suite(suite: str, runs: int, app_url: str, out_dir: Path) -> list[RunResult]:
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for index in range(1, runs + 1):
        junit = out_dir / f"{suite}-{index:02d}.xml"
        subprocess.run(
            [sys.executable, "-m", "pytest", f"tests_{suite}", "-q", "-p", "no:cacheprovider", f"--junitxml={junit}"],
            cwd=ROOT, env={**os.environ, "APP_URL": app_url}, capture_output=True, text=True, check=False,
        )
        result = parse_junit(junit)
        results.append(result)
        print(
            f"{suite} run {index:2d}/{runs}: {result.tests} tests, "
            f"{result.failures + result.errors} failed, {result.seconds:.1f} s"
        )
    return results


def _summarise_runs(suites: list[str], runs_dir: Path) -> dict[str, SuiteSummary]:
    """Read the junit files already on disk — no app, no pytest, no new runs."""
    summaries: dict[str, SuiteSummary] = {}
    for suite in suites:
        files = sorted(runs_dir.glob(f"{suite}-*.xml"))
        if not files:
            raise SystemExit(f"no junit files for tests_{suite} under {runs_dir}; run a measurement first")
        summaries[suite] = summarise(suite, [parse_junit(path) for path in files])
        print(f"{suite}: {len(files)} runs read from {runs_dir}")
    return summaries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--suite", choices=["before", "after", "both"], default="both")
    parser.add_argument("--app-url", default=None, help="use a running app instead of starting one")
    parser.add_argument("--out", type=Path, default=ROOT / "measurements" / "latest.json")
    parser.add_argument("--update-readme", action="store_true")
    parser.add_argument(
        "--summarise-only",
        action="store_true",
        help="rebuild the summary from measurements/runs/ instead of running the suites again",
    )
    parser.add_argument(
        "--render",
        type=Path,
        default=None,
        metavar="FILE",
        help="render the README block and the diagnosis's sentences from an existing measurement file; "
             "reads no junit file and runs nothing",
    )
    parser.add_argument(
        "--taken-on",
        default=None,
        metavar="TEXT",
        help=f"where this measurement was taken (default: {DEFAULT_TAKEN_ON}); the CI job passes github-runner",
    )
    args = parser.parse_args(argv)
    suites = ["before", "after"] if args.suite == "both" else [args.suite]

    if args.render is not None:
        payload = json.loads(args.render.read_text(encoding="utf-8"))
        block = render_block(payload)
        print(block)
        print("\n".join(render_citations(payload)))
        if args.update_readme:
            update_readme(ROOT / "README.md", block)
        return 0

    if args.summarise_only:
        if not args.out.exists():
            raise SystemExit(f"{args.out} does not exist; --summarise-only rebuilds an existing measurement")
        payload = json.loads(args.out.read_text(encoding="utf-8"))
        summaries = _summarise_runs(suites, ROOT / "measurements" / "runs")
        payload["suites"] = {**payload.get("suites", {}), **{n: asdict(s) for n, s in summaries.items()}}
        # Counting the same runs a new way does not move them to another
        # machine: keep the provenance the measurement was taken with unless
        # this call states a different one.
        payload["taken_on"] = args.taken_on or payload.get("taken_on", DEFAULT_TAKEN_ON)
        return _write(payload, args)

    process = None
    app_url = args.app_url
    if app_url is None:
        port = _free_port()
        process = _start_app(port)
        app_url = f"http://127.0.0.1:{port}"
    try:
        summaries: dict[str, SuiteSummary] = {}
        for suite in suites:
            _reset(app_url)  # the same starting state for each suite; never between runs
            summaries[suite] = summarise(suite, _run_suite(suite, args.runs, app_url, ROOT / "measurements" / "runs"))
    finally:
        if process is not None:
            process.terminate()
            process.wait(timeout=10)

    payload = {
        "taken_on": args.taken_on or DEFAULT_TAKEN_ON,
        "measured_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "render_delay_ms": list(_render_delay_ms()),
        "runs": args.runs,
        "suites": {name: asdict(summary) for name, summary in summaries.items()},
    }
    return _write(payload, args)


def _write(payload: dict, args: argparse.Namespace) -> int:
    """Write the measurement file and, when both suites are in it, the README block."""
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    suites = payload.get("suites", {})
    if {"before", "after"} <= set(suites):
        block = render_block(payload)
        print(block)
        if args.update_readme:
            update_readme(ROOT / "README.md", block)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The gate that decides whether a fresh measurement still describes this suite.

`tools/compare.py` runs in CI against a measurement the runner has just taken
and the one this repository committed. It has to let a runner be slower than a
laptop and a flaky test be flaky, and it has to stop the day the shares or the
times really move — so both halves of that judgement get a case here.
"""
from __future__ import annotations

import json
from pathlib import Path

from tools.compare import main


def _measurement(path: Path, *, share: float, seconds: float) -> str:
    """A measurement file with only the two fields compare.py reads."""
    suite = {"failing_runs_share": share, "total_seconds": seconds}
    payload = {"suites": {"before": suite, "after": {**suite, "failing_runs_share": 0.0}}}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_a_fresh_measurement_within_tolerance_is_accepted(tmp_path: Path) -> None:
    committed = _measurement(tmp_path / "latest.json", share=0.95, seconds=150.0)
    fresh = _measurement(tmp_path / "ci-latest.json", share=0.90, seconds=180.0)
    assert main([committed, fresh]) == 0, "a slower runner and one lucky run are not a change in the suite"


def test_a_share_that_moved_too_far_is_refused(tmp_path: Path, capsys) -> None:
    committed = _measurement(tmp_path / "latest.json", share=0.95, seconds=150.0)
    fresh = _measurement(tmp_path / "ci-latest.json", share=0.60, seconds=150.0)
    assert main([committed, fresh]) == 1, "a suite that now fails far less often is no longer the one described"
    assert "failing-runs share" in capsys.readouterr().err


def test_a_time_that_moved_too_far_is_refused(tmp_path: Path, capsys) -> None:
    committed = _measurement(tmp_path / "latest.json", share=0.95, seconds=150.0)
    fresh = _measurement(tmp_path / "ci-latest.json", share=0.95, seconds=400.0)
    assert main([committed, fresh]) == 1, "a suite that takes two and a half times as long needs re-measuring"
    assert "total time" in capsys.readouterr().err

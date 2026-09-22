# tools/compare.py
"""Compare a fresh measurement with the committed one and fail beyond a tolerance.

Times move with the runner, shares move with luck: a fresh measurement is
accepted when every share is within 0.10 of the committed one and every time
within 30 %. Anything further apart means the README is describing a suite
that no longer behaves that way, and the file should be re-measured and
re-committed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SHARE_TOLERANCE = 0.10
TIME_TOLERANCE = 0.30


def main(argv: list[str]) -> int:
    committed = json.loads(Path(argv[0]).read_text(encoding="utf-8"))["suites"]
    fresh = json.loads(Path(argv[1]).read_text(encoding="utf-8"))["suites"]
    problems = []
    for suite in ("before", "after"):
        old, new = committed[suite], fresh[suite]
        old_share, new_share = old["failing_runs_share"], new["failing_runs_share"]
        old_time, new_time = old["total_seconds"], new["total_seconds"]
        if abs(old_share - new_share) > SHARE_TOLERANCE:
            problems.append(f"{suite}: failing-runs share {old_share} committed vs {new_share} fresh")
        if old_time and abs(old_time - new_time) / old_time > TIME_TOLERANCE:
            problems.append(f"{suite}: total time {old_time} s committed vs {new_time} s fresh")
        print(f"{suite}: share {old_share} -> {new_share}, time {old_time} s -> {new_time} s")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print("fresh measurement agrees with the committed one within tolerance")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

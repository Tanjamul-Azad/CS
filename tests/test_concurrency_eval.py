"""Regression-check the process-backed concurrency experiment."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

from run_concurrency_eval import run_all  # noqa: E402


def test_process_backed_concurrency_expectations(tmp_path):
    rows = run_all(tmp_path)
    assert all(row["passed"] for row in rows)
    assert rows[0]["child_processes_started"] == 1
    assert rows[1]["overlap_milliseconds"] > 0
    assert rows[1]["distinct_staging_roots"] is True
    assert rows[1]["committed_files"] == ["a.txt", "b.txt"]

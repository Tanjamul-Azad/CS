"""Regression-check the controlled ablation experiment itself."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

from run_mediator_ablations import run_all  # noqa: E402


def test_each_removed_property_exposes_only_its_registered_failure(tmp_path):
    rows = run_all(tmp_path)
    assert rows[0]["variant"] == "full_mcpgate"
    assert rows[0]["failure_exposed"] is False
    assert all(row["failure_exposed"] for row in rows[1:])
    assert {row["variant"] for row in rows} == {
        "full_mcpgate",
        "no_allowance_ledger",
        "no_request_shape",
        "independent_second_read",
        "shared_staging",
        "path_policy_only",
        "no_outer_namespace",
    }

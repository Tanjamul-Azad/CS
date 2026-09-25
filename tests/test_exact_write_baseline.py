"""Regression-check the exact-write engineering baseline experiment."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

from run_exact_write_baseline import run_all  # noqa: E402


def test_exact_write_baseline_preserves_the_expected_security_boundary(tmp_path):
    result = run_all(tmp_path, repetitions=3)
    rows = {(row["condition"], row["case"]): row
            for row in result["security_cases"]}
    assert rows[("path_policy_only", "content_substitution")][
        "trusted_bytes_correct"
    ] is False
    assert rows[("trusted_direct_writer", "content_substitution")][
        "trusted_bytes_correct"
    ] is True
    assert rows[("mcpgate_exact_write", "content_substitution")][
        "trusted_bytes_correct"
    ] is True
    assert rows[("mcpgate_exact_write", "unmediated_side_effect")][
        "outside_effect"
    ] is True
    assert rows[("trusted_direct_writer", "unmediated_side_effect")][
        "outside_effect"
    ] is False
    assert result["performance"]["trusted_direct_writer"]["n"] == 3
    assert result["performance"]["mcpgate_exact_write"]["n"] == 3

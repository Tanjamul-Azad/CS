"""Guard the matched-evaluation overhead and clustered-interval summary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RESULT = Path(__file__).resolve().parents[1] / "artifact" / "results" / "matched_stats.json"

pytestmark = pytest.mark.skipif(
    not RESULT.is_file(), reason="matched_stats not generated")


def _data():
    return json.loads(RESULT.read_text(encoding="utf-8"))


def test_covers_all_seven_servers():
    assert _data()["servers"] >= 7


def test_mcpgate_prevention_is_total_with_clustered_interval():
    prevention = _data()["by_condition"]["MCPGATE"]["prevention"]
    assert prevention["prevented"] == prevention["total"]
    assert prevention["rate"] == 1.0
    assert prevention["clustered_ci"][0] == 1.0


def test_static_lp_is_between_no_defense_and_mcpgate():
    by = _data()["by_condition"]
    none = by["NONE"]["prevention"]["rate"]
    lp = by["STATIC_LP"]["prevention"]["rate"]
    assert none < lp < 1.0


def test_overhead_is_recorded_for_every_condition():
    for cond, stats in _data()["by_condition"].items():
        assert stats["latency_ms"][0] is not None, cond
        assert stats["cpu_seconds"][0] is not None, cond
        assert stats["peak_rss_mb"][0] is not None, cond

"""Guard the 100-trial stochastic concurrency result."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RESULT = Path(__file__).resolve().parents[1] / "artifact" / "results" / "concurrency_100.json"

pytestmark = pytest.mark.skipif(
    not RESULT.is_file(), reason="concurrency_100 result not generated")


def _data():
    return json.loads(RESULT.read_text(encoding="utf-8"))


def test_at_least_one_hundred_trials():
    assert _data()["trials"] >= 100


def test_overlapping_allowance_admits_exactly_one_every_trial():
    data = _data()["A9_overlapping_last_allowance"]
    trials = _data()["trials"]
    assert data["trials_with_exactly_one_commit_and_distinct_stages"] == trials
    assert data["trials_with_more_than_one_commit"] == 0


def test_background_writer_is_refused_every_trial():
    data = _data()["A8_background_writer"]
    trials = _data()["trials"]
    assert data["trials_refused_at_freeze"] == trials
    assert data["trials_with_any_committed_file"] == 0

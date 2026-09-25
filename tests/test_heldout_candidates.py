from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_full_artifact as full  # noqa: E402


def test_checked_in_candidate_inventory_is_pinned_and_balanced():
    assert full._check_candidates(ROOT) == []


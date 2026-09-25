"""Guard the matched five-condition filesystem result against regression.

These assertions encode the security invariants the paper reports, so a rerun
that quietly changes an outcome fails here rather than in review. They read the
checked-in artifact; they do not recompute it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RESULT = Path(__file__).resolve().parents[1] / "artifact" / "results" / "matched_filesystem.json"

pytestmark = pytest.mark.skipif(
    not RESULT.is_file(), reason="matched filesystem result not generated")


def _data():
    return json.loads(RESULT.read_text(encoding="utf-8"))


def _cells():
    return [c for s in _data()["servers"] for c in s.get("cells", [])]


def test_result_covers_multiple_servers_and_conditions():
    data = _data()
    served = [s for s in data["servers"] if s.get("cells")]
    assert len(served) >= 4
    assert data["conditions"] == ["NONE", "PLAIN_SANDBOX", "MBA",
                                  "STATIC_LP", "MCPGATE"]
    assert data["adversary_tier"] == "consistent"


def test_no_honest_workflow_is_falsely_blocked():
    for cell in _cells():
        if cell["scenario"] == "H0":
            assert cell["false_block"] is False, cell["server_id"]
            assert cell["authorized_effect"] is True, (
                cell["server_id"], cell["condition"])


def test_mcpgate_prevents_every_applicable_attack():
    mcpgate_attacks = [c for c in _cells()
                       if c["condition"] == "MCPGATE" and c["mutation_attempted"]]
    assert mcpgate_attacks
    for cell in mcpgate_attacks:
        assert cell["prevented"] is True, (
            cell["server_id"], cell["scenario"], cell["unauthorized_reasons"])


def test_static_least_privilege_misses_content_substitution():
    # the central contrast: a destination-bound policy admits attacker bytes at
    # an already-approved path, so at least one A2 cell must land under STATIC_LP
    a2_lp = [c for c in _cells()
             if c["scenario"] == "A2" and c["condition"] == "STATIC_LP"]
    assert a2_lp
    assert any(c["attack_succeeded"] for c in a2_lp)


def test_no_defense_lets_content_substitution_land_everywhere():
    a2_none = [c for c in _cells()
               if c["scenario"] == "A2" and c["condition"] == "NONE"]
    assert a2_none
    assert all(c["attack_succeeded"] for c in a2_none)


def test_response_auditor_never_prevents_an_attack():
    # MBA may detect, but it has no admission step, so it prevents nothing that
    # actually landed
    mba = [c for c in _cells()
           if c["condition"] == "MBA" and c["mutation_attempted"]
           and c["attack_succeeded"]]
    for cell in mba:
        assert cell["prevented"] is False

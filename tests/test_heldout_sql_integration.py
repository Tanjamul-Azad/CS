from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "artifact" / "held-out-manifest.json"
PLAN = ROOT / "artifact" / "held-out-evaluation-plan.json"
FIRST = ROOT / "artifact" / "results" / "heldout_sql_integration.json"
AMENDED = ROOT / "artifact" / "results" / "heldout_sql_integration_amended.json"


def test_first_integration_failure_is_retained() -> None:
    result = json.loads(FIRST.read_text(encoding="utf-8"))
    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row["server_id"] == "io.github.mrfentmen/sqlite-mcp"
    assert row["status"] == "FAILED"
    assert row["observed_state"]["tables"]["evidence"] == []
    assert row["expected_after_state"]["tables"]["evidence"]


def test_amended_honest_run_is_hash_bound_and_not_a_security_result() -> None:
    result = json.loads(AMENDED.read_text(encoding="utf-8"))
    assert result["phase"] == "POST_FREEZE_HONEST_SQL_INTEGRATION_NO_SECURITY_OUTCOMES"
    assert result["matched_attack_calls"] == 0
    assert result["matched_defense_conditions"] == 0
    assert result["manifest_sha256"] == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert result["evaluation_plan_sha256"] == hashlib.sha256(PLAN.read_bytes()).hexdigest()
    assert len(result["rows"]) == 2
    assert all(row["status"] == "HONEST_COMMITTED" for row in result["rows"])
    assert all(row["trusted_state_matches"] is True for row in result["rows"])


def test_runtime_images_match_amended_manifest() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = {
        row["id"]: row["evaluation_image_id"]
        for row in manifest["servers"] if "evaluation_image_id" in row
    }
    result = json.loads(AMENDED.read_text(encoding="utf-8"))
    observed = {
        row["server_id"]: row["runtime_image_reference"]
        for row in result["rows"]
    }
    assert observed == expected


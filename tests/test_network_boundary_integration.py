from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "artifact" / "results" / "network_boundary_integration.json"


def test_direct_container_attempts_did_not_reach_oracle() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    direct = result["direct_container"]
    assert result["phase"] == "NETWORK_BOUNDARY_INTEGRATION_NOT_MATCHED_EVALUATION"
    assert result["matched_attack_calls"] == 0
    assert result["matched_defense_conditions"] == 0
    assert direct["exit_code"] == 0
    assert direct["oracle_events_after_direct_attempts"] == []
    assert direct["attempts"]["tcp"] != "CONNECTED"
    assert direct["attempts"]["udp"] != "SENT"
    assert direct["attempts"]["raw_socket"] != "OPENED"
    assert direct["attempts"]["child_process"]["returncode"] != 0


def test_broker_sent_one_exact_request_to_same_target() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    broker = result["trusted_broker"]
    events = broker["oracle_events_after_broker"]
    assert broker["record_decision"] == "SENT"
    assert broker["status"] == 201
    assert broker["pinned_ip"] == result["target"]["address"]
    assert len(events) == 1
    assert events[0]["method"] == "POST"
    assert events[0]["path"] == "/approved?mode=strict"
    assert events[0]["content_type"] == "application/json"
    assert events[0]["body_matches"] is True


def test_container_base_image_is_digest_pinned() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    assert "@sha256:" in result["container_image_reference"]
    assert result["container_image_id"].startswith("sha256:")


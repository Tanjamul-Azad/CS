"""Keep the host-side reporter aligned with the container probe schema."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_m2_real_server as real_runner  # noqa: E402
from experiments.boundary.probe_m2_real_server import reset_dir  # noqa: E402
from run_m2_real_server import report  # noqa: E402


def test_reset_dir_preserves_root_and_clears_contents(tmp_path):
    mount_root = tmp_path / "mounted"
    (mount_root / "nested").mkdir(parents=True)
    (mount_root / "nested" / "stale.txt").write_text("stale", encoding="utf-8")
    (mount_root / "top.txt").write_text("stale", encoding="utf-8")

    reset_dir(mount_root, None, None, 0o755)

    assert mount_root.is_dir()
    assert list(mount_root.iterdir()) == []


def test_server_lock_requires_an_exact_version(tmp_path, monkeypatch):
    lock = tmp_path / "server-lock.json"
    monkeypatch.setattr(real_runner, "LOCK", lock)

    lock.write_text(json.dumps({
        "filesystem_mcp": {"package": "filesystem-mcp", "version": None}
    }), encoding="utf-8")
    with pytest.raises(RuntimeError, match="exact filesystem-mcp version"):
        real_runner._load_server_lock()

    lock.write_text(json.dumps({
        "filesystem_mcp": {"package": "filesystem-mcp", "version": "1.2.3"}
    }), encoding="utf-8")
    with pytest.raises(RuntimeError, match="sha512 integrity"):
        real_runner._load_server_lock()

    lock.write_text(json.dumps({
        "filesystem_mcp": {
            "package": "filesystem-mcp", "version": "1.2.3",
            "integrity": "sha512-YWJjZA==",
        }
    }), encoding="utf-8")
    assert real_runner._load_server_lock() == ("1.2.3", "sha512-YWJjZA==")


def test_report_accepts_integrated_probe_rows(capsys):
    row = {
        "scenario": "honest",
        "attack_landed_per_proxy": None,
        "diverted_field": None,
        "verdicts": {
            "trusted_store_admission": "PASS",
            "observed_escape_path_untouched": "PASS",
        },
        "decision": "committed",
        "decision_phase": "commit",
        "ledger_state": "COMMITTED",
        "full_pipeline": ["request_shape", "commit"],
        "staged_content": "approved",
        "escape_content": None,
        "committed_content": "approved",
        "unauthorized_effects": [],
        "server_error": None,
        "mediation_error": None,
    }

    report([row])

    output = capsys.readouterr().out
    assert "trusted_store=PASS" in output
    assert "ledger=COMMITTED" in output
    assert "pipeline_stages=2" in output


def _accepted_row(scenario: str) -> dict:
    honest = scenario == "honest"
    return {
        "scenario": scenario,
        "server_error": None,
        "decision": "committed" if honest else "refused",
        "ledger_state": "COMMITTED" if honest else "FAILED",
        "verdicts": {"trusted_store_admission": "PASS"},
    }


def test_acceptance_rejects_a_handshake_failure_even_when_attacks_do_not_commit():
    rows = [_accepted_row(name) for name in (
        "honest", "path_diversion", "content_substitution",
    )]
    rows[0]["server_error"] = "MCPError: Connection closed"
    rows[0]["decision"] = "failed"
    rows[0]["ledger_state"] = "FAILED"
    rows[0]["verdicts"]["trusted_store_admission"] = "FAIL"

    issues = real_runner._acceptance_issues(rows)

    assert any("honest server failed" in issue for issue in issues)
    assert any("honest decision" in issue for issue in issues)


def test_acceptance_passes_only_the_complete_three_scenario_result():
    rows = [_accepted_row(name) for name in (
        "honest", "path_diversion", "content_substitution",
    )]
    assert real_runner._acceptance_issues(rows) == []

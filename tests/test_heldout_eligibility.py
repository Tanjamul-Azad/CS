from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

import run_heldout_eligibility as eligibility  # noqa: E402


def _candidate(**updates):
    row = {
        "id": "example/server",
        "ecosystem": "npm",
        "package": "@scope/server",
        "version": "1.2.3",
        "integrity": "sha512-YWJjZA==",
        "binary": "server-bin",
    }
    row.update(updates)
    return row


def test_candidate_metadata_rejects_shell_or_floating_inputs():
    eligibility._validate(_candidate())
    with pytest.raises(ValueError, match="unsafe package"):
        eligibility._validate(_candidate(package="x; touch /tmp/pwned"))
    with pytest.raises(ValueError, match="version is not exact"):
        eligibility._validate(_candidate(version="latest"))
    with pytest.raises(ValueError, match="probe MCP version"):
        eligibility._validate(_candidate(probe_mcp_version="latest"))
    with pytest.raises(ValueError, match="unsafe binary"):
        eligibility._validate(_candidate(binary="sh -c pwn"))
    eligibility._validate(_candidate(eligibility_args=["--root", "/sandbox"]))
    with pytest.raises(ValueError, match="unsafe eligibility"):
        eligibility._validate(_candidate(eligibility_args=["; touch /tmp/pwned"]))


def test_image_tag_is_stable_and_changes_with_artifact_identity():
    first = eligibility._image_tag(_candidate())
    assert first == eligibility._image_tag(_candidate())
    assert first != eligibility._image_tag(_candidate(version="1.2.4"))
    assert first.startswith("mcpgate-heldout:")


def test_windows_docker_desktop_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(eligibility.shutil, "which", lambda _name: None)
    monkeypatch.setattr(eligibility.os, "name", "nt")
    cli = tmp_path / "Programs" / "DockerDesktop" / "resources" / "bin" / "docker.exe"
    cli.parent.mkdir(parents=True)
    cli.write_bytes(b"")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert eligibility._docker_executable() == str(cli)

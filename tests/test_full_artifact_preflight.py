"""The full release runner must fail closed on missing human/external evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_full_artifact as full  # noqa: E402


def _write_labels(root: Path) -> None:
    processed = root / "data" / "processed"
    processed.mkdir(parents=True)
    fields = [*full.GIVEN_COLUMNS, "label", "check", "hint_conflict"]
    paths = [processed / "label_sheet.tsv"] + [
        processed / f"labels_annotator_{name}.tsv" for name in ("A", "B")
    ]
    for path in paths:
        with path.open(
            "w", encoding="utf-8", newline="",
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
            writer.writeheader()
            for index in range(265):
                writer.writerow({
                    "server_id": f"server-{index // 5}",
                    "tool": f"tool-{index}",
                    "description": "description",
                    "input_fields": "path,content",
                    "siblings": "read: returns the written object",
                    "label": "A2" if path.name != "label_sheet.tsv" else "",
                    "check": "call read and compare the object" if path.name != "label_sheet.tsv" else "",
                    "hint_conflict": "n" if path.name != "label_sheet.tsv" else "",
                })
    (processed / "label_sheet.corpus_archive.jsonl").write_text(
        '{"frozen": true}\n', encoding="utf-8",
    )
    (processed / "label_split.json").write_text(
        '{"split": {}}\n', encoding="utf-8",
    )
    docs = root / "docs"
    docs.mkdir()
    (docs / "14-labeling-codebook.md").write_text("# Codebook\n", encoding="utf-8")


def _write_locks_and_manifest(root: Path) -> None:
    artifact = root / "artifact"
    artifact.mkdir()
    (artifact / "server-lock.json").write_text(json.dumps({
        "filesystem_mcp": {
            "version": "1.3.0", "integrity": "sha512-YWJjZA==",
        }
    }), encoding="utf-8")
    classes = ("EXACT", "CONSTRAINED", "UNDERSPECIFIED")
    servers = []
    for index in range(10):
        servers.append({
            "id": f"server-{index}",
            "ecosystem": "npm",
            "package": f"package-{index}",
            "version": "1.0.0",
            "integrity": f"sha512-integrity-{index}",
            "workflow_class": classes[index % len(classes)],
            "tool": "write",
            "runner": ["python", f"runner-{index}.py"],
        })
    (artifact / "held-out-manifest.json").write_text(json.dumps({
        "status": "FROZEN",
        "minimum_independent_servers": 10,
        "minimum_per_claimed_workflow_class": 2,
        "claimed_workflow_classes": list(classes),
        "servers": servers,
    }), encoding="utf-8")
    candidates = []
    for index in range(10):
        candidates.append({
            "id": f"candidate-{index}",
            "workflow_class_candidate": classes[index % len(classes)],
            "version": "1.0.0",
            "integrity": "sha256:" + f"{index:064x}",
        })
    (artifact / "held-out-candidates.json").write_text(json.dumps({
        "primary": candidates,
    }), encoding="utf-8")
    (artifact / "requirements-full-linux.txt").write_text(
        "example==1.0.0 --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8",
    )
    immutable = (
        "data/processed/label_sheet.tsv",
        "data/processed/label_sheet.corpus_archive.jsonl",
        "data/processed/label_split.json",
        "docs/14-labeling-codebook.md",
    )
    hashes = {
        relative: hashlib.sha256((root / relative).read_bytes()).hexdigest()
        for relative in immutable
    }
    (artifact / "round2-annotation-freeze.json").write_text(json.dumps({
        "files": hashes,
    }), encoding="utf-8")


def test_preflight_accepts_complete_non_host_fixture(tmp_path):
    _write_labels(tmp_path)
    _write_locks_and_manifest(tmp_path)
    issues, commands = full.preflight(
        tmp_path, check_host=False, require_clean=False,
    )
    assert issues == []
    assert len(commands) == 10


def test_full_lock_accepts_pip_compile_multiline_hashes(tmp_path):
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    (artifact / "requirements-full-linux.txt").write_text(
        "example==1.0.0 \\\n"
        "    --hash=sha256:" + "a" * 64 + " \\\n"
        "    --hash=sha256:" + "b" * 64 + "\n",
        encoding="utf-8",
    )
    assert full._check_full_lock(tmp_path) == []


def test_preflight_rejects_blank_labels_and_unfrozen_manifest(tmp_path):
    _write_labels(tmp_path)
    _write_locks_and_manifest(tmp_path)
    label = tmp_path / "data" / "processed" / "labels_annotator_A.tsv"
    text = label.read_text(encoding="utf-8").replace("A2\tcall read", "\tcall read", 1)
    label.write_text(text, encoding="utf-8")
    manifest_path = tmp_path / "artifact" / "held-out-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "DRAFT_NOT_FROZEN"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    issues, _ = full.preflight(tmp_path, check_host=False, require_clean=False)

    assert any("annotator A" in issue for issue in issues)
    assert any("not FROZEN" in issue for issue in issues)

from __future__ import annotations

import csv
import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import build_annotator_packages as packages  # noqa: E402


def _write_sheet(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [*packages.GIVEN_COLUMNS, *packages.JUDGMENT_COLUMNS]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        for index in range(packages.EXPECTED_ROWS):
            writer.writerow({
                "server_id": f"server-{index}",
                "tool": f"tool-{index}",
                "description": "description",
                "input_fields": "path,content",
                "siblings": "read_file",
                "label": "",
                "check": "",
                "hint_conflict": "",
            })


def test_packages_are_isolated_and_manifested(tmp_path):
    for relative in (packages.SAMPLE, *packages.SHEETS.values()):
        _write_sheet(tmp_path / relative)
    for relative, content in (
        (packages.RUNBOOK, b"runbook\n"),
        (packages.CODEBOOK, b"codebook\n"),
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    freeze = {
        "files": {
            packages.SAMPLE.as_posix(): hashlib.sha256(
                (tmp_path / packages.SAMPLE).read_bytes()
            ).hexdigest(),
            packages.CODEBOOK.as_posix(): hashlib.sha256(
                (tmp_path / packages.CODEBOOK).read_bytes()
            ).hexdigest(),
        }
    }
    freeze_path = tmp_path / packages.FREEZE
    freeze_path.parent.mkdir(parents=True, exist_ok=True)
    freeze_path.write_text(json.dumps(freeze), encoding="utf-8")

    created = packages.build(tmp_path, tmp_path / "out")
    assert [path.name for path in created] == [
        "round2-annotator-A.zip", "round2-annotator-B.zip",
    ]
    for label, archive_path in zip(("A", "B"), created):
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            assert f"labels_annotator_{label}.tsv" in names
            assert f"labels_annotator_{'B' if label == 'A' else 'A'}.tsv" not in names
            manifest = archive.read("MANIFEST.sha256").decode("ascii")
            assert f"labels_annotator_{label}.tsv" in manifest


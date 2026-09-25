"""Build isolated, deterministic Round-2 packages for human annotators.

Each archive contains exactly one annotator sheet, so A cannot accidentally
open or edit B's copy.  The script validates the frozen sample and codebook,
checks that every judgment cell is still blank, and writes a manifest inside
each archive.  It never labels, copies, or adjudicates a row.
"""

from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifact" / "annotator-packages"
SAMPLE = Path("data/processed/label_sheet.tsv")
SHEETS = {
    "A": Path("data/processed/labels_annotator_A.tsv"),
    "B": Path("data/processed/labels_annotator_B.tsv"),
}
RUNBOOK = Path("paper/ROUND2_ANNOTATION_RUNBOOK_BN.md")
CODEBOOK = Path("docs/14-labeling-codebook.md")
FREEZE = Path("artifact/round2-annotation-freeze.json")
GIVEN_COLUMNS = ("server_id", "tool", "description", "input_fields", "siblings")
JUDGMENT_COLUMNS = ("label", "check", "hint_conflict")
EXPECTED_ROWS = 265
ZIP_TIME = (2026, 9, 25, 0, 0, 0)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _validate(root: Path) -> None:
    freeze = json.loads((root / FREEZE).read_text(encoding="utf-8"))
    frozen_files = freeze.get("files", {})
    for relative in (SAMPLE, CODEBOOK):
        expected = frozen_files.get(relative.as_posix())
        observed = _sha256((root / relative).read_bytes())
        if expected != observed:
            raise RuntimeError(f"freeze hash mismatch: {relative.as_posix()}")

    sample = _read_tsv(root / SAMPLE)
    if len(sample) != EXPECTED_ROWS:
        raise RuntimeError(
            f"frozen sample must contain {EXPECTED_ROWS} rows, found {len(sample)}"
        )
    for label, relative in SHEETS.items():
        rows = _read_tsv(root / relative)
        if len(rows) != EXPECTED_ROWS:
            raise RuntimeError(
                f"annotator {label} sheet must contain {EXPECTED_ROWS} rows, "
                f"found {len(rows)}"
            )
        for line, (source, row) in enumerate(zip(sample, rows), start=2):
            if any(source.get(key) != row.get(key) for key in GIVEN_COLUMNS):
                raise RuntimeError(
                    f"annotator {label} given columns differ at TSV line {line}"
                )
            if any((row.get(key) or "").strip() for key in JUDGMENT_COLUMNS):
                raise RuntimeError(
                    f"annotator {label} judgment cells are not blank at TSV line {line}"
                )


def _instructions(label: str) -> bytes:
    return (
        f"Round-2 Annotator {label}\n"
        "=====================\n\n"
        "1. ROUND2_ANNOTATION_RUNBOOK_BN.md সম্পূর্ণ পড়ুন।\n"
        "2. 14-labeling-codebook.md অনুসরণ করুন।\n"
        f"3. শুধু labels_annotator_{label}.tsv-এর label, check, এবং "
        "hint_conflict পূরণ করুন।\n"
        "4. অন্য annotator-এর সঙ্গে completion-এর আগে আলোচনা করবেন না।\n"
        "5. TSV format বজায় রাখুন; CSV/XLSX হিসেবে ফেরত দেবেন না।\n"
        "6. পূর্ণ file-টি author-কে ফেরত দিন; original filename রাখুন।\n"
    ).encode("utf-8")


def _zip_entry(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data)


def build(root: Path = ROOT, output: Path | None = None) -> list[Path]:
    root = Path(root)
    output = Path(output) if output is not None else root / OUTPUT.relative_to(ROOT)
    _validate(root)
    output.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for label, sheet in SHEETS.items():
        files = {
            sheet.name: (root / sheet).read_bytes(),
            RUNBOOK.name: (root / RUNBOOK).read_bytes(),
            CODEBOOK.name: (root / CODEBOOK).read_bytes(),
            "START_HERE_BN.txt": _instructions(label),
        }
        manifest = "".join(
            f"{_sha256(data)}  {name}\n" for name, data in sorted(files.items())
        ).encode("ascii")
        archive_path = output / f"round2-annotator-{label}.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            for name, data in sorted(files.items()):
                _zip_entry(archive, name, data)
            _zip_entry(archive, "MANIFEST.sha256", manifest)
        created.append(archive_path)
    return created


def main() -> int:
    for path in build():
        print(f"created {path.relative_to(ROOT)} sha256={_sha256(path.read_bytes())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


"""score_labels.py must prefer an archived sample corpus over the live one.

Found 2026-09-11: label_sheet.tsv was labelled by two annotators (265 rows,
real work), but the classifier-vs-human validation step failed with "no
overlap" against every (server_id, tool) key. Root cause: make_label_sample.py
wrote only truncated display fields to the TSV, never the full
ExtractedTool records classify() needs, and relied on re-loading
d1_corpus.jsonl by key at scoring time. d1_corpus.jsonl is a live GitHub
harvest, gitignored and regenerated over time, so a server_id present when
the sample was drawn is not guaranteed to still be present -- or to
contain the same tools -- later. The sample was silently orphaned from the
data it was drawn from.

Fix: make_label_sample.py now archives the exact sampled records as
*.corpus_archive.jsonl; score_labels.py prefers that archive when present.
These tests pin the preference and the fallback message.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _write_sheet(path: Path, rows: list[tuple[str, str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write("server_id\ttool\tdescription\tinput_fields\tsiblings\t"
                "label\tcheck\thint_conflict\n")
        for sid, tool, label in rows:
            f.write(f"{sid}\t{tool}\t\t\t\t{label}\t-\tn\n")


def test_score_labels_prefers_the_archive_over_the_live_corpus(tmp_path, monkeypatch):
    """The whole point: a tool present in the archive but ABSENT from the
    live corpus (simulating a regenerated harvest that dropped it) must
    still be found and scored."""
    import score_labels as sl

    a = tmp_path / "labels_annotator_A.tsv"
    b = tmp_path / "labels_annotator_B.tsv"
    _write_sheet(a, [("orphaned/server", "write_file", "A2")])
    _write_sheet(b, [("orphaned/server", "write_file", "A2")])

    archive = tmp_path / "label_sheet.corpus_archive.jsonl"
    archive.write_text(json.dumps({
        "name": "write_file", "server_id": "orphaned/server",
        "description": "Write a file.", "input_fields": ["path"],
        "output_fields": [], "annotations": {"readOnlyHint": False},
    }) + "\n", encoding="utf-8")

    # Live corpus does NOT contain this server -- the regenerated-harvest
    # scenario that orphaned the real sample.
    live_corpus = tmp_path / "d1_corpus.jsonl"
    live_corpus.write_text(json.dumps({
        "name": "unrelated_tool", "server_id": "some/other-server",
        "description": "", "input_fields": [], "output_fields": [],
        "annotations": {},
    }) + "\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv",
                        ["score_labels.py", "--a", str(a), "--b", str(b),
                         "--corpus", str(live_corpus), "--archive", str(archive)])
    sl.main()   # must not raise, and must find the tool via the archive


def test_missing_archive_falls_back_and_explains_rather_than_crashing(
        tmp_path, monkeypatch, capsys):
    import score_labels as sl

    a = tmp_path / "labels_annotator_A.tsv"
    b = tmp_path / "labels_annotator_B.tsv"
    _write_sheet(a, [("orphaned/server", "write_file", "A2")])
    _write_sheet(b, [("orphaned/server", "write_file", "A2")])

    live_corpus = tmp_path / "d1_corpus.jsonl"
    live_corpus.write_text(json.dumps({
        "name": "unrelated_tool", "server_id": "some/other-server",
        "description": "", "input_fields": [], "output_fields": [],
        "annotations": {},
    }) + "\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv",
                        ["score_labels.py", "--a", str(a), "--b", str(b),
                         "--corpus", str(live_corpus)])
    sl.main()
    out = capsys.readouterr().out
    assert "NO OVERLAP" in out
    assert "kappa" in out.lower()   # the agreement number still printed

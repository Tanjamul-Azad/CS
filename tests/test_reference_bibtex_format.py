from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from normalize_bibtex_comments import normalize  # noqa: E402
from verify_refs import parse  # noqa: E402


def test_checked_in_bibliography_has_bibtex_safe_status_comments():
    text = (ROOT / "paper" / "references.bib").read_text(encoding="utf-8")
    assert not re.search(r"^@[A-Za-z]+\{[^,]+,\s*%", text, re.MULTILINE)
    entries = parse(text)
    assert len(entries) == 62
    assert sum(entry.status == "V" for entry in entries) == 21
    assert sum(entry.status == "U" for entry in entries) == 41


def test_normalizer_is_idempotent_on_safe_header():
    safe = "% [V] verified\n@article{key,\n  title={T},\n}\n"
    assert normalize(safe) == (safe, 0)


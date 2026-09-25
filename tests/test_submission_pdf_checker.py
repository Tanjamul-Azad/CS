from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_submission_pdf import check  # noqa: E402


def test_checked_in_working_pdf_passes_structural_checks_when_present():
    pdf = ROOT / "paper" / "latex" / "main.pdf"
    if not pdf.exists():
        pytest.skip("generated PDF is intentionally gitignored")
    assert check(pdf, working_draft=True) == []
    assert "EVIDENCE GATE marker remains in release PDF" in check(
        pdf, working_draft=False,
    )


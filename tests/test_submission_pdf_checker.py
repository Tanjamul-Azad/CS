from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_submission_pdf import body_page_issues, check  # noqa: E402


def test_body_on_appendix_page_is_not_lost_from_page_limit():
    pages = ["Body text"] * 13 + ["10 Conclusion\nFinal body paragraph\nA Ethical Considerations\nEthics text"]
    assert body_page_issues(pages) == ["body is 14 pages; USENIX limit is 13"]
    assert body_page_issues(["Body text"] * 13 + ["A Ethical Considerations\nEthics text\n14"]) == []
    assert body_page_issues(["Body text"] * 14 + ["A Ethical Considerations\nEthics text"]) == ["body is 14 pages; USENIX limit is 13"]


def test_checked_in_working_pdf_passes_structural_checks_when_present():
    pdf = ROOT / "paper" / "submission" / "main.pdf"
    if not pdf.exists():
        pytest.skip("generated PDF is intentionally gitignored")
    assert check(pdf, working_draft=True, named_draft=True) == []
    assert "anonymous artifact URL placeholder remains in release PDF" in check(
        pdf, working_draft=False, named_draft=True,
    )

"""Structural release checks for the generated anonymous USENIX PDF."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF = ROOT / "paper" / "mcpgate-submission.pdf"


def _font_descriptor(font: object) -> object | None:
    font = font.get_object()
    descriptor = font.get("/FontDescriptor")
    if descriptor:
        return descriptor.get_object()
    descendants = font.get("/DescendantFonts")
    if descendants:
        descendant = descendants[0].get_object()
        descriptor = descendant.get("/FontDescriptor")
        if descriptor:
            return descriptor.get_object()
    return None


def check(
    path: Path, *, working_draft: bool = False, named_draft: bool = False,
) -> list[str]:
    reader = PdfReader(path)
    issues: list[str] = []
    if len(reader.pages) == 0:
        return ["PDF has no pages"]
    metadata = reader.metadata or {}
    author_metadata = (metadata.get("/Author") or "").strip()
    if not named_draft and author_metadata:
        issues.append("PDF Author metadata is not blank")
    if named_draft and "Md. Tanzamul Azad" not in author_metadata:
        issues.append("named-draft PDF Author metadata is missing the lead author")

    texts: list[str] = []
    fonts: dict[str, bool] = {}
    for number, page in enumerate(reader.pages, start=1):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        if abs(width - 612) > 1 or abs(height - 792) > 1:
            issues.append(f"page {number} is not U.S. Letter: {width}x{height} pt")
        texts.append(page.extract_text() or "")
        resources = page.get("/Resources")
        if not resources:
            continue
        font_map = resources.get_object().get("/Font")
        if not font_map:
            continue
        for reference in font_map.get_object().values():
            font = reference.get_object()
            name = str(font.get("/BaseFont", "<unnamed>"))
            descriptor = _font_descriptor(font)
            embedded = bool(descriptor and any(
                key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3")
            ))
            fonts[name] = fonts.get(name, False) or embedded

    unembedded = sorted(name for name, embedded in fonts.items() if not embedded)
    if unembedded:
        issues.append(f"unembedded fonts: {', '.join(unembedded)}")

    all_text = "\n".join(texts)
    forbidden_tokens = ["ZZTOKEN", "Citation `", "[??]"]
    if not named_draft:
        forbidden_tokens.extend([
            "Tanjamul", "Tanzamul", "Jahidul", "Azizur",
            "United International University", "UIU",
        ])
    for forbidden in forbidden_tokens:
        if forbidden.casefold() in all_text.casefold():
            issues.append(f"forbidden/unresolved text appears in PDF: {forbidden}")
    if not named_draft and re.search(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", all_text, re.I,
    ):
        issues.append("email address appears in anonymous PDF")
    if re.search(r"[A-Za-z]:\\(?:Users|UIU)\\", all_text):
        issues.append("local Windows path appears in PDF text")
    if not working_draft and "EVIDENCE GATE" in all_text:
        issues.append("EVIDENCE GATE marker remains in release PDF")
    if not working_draft and "ANONYMOUS-ARTIFACT-URL-PENDING" in all_text:
        issues.append("anonymous artifact URL placeholder remains in release PDF")

    appendix_page = next(
        (index for index, text in enumerate(texts, start=1)
         if re.search(r"^(?:[A-Z]\s+)?Ethical Considerations\s*$", text, re.MULTILINE)),
        None,
    )
    if appendix_page is None:
        issues.append("Ethical Considerations appendix heading was not found")
    elif appendix_page - 1 > 13:
        issues.append(f"body is {appendix_page - 1} pages; USENIX limit is 13")
    open_science_page = next(
        (index for index, text in enumerate(texts, start=1)
         if re.search(r"^(?:[A-Z]\s+)?Open Science\s*$", text, re.MULTILINE)),
        None,
    )
    if open_science_page is None:
        issues.append("required Open Science appendix heading was not found")
    elif appendix_page is not None and open_science_page < appendix_page:
        issues.append("Open Science appears before Ethical Considerations")
    references_page = next(
        (index for index, text in enumerate(texts, start=1)
         if re.search(r"^References\s*$", text, re.MULTILINE)),
        None,
    )
    if references_page is None:
        issues.append("References heading was not found")
    elif open_science_page is not None and references_page < open_science_page:
        issues.append("References appear before Open Science")
    if named_draft:
        for expected in (
            "Md. Tanzamul Azad", "Jahidul Islam", "Azizur Rahman Anik",
            "United International University",
            "i.m.tanjamu@gmail.com", "jislam223654@bscse.uiu.ac.bd",
            "azizur@cse.uiu.ac.bd",
        ):
            if expected not in all_text:
                issues.append(f"named-draft author detail was not found: {expected}")
    elif "Anonymous submission" not in all_text:
        issues.append("anonymous author marker was not found")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", nargs="?", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--working-draft", action="store_true")
    parser.add_argument("--named-draft", action="store_true")
    args = parser.parse_args()
    issues = check(
        args.pdf,
        working_draft=args.working_draft,
        named_draft=args.named_draft,
    )
    if issues:
        for issue in issues:
            print(f"PDF CHECK FAILED: {issue}")
        return 1
    print(f"PDF CHECK PASS: {args.pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

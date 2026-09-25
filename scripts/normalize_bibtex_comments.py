"""Move verification comments out of BibTeX entry headers.

BibTeX does not treat an inline ``%`` after ``@type{key,`` consistently as a
comment.  The working bibliography historically stored [V]/[U] there, which
our Python verifier accepted but the venue's BibTeX rejected.  This mechanical
normalizer keeps the marker immediately above the entry and is idempotent.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BIB = ROOT / "paper" / "references.bib"
INLINE = re.compile(
    r"^(?P<header>@[A-Za-z]+\{[^,\s]+,)\s*"
    r"%\s*(?P<marker>\[[VU]\])(?P<detail>[^\r\n]*)$",
    re.MULTILINE,
)


def normalize(text: str) -> tuple[str, int]:
    def replacement(match: re.Match[str]) -> str:
        detail = match.group("detail").rstrip()
        return f"% {match.group('marker')}{detail}\n{match.group('header')}"

    return INLINE.subn(replacement, text)


def main() -> int:
    original = BIB.read_text(encoding="utf-8")
    updated, count = normalize(original)
    if updated != original:
        BIB.write_text(updated, encoding="utf-8")
    print(f"normalized {count} BibTeX verification comment(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


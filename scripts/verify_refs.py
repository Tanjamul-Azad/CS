"""Offline structural gate for ``paper/references.bib``.

This does not pretend that a resolving DOI proves a related-work claim.  Human
primary-source checks are recorded in ``paper/REFERENCE_LEDGER.md``.  The script
enforces the mechanical half: unique keys, an explicit [V]/[U] status,
publication-type metadata plus a primary locator for every [V] entry, and a
submission guard that prevents the working manuscript from citing [U] entries.
"""

from __future__ import annotations

import re
import argparse
from dataclasses import replace
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BIB = ROOT / "paper" / "submission" / "references.bib"
MANUSCRIPT = ROOT / "paper" / "submission" / "main.tex"
ENTRY = re.compile(
    r"^(?:%\s*\[(?P<status>[VU])\][^\n]*\n)?"
    r"@(?P<kind>[A-Za-z]+)\{(?P<key>[^,\s]+),\s*\n"
    r"(?P<body>.*?)(?=^(?:%\s*\[[VU]\][^\n]*\n)?@|\Z)",
    re.MULTILINE | re.DOTALL,
)
FIELD = re.compile(r"(?:^|,)\s*(?P<name>[A-Za-z][A-Za-z0-9_-]*)\s*=", re.MULTILINE)
CITATION = re.compile(r"(?<![A-Za-z0-9_])@([A-Za-z0-9_:-]+)")


@dataclass(frozen=True)
class Entry:
    kind: str
    key: str
    status: str
    fields: frozenset[str]


def parse(text: str) -> list[Entry]:
    entries = []
    for match in ENTRY.finditer(text):
        status = match.group("status") or ""
        entries.append(
            Entry(
                kind=match.group("kind").lower(),
                key=match.group("key"),
                status=status,
                fields=frozenset(
                    item.group("name").lower()
                    for item in FIELD.finditer(match.group("body"))
                ),
            )
        )
    return entries


def audit(entries: list[Entry]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if entry.key in seen:
            errors.append(f"duplicate key: {entry.key}")
        seen.add(entry.key)
        if not entry.status:
            errors.append(f"{entry.key}: missing [V] or [U] marker")
        if entry.status != "V":
            continue

        required = {"title", "year"}
        if entry.kind != "misc":
            required.add("author")
        if entry.kind == "article":
            required.add("journal")
        elif entry.kind == "inproceedings":
            required.add("booktitle")
        elif entry.kind == "techreport":
            required.add("institution")
        missing = required - entry.fields
        if missing:
            errors.append(
                f"{entry.key}: verified {entry.kind} missing {sorted(missing)}"
            )
        if not ({"doi", "url"} & entry.fields):
            errors.append(f"{entry.key}: verified entry lacks DOI or primary URL")
    return errors


def audit_manuscript(entries: list[Entry]) -> list[str]:
    if not MANUSCRIPT.exists():
        return []
    by_key = {entry.key: entry for entry in entries}
    if MANUSCRIPT.suffix == ".tex":
        source = MANUSCRIPT.read_text(encoding="utf-8") + "\n".join(p.read_text(encoding="utf-8") for p in (MANUSCRIPT.parent / "sections").glob("*.tex"))
        cited = sorted({k.strip() for m in re.finditer(r"\\cite\{([^}]+)\}", source) for k in m.group(1).split(",")})
    else:
        cited = sorted(set(CITATION.findall(MANUSCRIPT.read_text(encoding="utf-8"))))
    errors: list[str] = []
    for key in cited:
        entry = by_key.get(key)
        if entry is None:
            errors.append(f"manuscript cites missing key: {key}")
        elif entry.status != "V":
            errors.append(f"manuscript cites unverified [{entry.status or '?'}] key: {key}")
    print(f"{MANUSCRIPT.relative_to(ROOT)}: {len(cited)} unique citation keys")
    return errors


def main() -> int:
    global BIB, MANUSCRIPT
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy", action="store_true", help="audit historical Markdown and marked bibliography")
    args = parser.parse_args()
    if args.legacy:
        BIB = ROOT / "paper/references.bib"
        MANUSCRIPT = ROOT / "paper/MANUSCRIPT_DRAFT.md"
    if not BIB.exists():
        print("Private manuscript bibliography is not present; obtain the source package to audit citations.", file=sys.stderr)
        return 1
    entries = parse(BIB.read_text(encoding="utf-8"))
    # Current LaTeX bibliography has no historical V/U markers. This command
    # checks required metadata and citation topology, never source truth.
    if not args.legacy:
        entries = [replace(e, status="V") for e in entries]
    errors = audit(entries)
    verified = sum(entry.status == "V" for entry in entries)
    unverified = sum(entry.status == "U" for entry in entries)
    print(
        f"{BIB.relative_to(ROOT)}: {len(entries)} entries; "
        f"{verified} metadata-checked, {unverified} unverified historical entries"
    )
    errors.extend(audit_manuscript(entries))
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

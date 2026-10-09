"""Fail-closed readiness check for the EffectSeal paper package.

This is deliberately stricter than the test suite. Passing unit tests does not
make an empirical paper submission-ready: open claims, unchecked P0 gates,
unverified citations, and evidence placeholders are independent blockers.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "paper" / "CLAIM_EVIDENCE_MATRIX.md"
ROADMAP = ROOT / "paper" / "SUBMISSION_ROADMAP.md"
SUBMISSION = ROOT / "paper" / "submission"
PDF = SUBMISSION / "main.pdf"

CLAIM_ROW = re.compile(
    r"^\|\s*(?:C|N)\d+\s*\|.*?\|\s*(READY|QUALIFIED|OPEN|RETIRED)(?:\s+[^|]+)?\s*\|",
    re.MULTILINE,
)


def p0_unchecked(text: str) -> list[str]:
    match = re.search(
        r"### P0.*?(?=\n### P1)", text, flags=re.DOTALL,
    )
    if not match:
        return ["P0 section missing"]
    pending: list[str] = []
    current = ""
    for line in match.group(0).splitlines():
        if line.startswith("- [ ] "):
            if current:
                pending.append(current.strip())
            current = line[6:].strip()
        elif current and line.startswith("      "):
            current += " " + line.strip()
        elif current:
            pending.append(current.strip())
            current = ""
    if current:
        pending.append(current.strip())
    return pending


def run(command: list[str]) -> int:
    return subprocess.run(command, cwd=ROOT).returncode


def static_artifact_issues(*, require_annotation: bool = False) -> list[str]:
    """Inspect evidence that must be complete before the release can run."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_full_artifact as full

    issues: list[str] = []
    if require_annotation:
        issues.extend(full._check_labels(ROOT))
        issues.extend(full._check_annotation_freeze(ROOT))
    issues.extend(full._check_server_lock(ROOT))
    issues.extend(full._check_candidates(ROOT))
    held_out, _ = full._check_held_out(ROOT)
    issues.extend(held_out)
    issues.extend(full._check_full_lock(ROOT))
    return issues


def submission_source_issues(*, require_anonymous: bool = False) -> list[str]:
    issues: list[str] = []
    if not (SUBMISSION / "main.tex").exists():
        return ["private manuscript source is absent; obtain the local source package"]
    main = (SUBMISSION / "main.tex").read_text(encoding="utf-8")
    section_paths = sorted((SUBMISSION / "sections").glob("*.tex"))
    source = "\n".join([main] + [path.read_text(encoding="utf-8") for path in section_paths])
    bib = (SUBMISSION / "references.bib").read_text(encoding="utf-8")
    active_main = "\n".join(
        line.split("%", 1)[0] for line in main.splitlines()
    )

    if require_anonymous:
        if r"\anonymousreviewtrue" not in active_main:
            issues.append("anonymous review mode is not selected")
    else:
        if r"\anonymousreviewfalse" not in active_main:
            issues.append("named working-draft mode is not selected")
        for token in (
            "Md. Tanzamul Azad", "Jahidul Islam", "Azizur Rahman Anik",
            "United International University",
            "i.m.tanjamu@gmail.com", "jislam223654@bscse.uiu.ac.bd",
            "azizur@cse.uiu.ac.bd",
        ):
            if token not in main:
                issues.append(f"named working-draft author detail is missing: {token}")
    if r"\section{Ethical Considerations}" not in source:
        issues.append("Ethical Considerations appendix heading is missing")
    if r"\section{Open Science}" not in source:
        issues.append("Open Science appendix heading is missing")
    if "EVIDENCE GATE" in source:
        issues.append("EVIDENCE GATE marker remains in submission source")

    cited: set[str] = set()
    for match in re.finditer(r"\\cite\{([^}]+)\}", source):
        cited.update(key.strip() for key in match.group(1).split(","))
    entries = set(re.findall(r"^@\w+\{([^,]+),", bib, re.MULTILINE))
    missing = sorted(cited - entries)
    if missing:
        issues.append(f"submission bibliography misses citation keys: {missing}")
    uncited = sorted(entries - cited)
    if uncited:
        issues.append(f"submission bibliography has uncited entries: {uncited}")
    print(
        f"submission source: {len(section_paths)} sections; "
        f"{len(cited)} cited keys; {len(entries)} bibliography entries"
    )
    return issues


def main() -> int:
    # Redirected Windows consoles may expose a legacy cp1252 stream even when
    # the repository text is UTF-8 (for example the kappa symbol in a gate).
    # A readiness checker must report the blocker rather than crash on it.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tests", action="store_true",
        help="also run the full pytest suite (slower)",
    )
    parser.add_argument(
        "--release", action="store_true",
        help="require the real anonymous artifact URL and release PDF gate",
    )
    parser.add_argument(
        "--require-annotation", action="store_true",
        help="require Round-2 labels even though the current paper omits prevalence",
    )
    args = parser.parse_args()

    if not (SUBMISSION / "main.tex").exists():
        print("NOT SUBMISSION-READY: private manuscript source is absent; obtain the local source package.")
        return 1

    statuses = Counter(CLAIM_ROW.findall(MATRIX.read_text(encoding="utf-8")))
    pending_p0 = p0_unchecked(ROADMAP.read_text(encoding="utf-8"))
    source_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [SUBMISSION / "main.tex", *sorted((SUBMISSION / "sections").glob("*.tex"))]
    )
    evidence_gates = source_text.count("EVIDENCE GATE")

    print("EffectSeal submission readiness")
    print("=" * 48)
    print(
        "claims: "
        + ", ".join(
            f"{name.lower()}={statuses.get(name, 0)}"
            for name in ("READY", "QUALIFIED", "OPEN", "RETIRED")
        )
    )
    print(f"unchecked P0 gates: {len(pending_p0)}")
    for item in pending_p0:
        print(f"  - {item}")
    print(f"manuscript evidence gates: {evidence_gates}")
    artifact_issues = static_artifact_issues(require_annotation=args.require_annotation)
    print(f"static artifact blockers: {len(artifact_issues)}")
    for item in artifact_issues:
        print(f"  - {item}")

    source_issues = submission_source_issues(require_anonymous=args.release)
    print(f"submission source blockers: {len(source_issues)}")
    for item in source_issues:
        print(f"  - {item}")
    pdf_command = [sys.executable, "scripts/check_submission_pdf.py", str(PDF)]
    if not args.release:
        pdf_command.extend(["--working-draft", "--named-draft"])
    pdf_ok = PDF.exists() and run(pdf_command) == 0
    tests_ok = True
    if args.tests:
        # Use a unique workspace-local base directory.  A stale pytest tree on
        # Windows can inherit ACLs that make cleanup fail before collection,
        # which is an environment error rather than a regression.
        basetemp = ROOT.parent / "tmp" / f"pytest-submission-{os.getpid()}"
        basetemp.parent.mkdir(parents=True, exist_ok=True)
        tests_ok = run([
            sys.executable, "-m", "pytest", "-q",
            "--basetemp", str(basetemp),
            "-p", "no:cacheprovider",
        ]) == 0

    blockers = []
    if statuses.get("OPEN", 0):
        blockers.append(f"{statuses['OPEN']} claim(s) remain OPEN")
    if pending_p0:
        blockers.append(f"{len(pending_p0)} P0 gate(s) remain unchecked")
    if evidence_gates:
        blockers.append(f"{evidence_gates} manuscript evidence gate(s) remain")
    if artifact_issues:
        blockers.append(f"{len(artifact_issues)} static artifact blocker(s) remain")
    if source_issues:
        blockers.append(f"{len(source_issues)} submission source blocker(s) remain")
    if not pdf_ok:
        blockers.append("latest submission PDF gate failed")
    if args.release and "ANONYMOUS-ARTIFACT-URL-PENDING" in source_text:
        blockers.append("anonymous artifact URL has not been inserted")
    if not tests_ok:
        blockers.append("test suite failed")

    print("=" * 48)
    if blockers:
        print("NOT SUBMISSION-READY")
        for blocker in blockers:
            print(f"  - {blocker}")
        return 1
    print("SUBMISSION-READY: all automated gates passed")
    print("Human author, ethics, conflict, and venue-format review still apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

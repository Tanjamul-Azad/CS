"""Fail-closed readiness check for the MCPGate paper package.

This is deliberately stricter than the test suite. Passing unit tests does not
make an empirical paper submission-ready: open claims, unchecked P0 gates,
unverified citations, and evidence placeholders are independent blockers.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "paper" / "CLAIM_EVIDENCE_MATRIX.md"
ROADMAP = ROOT / "paper" / "SUBMISSION_ROADMAP.md"
MANUSCRIPT = ROOT / "paper" / "MANUSCRIPT_DRAFT.md"

CLAIM_ROW = re.compile(
    r"^\|\s*C\d+\s*\|.*?\|\s*(READY|QUALIFIED|OPEN|RETIRED)\s*\|",
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


def static_artifact_issues() -> list[str]:
    """Inspect evidence that must be complete before the release can run."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_full_artifact as full

    issues: list[str] = []
    issues.extend(full._check_labels(ROOT))
    issues.extend(full._check_annotation_freeze(ROOT))
    issues.extend(full._check_server_lock(ROOT))
    issues.extend(full._check_candidates(ROOT))
    held_out, _ = full._check_held_out(ROOT)
    issues.extend(held_out)
    issues.extend(full._check_full_lock(ROOT))
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
    args = parser.parse_args()

    statuses = Counter(CLAIM_ROW.findall(MATRIX.read_text(encoding="utf-8")))
    pending_p0 = p0_unchecked(ROADMAP.read_text(encoding="utf-8"))
    evidence_gates = MANUSCRIPT.read_text(encoding="utf-8").count(
        "**EVIDENCE GATE:**"
    )

    print("MCPGate submission readiness")
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
    artifact_issues = static_artifact_issues()
    print(f"static artifact blockers: {len(artifact_issues)}")
    for item in artifact_issues:
        print(f"  - {item}")

    refs_ok = run([sys.executable, "scripts/verify_refs.py"]) == 0
    tex_ok = run([
        sys.executable, "scripts/prepare_usenix_source.py", "--check",
    ]) == 0
    tests_ok = True
    if args.tests:
        tests_ok = run([sys.executable, "-m", "pytest", "-q"]) == 0

    blockers = []
    if statuses.get("OPEN", 0):
        blockers.append(f"{statuses['OPEN']} claim(s) remain OPEN")
    if pending_p0:
        blockers.append(f"{len(pending_p0)} P0 gate(s) remain unchecked")
    if evidence_gates:
        blockers.append(f"{evidence_gates} manuscript evidence gate(s) remain")
    if artifact_issues:
        blockers.append(f"{len(artifact_issues)} static artifact blocker(s) remain")
    if not refs_ok:
        blockers.append("reference verification failed")
    if not tex_ok:
        blockers.append("generated USENIX LaTeX is stale")
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

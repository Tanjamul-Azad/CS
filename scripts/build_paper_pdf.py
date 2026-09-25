"""Build and statically verify the anonymous USENIX submission PDF."""

from __future__ import annotations

import re
import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LATEX = ROOT / "paper" / "latex"
PDF = LATEX / "main.pdf"


def _run(command: list[str]) -> None:
    result = subprocess.run(
        command, cwd=LATEX, check=False, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    if result.returncode != 0:
        tail = (result.stdout + "\n" + result.stderr)[-6000:]
        raise RuntimeError(f"{' '.join(command)} failed:\n{tail}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--working-draft", action="store_true",
        help="allow explicit EVIDENCE GATE markers while checking layout",
    )
    args = parser.parse_args()
    required = ("pdflatex", "bibtex")
    missing = [name for name in required if shutil.which(name) is None]
    if missing:
        print(f"paper build blocked: missing {', '.join(missing)}", file=sys.stderr)
        return 2

    try:
        _run([sys.executable, str(ROOT / "scripts" / "prepare_usenix_source.py")])
        _run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"])
        _run(["bibtex", "main"])
        _run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"])
        _run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"])
    except RuntimeError as error:
        print(f"paper build blocked:\n{error}", file=sys.stderr)
        return 1

    if not PDF.exists() or PDF.stat().st_size == 0:
        print("paper build failed: main.pdf was not produced", file=sys.stderr)
        return 1
    log = (LATEX / "main.log").read_text(encoding="utf-8", errors="replace")
    forbidden = (
        r"LaTeX Warning: There were undefined references",
        r"LaTeX Warning: Citation .* undefined",
        r"! LaTeX Error",
    )
    found = [pattern for pattern in forbidden if re.search(pattern, log)]
    if found:
        print(f"paper build failed: unresolved LaTeX diagnostics: {found}", file=sys.stderr)
        return 1

    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo:
        result = subprocess.run(
            [pdfinfo, str(PDF)], cwd=LATEX, check=False,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if result.returncode != 0 or not re.search(
            r"Page size:\s+612\s+x\s+792\s+pts", result.stdout,
        ):
            print("paper build failed: output is not U.S. Letter", file=sys.stderr)
            return 1
    print(f"paper PDF: {PDF.relative_to(ROOT)} ({PDF.stat().st_size} bytes)")
    command = [sys.executable, str(ROOT / "scripts" / "check_submission_pdf.py"), str(PDF)]
    if args.working_draft:
        command.append("--working-draft")
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode != 0:
        return result.returncode
    print("manual gate still required: grayscale readability and final author review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

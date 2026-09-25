"""Generate a reviewable USENIX LaTeX source from the working Markdown.

This deliberately implements only the Markdown constructs used by the paper:
headings, paragraphs, fenced code, block quotes, simple lists, tables, inline
code, emphasis, links, and Pandoc-style citation groups.  Unknown constructs
fail rather than being silently dropped.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"
OUT = PAPER / "latex"


SPECIAL = {
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}",
}
UNICODE = {
    "→": r"\ensuremath{\rightarrow}",
    "≥": r"\ensuremath{\geq}",
    "≤": r"\ensuremath{\leq}",
    "κ": r"\ensuremath{\kappa}",
    "×": r"\ensuremath{\times}",
    "–": "--", "—": "---", "’": "'", "“": "``", "”": "''",
}
FIGURES_AFTER = {
    "Introduction": (
        "fig1_mcpgate_architecture",
        "MCPGate's eight-stage trusted-state admission path and its explicit non-claim.",
    ),
    "Measurement method": (
        "fig2_study_flow",
        "Measurement funnel and the evidence flow from response auditing to effect admission.",
    ),
    "Measurement results": (
        "fig6_auditor_operating_points",
        "Recorded response-auditor operating points relative to the pre-registered deployability region.",
    ),
    "Controlled baseline comparison": (
        "fig3_controlled_baselines",
        "Controlled attacks separated by baseline; these rows are not held-out real-server results.",
    ),
    "Controlled ablations": (
        "fig4_controlled_ablations",
        "Each removed property exposes its targeted failure in the controlled suite.",
    ),
    "Exact-write engineering baseline": (
        "fig5_exact_write_latency",
        "Development-machine latency for a trusted direct writer and MCPGate exact-write admission.",
    ),
}


def _figure(title: str) -> list[str]:
    if title not in FIGURES_AFTER:
        return []
    name, caption = FIGURES_AFTER[title]
    return [
        r"\begin{figure*}[t]",
        r"\centering",
        rf"\includegraphics[width=\textwidth]{{../figures/{name}.pdf}}",
        r"\caption{" + inline(caption) + "}",
        rf"\label{{fig:{name}}}",
        r"\end{figure*}",
    ]


def _plain_escape(value: str) -> str:
    output = []
    for char in value:
        if char in UNICODE:
            output.append(UNICODE[char])
        elif char in SPECIAL:
            output.append(SPECIAL[char])
        elif char == "~":
            output.append(r"\textasciitilde{}")
        elif char == "^":
            output.append(r"\textasciicircum{}")
        elif char == "\\":
            output.append(r"\textbackslash{}")
        else:
            output.append(char)
    return "".join(output)


def inline(value: str) -> str:
    """Convert inline syntax without escaping generated LaTeX commands."""
    tokens: dict[str, str] = {}

    def hold(rendered: str) -> str:
        token = f"ZZTOKEN{len(tokens)}ZZ"
        tokens[token] = rendered
        return token

    def citation(match: re.Match[str]) -> str:
        keys = re.findall(r"@([A-Za-z0-9_:.-]+)", match.group(1))
        if not keys:
            raise ValueError(f"empty citation group: {match.group(0)}")
        return hold(r"~\cite{" + ",".join(keys) + "}")

    value = re.sub(r"\[([^\]]*@[^\]]+)\]", citation, value)
    value = re.sub(
        r"`([^`]+)`",
        lambda match: hold(r"\texttt{\detokenize{" + match.group(1) + "}}"),
        value,
    )
    value = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        lambda match: hold(
            r"\href{" + match.group(2) + "}{" + _plain_escape(match.group(1)) + "}"
        ),
        value,
    )
    value = re.sub(
        r"\*\*([^*]+)\*\*",
        lambda match: hold(r"\textbf{" + _plain_escape(match.group(1)) + "}"),
        value,
    )
    rendered = _plain_escape(value)
    for token, replacement in tokens.items():
        rendered = rendered.replace(token, replacement)
    return rendered


def _strip_number(title: str) -> str:
    return re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", title).strip()


def _table(lines: list[str]) -> list[str]:
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    if len(rows) < 2 or not all(re.fullmatch(r":?-{3,}:?", cell) for cell in rows[1]):
        raise ValueError("unsupported Markdown table")
    columns = len(rows[0])
    if any(len(row) != columns for row in rows):
        raise ValueError("ragged Markdown table")
    spec = "@{}" + "X" * columns + "@{}"
    rendered = [
        r"\begin{table*}[t]", r"\centering", r"\small",
        rf"\begin{{tabularx}}{{\textwidth}}{{{spec}}}", r"\toprule",
        " & ".join(r"\textbf{" + inline(cell) + "}" for cell in rows[0]) + r" \\",
        r"\midrule",
    ]
    rendered.extend(" & ".join(inline(cell) for cell in row) + r" \\" for row in rows[2:])
    rendered.extend([r"\bottomrule", r"\end{tabularx}", r"\end{table*}"])
    return rendered


def convert(
    markdown: str, *, manuscript: bool = False, fragment: bool = False,
) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    index = 0
    in_abstract = False
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if (manuscript or fragment) and stripped.startswith("# "):
            index += 1
            continue
        if manuscript and stripped == "## Submission blocker ledger":
            break
        if manuscript and stripped == "## Abstract":
            output.append(r"\begin{abstract}")
            in_abstract = True
            index += 1
            continue
        if stripped.startswith("## "):
            if in_abstract:
                output.append(r"\end{abstract}")
                in_abstract = False
            command = "subsection" if fragment else "section"
            title = _strip_number(stripped[3:])
            output.append(rf"\{command}{{" + inline(title) + "}")
            if manuscript:
                output.extend(_figure(title))
            index += 1
            continue
        if stripped.startswith("### "):
            command = "subsubsection" if fragment else "subsection"
            title = _strip_number(stripped[4:])
            output.append(
                rf"\{command}{{" + inline(title) + "}"
            )
            if manuscript:
                output.extend(_figure(title))
            index += 1
            continue
        if stripped.startswith("#### "):
            output.append(r"\subsubsection{" + inline(_strip_number(stripped[5:])) + "}")
            index += 1
            continue
        if stripped.startswith("```"):
            fence = stripped
            code: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            if index >= len(lines):
                raise ValueError(f"unclosed code fence {fence}")
            output.extend([r"\begin{verbatim}", *code, r"\end{verbatim}"])
            index += 1
            continue
        if stripped.startswith("|"):
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index])
                index += 1
            output.extend(_table(table_lines))
            continue
        list_match = re.match(r"^(?:[-*]|\d+\.)\s+(.*)", stripped)
        if list_match:
            ordered = bool(re.match(r"^\d+\.", stripped))
            environment = "enumerate" if ordered else "itemize"
            output.append(r"\begin{" + environment + "}")
            while index < len(lines):
                current = lines[index]
                match = re.match(r"^\s*(?:\d+\.|[-*])\s+(.*)", current)
                if not match:
                    break
                parts = [match.group(1).strip()]
                index += 1
                while index < len(lines) and (
                    lines[index].startswith("  ") and not re.match(
                        r"^\s*(?:\d+\.|[-*])\s+", lines[index]
                    )
                ):
                    parts.append(lines[index].strip())
                    index += 1
                output.append(r"\item " + inline(" ".join(parts)))
            output.append(r"\end{" + environment + "}")
            continue
        if stripped.startswith(">"):
            quote = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip()[1:].strip())
                index += 1
            if manuscript and any("Working manuscript" in part for part in quote):
                continue
            output.extend([r"\begin{quote}", inline(" ".join(quote)), r"\end{quote}"])
            continue
        if not stripped:
            output.append("")
            index += 1
            continue

        paragraph = [stripped]
        index += 1
        while index < len(lines):
            candidate = lines[index]
            if not candidate.strip() or re.match(
                r"^(#{1,4}\s|```|\||>|\s*(?:[-*]|\d+\.)\s+)", candidate
            ):
                break
            paragraph.append(candidate.strip())
            index += 1
        output.append(inline(" ".join(paragraph)))

    if in_abstract:
        output.append(r"\end{abstract}")
    return "\n".join(output).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true",
        help="fail if checked-in generated LaTeX differs from Markdown sources",
    )
    args = parser.parse_args()
    sources = (
        (PAPER / "MANUSCRIPT_DRAFT.md", OUT / "body.tex", True, False),
        (PAPER / "ETHICS_APPENDIX.md", OUT / "ethics.tex", False, True),
        (PAPER / "OPEN_SCIENCE_APPENDIX.md", OUT / "open-science.tex", False, True),
    )
    OUT.mkdir(parents=True, exist_ok=True)
    stale: list[Path] = []
    for source, destination, manuscript, fragment in sources:
        rendered = convert(
            source.read_text(encoding="utf-8"),
            manuscript=manuscript,
            fragment=fragment,
        )
        expected = "% GENERATED by scripts/prepare_usenix_source.py; do not edit.\n" + rendered
        if args.check:
            if not destination.exists() or destination.read_text(encoding="utf-8") != expected:
                stale.append(destination)
            continue
        destination.write_text(expected, encoding="utf-8")
        print(f"wrote {destination.relative_to(ROOT)}")
    if stale:
        for destination in stale:
            print(f"stale generated LaTeX: {destination.relative_to(ROOT)}")
        return 1
    if args.check:
        print("generated USENIX LaTeX is synchronized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

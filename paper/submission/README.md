# Submission source (USENIX Security 2027, anonymous)

Status: scaffold. `main.tex` and the verified `references.bib` (30 entries:
21 from REFERENCE_LEDGER.md plus 9 checked against Crossref/USENIX on
2026-09-26) are in place. Section files under `sections/` and paper-sized
figures under `figures/` are still to be written.

Planned sections: 00-abstract, 01-introduction, 02-background,
03-measurement, 04-design, 05-implementation, 06-methodology, 07-results,
08-limitations, 09-related, 10-conclusion, A-ethics, B-open-science.

Build: `pdflatex main && bibtex main && pdflatex main && pdflatex main`.

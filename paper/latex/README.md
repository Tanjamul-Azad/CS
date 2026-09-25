# USENIX Security 2027 source

`main.tex` uses the official USENIX Security 2027 `usenix.sty` downloaded from:

<https://www.usenix.org/sites/default/files/usenixsecurity2027_latex_templates.zip>

Downloaded 2026-09-25; ZIP SHA-256:

```text
7DC55FC858881A7D64A06D7C8277BE25C6DCC6070B17F74EF0D8A6BED70AA38E
```

Regenerate the LaTeX body and appendices from the working Markdown sources:

```bash
python scripts/prepare_usenix_source.py
```

Then, from `paper/latex/`, compile with a complete LaTeX installation:

```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Or use the checked build/check wrapper from the repository root:

```bash
python scripts/build_paper_pdf.py --working-draft
```

The `--working-draft` flag permits the remaining explicit `EVIDENCE GATE` markers
while still checking page size, font embedding, anonymous metadata, appendix
presence, and body-page count. Omit that flag for a release build; the command
then fails while any evidence marker remains.

A 15-page working PDF was built and visually inspected on 2026-09-25: 11 body
pages, Ethics/Open Science appendices beginning on page 12, and references on
pages 14--15. The stable review copy is
`output/pdf/mcpgate-usenix-working-draft.pdf`. It is not release evidence. The
release PDF must still be rebuilt in the clean Linux artifact environment and
checked for grayscale readability and venue compliance.

`body.tex`, `ethics.tex`, and `open-science.tex` are generated files. Edit the
corresponding Markdown source and regenerate instead of hand-editing them.

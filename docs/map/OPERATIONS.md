# Operations map — how to run things

## Tests

`python -m pytest -q`; current counts are in the dated test/reproduction logs.

## Docker on this machine

- CLI: `$LOCALAPPDATA/Programs/DockerDesktop/resources/bin/docker.exe`; start
  Docker Desktop first if the engine is down.
- Prefix runs with `MSYS_NO_PATHCONV=1` and set `MCPGATE_SCRATCH` to a
  Windows path in the session scratchpad (bind mounts need Windows paths).
- Subprocess output must be decoded as UTF-8 (`encoding="utf-8", errors="replace"`).
- Stop only containers owned by the current run; preserve unrelated work.

## Experiments: plan -> runner -> result

| Workstream | Plan (commit first) | Runner | Result |
|---|---|---|---|
| Matched 5-condition eval | `artifact/held-out-evaluation-plan.json` | `experiments/run_matched_filesystem.py`, `run_matched_sql.py` | `artifact/results/matched_*.json` (use the committed version) |
| A templates (dev) | `artifact/template-generalization-plan.json` | `experiments/run_template_generalization.py`, `run_template_sql.py` | `template_generalization*.json` |
| C confinement | `artifact/confinement-plan.json` | `experiments/run_confinement.py` | `confinement.json` |
| D adaptive | `artifact/adaptive-templates-plan.json` | `experiments/run_adaptive_templates.py` | `adaptive_templates*.json` |
| E formal | — | `java -cp F:/tools/tla2tools.jar tlc2.TLC -config <cfg> -deadlock EffectSeal.tla`; `python formal/check_model.py` | `formal/tlc/*.log` |
| F LLM judge | `artifact/llm-judge-plan.json` | `experiments/run_llm_judge.py collect|judge [--version v2]`; `analyze_judge_leaks.py`; `run_calllevel_baseline.py [--v2]` | `llm_judge*.json`, `calllevel_baseline*.json` |
| G held-out batch | `artifact/batch2-evaluation-plan.json` | `run_batch2_eligibility.py`, `run_batch2_workflow.py`, `run_batch2_templates.py` | `batch2_*.json` |
| I agent end to end | `artifact/agent-e2e-plan.json` | `experiments/run_agent_e2e.py`, `run_agent_e2e_v2.py` | `agent_e2e*.json` |

Numbered runs (`*_run1.json`, `*_run2.json`, ...) are kept on purpose; the
unnumbered file is the latest valid run.

## Figures

- `python scripts/make_strengthening_figures.py` (figures 11–16 ) writes `paper/figures/` and copies PDFs into
  `paper/submission/figures/`.
- `python scripts/make_submission_figures.py` for the older figures.
- `python scripts/matched_stats.py` for matched statistics.

## Building the paper (local only)

Folder: `paper/submission/`; main file: `main.tex`; compiler: pdfLaTeX.

```
pdflatex main
bibtex main
pdflatex main
pdflatex main
```

On Overleaf: upload the whole `paper/submission/` folder (main.tex,
usenix.sty, references.bib, sections/, figures/), set `main.tex` as the main
document and pdfLaTeX as the compiler. Fonts: Times text (from usenix.sty),
`glyphtounicode` on, no `amssymb` symbols, and no line breaks at explicit
hyphens, so every character extracts cleanly for text-based checkers. Do not
add `newtxmath`: its math letters extract as invalid bytes.

To upload: `python scripts/make_overleaf_zip.py` writes a dated `../EffectSeal_Overleaf_YYYYMMDD-HHMMSS.zip`
(outside the repo) with only the files the paper needs.

Before submission: set `\anonymousreviewtrue` and replace `\artifacturl`.
Backups go to `../private_submission_backups/` as dated zips.

## Correctness repair and current network evidence

`artifact/paper-evidence-20261009.json` selects current bundles explicitly;
never choose a directory merely because it sorts last.
`python scripts/verify_current_evidence.py` checks hashes, re-infers templates,
replays request sequences and recomputes summaries/controls/races offline.
`python scripts/summarize_current_evidence.py --update-manuscript` regenerates
the marked supplementary network tables when private source is available.
`sh scripts/reproduce_clean_linux.sh` returns nonzero for any failed step.
Run in a fresh clone; its fixed-name outputs must not overwrite earlier evidence.
The script runs integrated proxy timing/races in addition to isolated mechanism
measurements. No live model/provider API scoring is part of that script.

`python scripts/build_paper_pdf.py --working-draft` builds the canonical current
manuscript, selects named-draft checks from its source switch, and records
`paper/submission/BUILD_MANIFEST.json`. Readiness checks reject a stale PDF or
changed source relative to this verified build. The Overleaf ZIP is source-only
and carries its own source hash manifest.

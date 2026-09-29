# Operations map — how to run things

## Tests

`python -m pytest -q` (about 290 tests, roughly 12 s).

## Docker on this machine

- CLI: `$LOCALAPPDATA/Programs/DockerDesktop/resources/bin/docker.exe`; start
  Docker Desktop first if the engine is down.
- Prefix runs with `MSYS_NO_PATHCONV=1` and set `MCPGATE_SCRATCH` to a
  Windows path in the session scratchpad (bind mounts need Windows paths).
- Subprocess output must be decoded as UTF-8 (`encoding="utf-8", errors="replace"`).
- Kill leftover containers with `docker ps -q | xargs docker kill` before
  stopping a runner process.

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

- `python scripts/make_strengthening_figures.py` (figures 11–16 and the
  matplotlib architecture) writes `paper/figures/` and copies PDFs into
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
document and pdfLaTeX as the compiler. Fonts: Times text with newtxmath, T1
encoding, `glyphtounicode` on, so text extracts cleanly.

Before submission: set `\anonymousreviewtrue` and replace `\artifacturl`.
Backups go to `../private_submission_backups/` as dated zips.

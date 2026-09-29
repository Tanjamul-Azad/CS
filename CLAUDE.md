# EffectSeal (MCP execution integrity) — working rules

Paper: "Faithful Responses, Faithless Effects" (EffectSeal; older code and
results say MCPGATE). Target: USENIX Security 2027, Cycle 2.

## Rules for every task

- Commit as `Tanjamul-Azad <i.m.tanjamul@gmail.com>`, no `Co-Authored-By`
  trailer. Run `python -m pytest -q` before committing; push to `origin main`
  in the same step. Never force-push.
- The manuscript (`paper/submission/`) is gitignored and must never be pushed.
  Figures, scripts, data, and docs are pushed.
- Do not download packages, models, or tools on this machine without asking.
  Docker images already built are fine to run.
- Before long Docker runs, check free space on C: (`df -h /c`); stop below 5 GB.
- Never overwrite a result file of an earlier run: save the next run under a
  new name, and commit a plan file before any scored run.
- API keys come only from the environment (`OPENAI_API_KEY`); never log,
  commit, or pass them into a container.

## Where things are

- What the system is and where its code lives: `docs/map/PRODUCT.md`
- How to run tests, experiments, figures, and build the paper: `docs/map/OPERATIONS.md`
- Which docs are current and which are history: `docs/map/DOCS.md`

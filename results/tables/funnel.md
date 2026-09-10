# Live-audit funnel

How 8,692 real registry servers reduce to an analysable set. The 14.3% survival rate is a selection effect and is characterised in `selection_effect`.

| Stage | Servers | Share |
|---|---|---|
| Registry candidates, runnable without credentials | 8692 | 100.0% |
| Launched and answered tools/list | 4121 | 47.4% |
| Usable write tool, both trials completed | 1242 | 14.3% |
| Attack actually landed (L1, pre-repair) | 128 | 1.5% |

*Source: `data/processed/scale_run.json`. Regenerate with `python experiments/make_results.py`.*

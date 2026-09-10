# Live-audit funnel

How 8,692 real registry servers reduce to an analysable set. The 14.3% survival rate is a selection effect and is characterised in `selection_effect`. The last row says MUTATION ATTEMPTED, not attacks that landed: the underlying flag meant only that the proxy selected a target field. See `effect_oracle` for how far apart those are.

| Stage | Servers | Share |
|---|---|---|
| Registry candidates, runnable without credentials | 8692 | 100.0% |
| Launched and answered tools/list | 4121 | 47.4% |
| Usable write tool, both trials completed | 1242 | 14.3% |
| Mutation attempted (L1, pre-repair) | 128 | 1.5% |

*Source: `data/processed/scale_run.json`. Regenerate with `python experiments/make_results.py`.*

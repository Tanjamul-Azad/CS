# Figure provenance

Regenerate all working manuscript figures with:

```bash
python scripts/make_submission_figures.py
```

| Figure | Source |
|---|---|
| `fig1_mcpgate_architecture.svg` | authoritative sequence in `src/mcpgate/mediator.py` and `docs/43` |
| `fig2_study_flow.svg` | `results/tables/funnel.md` and the claim/evidence roadmap |
| `fig3_controlled_baselines.svg` | `artifact/results/controlled_baselines.json` |
| `fig4_controlled_ablations.svg` | `artifact/results/controlled_ablations.json` |
| `fig5_exact_write_latency.svg` | `artifact/results/exact_write_baseline.json` |
| `fig6_auditor_operating_points.svg` | `results/tables/operating_points.csv` |

PNG files and `contact_sheet.png` are local visual-QA renders and are ignored by
Git. The SVG files are the review/manuscript artifacts. The latency plot must
remain labeled as development-host evidence until regenerated in the clean
Linux release environment.

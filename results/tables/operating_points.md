# Detector operating points

The central measurement. `strict` counts only VIOLATION; `permissive` also counts WARNING. A detection requires the attack to have landed AND the honest trial on the same server to stay silent - the cross-check that separates a real catch from a broken relation firing on everything. All runs target the same 218 candidates, so rows are directly comparable; a row marked PARTIAL was still running when this was generated.

| Run | Point | Usable | Landed | True detections | Detection rate | FPR |
|---|---|---|---|---|---|---|
| pre-R7 baseline | strict | 217 | 205 | 0 | 0.0% | 1.8% |
| pre-R7 baseline | permissive | 217 | 205 | 5 | 2.4% | 78.3% |
| R7 uncalibrated | strict | 217 | 205 | 0 | 0.0% | 6.9% |
| R7 uncalibrated | permissive | 217 | 205 | 4 | 2.0% | 78.3% |
| R7 calibrated | strict | 217 | 204 | 1 | 0.5% | 2.3% |
| R7 calibrated | permissive | 217 | 204 | 6 | 2.9% | 77.0% |

*Source: `data/processed/pilot_*.json`. Regenerate with `python experiments/make_results.py`.*

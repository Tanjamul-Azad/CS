# Results manifest

Generated 2026-09-10 14:36 UTC from commit `ae7fb56` by `experiments/make_results.py`.

Raw per-server traces are gitignored (large, regenerable). This manifest records the exact bytes each table was computed from, so a number in the write-up traces to a file and a stale table is detectable.

| Input | Path | Present | SHA-256 (16) | Size |
|---|---|---|---|---|
| Live scale run (L1, full corpus) | `data\processed\scale_run.json` | yes | `b6f9f30f8b6e6d47` | 12.7 MB |
| E0 resource sweep | `data\processed\resource_sweep.json` | yes | `66841f8a0b649e1d` | 5.8 MB |
| Escape partition | `data\processed\escape_partition.json` | yes | `15137233af8c33b4` | 0.2 MB |
| Pilot, pre-R7 baseline | `data\processed\pilot_pre_r7_baseline.json` | yes | `99e74a860d173ecb` | 0.4 MB |
| Pilot, R7 uncalibrated | `data\processed\pilot_r7.json` | yes | `5059a1f8eecd1959` | 0.5 MB |
| Pilot, R7 calibrated | `data\processed\pilot_r7_calibrated.json` | yes | `35443283f58f94d2` | 0.5 MB |
| Pilot, working error flag | `data\processed\pilot_errflag.json` | yes | `72b81762e6c7c950` | 0.5 MB |
| Effect oracle | `data\processed\effect_oracle.json` | yes | `8bb30e407b52985f` | 0.0 MB |
| M2 boundary probe | `data\processed\boundary_probe.json` | yes | `6aeae72e016de24d` | 0.0 MB |

## How to regenerate the raw inputs

```bash
python experiments/run_scale.py            # live audit, ~1 day
python experiments/run_resource_sweep.py   # E0, ~1 hour
python experiments/make_results.py         # this file + tables
```

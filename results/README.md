# Results

Every number reported in this project, regenerated from raw data by one
command:

```bash
python experiments/run_all.py           # everything that runs offline
python experiments/run_all.py --docker  # also the container stages
```

or just the tables:

```bash
python experiments/make_results.py
```

Nothing in this directory is written by hand. If a table disagrees with
the write-up, the table is right.

## Why this directory exists separately from `data/`

The raw per-server traces are large (12 MB for the live audit alone) and
gitignored, so a reader cloning this repository cannot open them. That is
acceptable for the traces and unacceptable for the numbers they support —
a result nobody else can inspect is not evidence. So the chain is split:

```
experiments/*.py   ->   data/processed/*.json   ->   results/tables/*
   (tracked)            (gitignored, large)          (tracked, small)
```

[`MANIFEST.md`](MANIFEST.md) records the SHA-256 prefix and size of every
raw input each table was computed from, plus the commit that generated
them. A table computed from a stale or missing input is visible rather
than silently wrong.

## The tables

| Table | What it establishes |
|---|---|
| [`funnel`](tables/funnel.md) | How 8,692 real registry servers reduce to 1,242 analysable ones |
| [`run_status`](tables/run_status.md) | Why servers dropped out — mostly no mutating tool at all |
| [`selection_effect`](tables/selection_effect.md) | The analysed set is the *favourable* tail, so a negative detection result on it is an upper bound |
| [`resource_channel`](tables/resource_channel.md) | **E0.** MCP's second observation channel: 0 of 1,216 servers publish an addressable URI template |
| [`escape_partition`](tables/escape_partition.md) | Which structural verification escape each server offers, and the 25.3% that have none |
| [`operating_points`](tables/operating_points.md) | **The central measurement.** Detection and false-positive rate, per detector version |
| [`suppressed_detections`](tables/suppressed_detections.md) | Real attacks the detector found and discarded — how the research direction was located |
| [`effect_oracle`](tables/effect_oracle.md) | **Ground truth.** What the proxy attempted vs what actually happened vs what the detector said |
| [`boundary_probe`](tables/boundary_probe.md) | **M2.** A real adversarial server process against an OS-enforced boundary |

## Reading order, if you have five minutes

1. **`suppressed_detections`** — the finding. The detector caught real
   attacks, including one where the attacker's `/tmp/exfil.dat` is sitting
   in the reader's own output, and scored them zero.
2. **`operating_points`** — why. The detector has two settings: catch
   nothing at a 1.8% false-alarm rate, or catch 2.4% at 78%. Neither is
   usable, and the rows below the baseline show what each fix did.
3. **`escape_partition`** — the structural explanation. 45.9% of servers
   offer only the enumeration escape, which was never implemented.
4. **`selection_effect`** — why the negative result is strong rather than
   weak: it was measured on the easiest quarter of the ecosystem.
5. **`effect_oracle`** — the correction that matters most. Every rate in
   this project divided by a count of "attacks that landed", and that
   count meant only that the proxy had changed an argument.
6. **`boundary_probe`** — the constructive answer: an untrusted server
   process attacking a protected area it cannot write to.

## Raw inputs, and what it costs to regenerate them

| Input | Command | Cost |
|---|---|---|
| `scale_run.json` | `python experiments/run_scale.py` | ~1 day, Docker |
| `resource_sweep.json` | `python experiments/run_resource_sweep.py` | ~1 hour, Docker |
| `escape_partition.json` | derived from the sweep, see `docs/24` | seconds |
| `pilot_*.json` | `run_scale.py --source data/processed/pilot_direction_a_candidates.json` | ~25 min, Docker |

All server execution happens inside a locked-down container
(`docker/Dockerfile`): `--rm`, capability-dropped, memory- and pid-capped,
non-root, one writable mount. These are real, unvetted third-party
packages and they are never run on the host.

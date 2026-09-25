# MCPGate Artifact — Working Guide

The frozen matched-evaluation design is
`artifact/held-out-evaluation-plan.json`. It was created before any matched
attack or defense outcome and is hash-bound to `artifact/held-out-manifest.json`.
It records five conditions, per-server applicability, repetitions, oracles,
outcome fields, and open implementation gates. It is a protocol artifact, not
an outcome artifact.

> **Status:** preparation scaffold, not yet an artifact-evaluation release.
> The quick checks run from this checkout. The full paper result set still
> requires the frozen five-condition held-out run, independent human labels,
> a clean release rerun, and checked-in compact matched-outcome files.

## 1. Scope

This artifact supports two separable claims:

1. response-only evidence does not reveal an effect when honest and malicious
   servers return the same transcript; and
2. for the supported local-filesystem domain, the integrated mediator admits
   only a contract-matching, quiesced staging snapshot into its trusted store.

It does not claim remote-server mediation, arbitrary rollback, network/process
containment, prompt-injection defense, durable exactly-once execution, or
contract signing/expiry.

## 2. Quick evaluation

Expected time on the development machine: under one minute. No Docker or
network is required.

Install the exact direct versions recorded for this path (this file is not yet
a full transitive lock), then run the one-command recorder:

```bash
python -m pip install -r artifact/requirements-quick.txt
python scripts/run_quick_artifact.py
```

The runner creates a new timestamped directory under
`artifact/results/quick/` containing stdout/stderr for every command, exit
codes, elapsed times, Git/Python/package metadata, and SHA-256 hashes. It does
not run `submission_check.py`, because that gate is expected to remain non-zero
until the explicit blockers in the roadmap are closed.

The underlying commands are:

```bash
python -m pytest -q
python experiments/demo_theorem1.py
python experiments/run_effect_oracle.py
python experiments/run_gateway_eval.py
python experiments/run_mediator_ablations.py
python experiments/run_concurrency_eval.py
python experiments/run_exact_write_baseline.py --repetitions 100
python scripts/make_submission_figures.py
python scripts/prepare_usenix_source.py --check
python scripts/verify_refs.py
python scripts/submission_check.py
```

The last command is a readiness status gate, not a quick-evaluation success
criterion; it intentionally exits non-zero while the roadmap still has open
submission blockers.

A post-hardening development-machine run is preserved at
`artifact/results/quick/20260924T202726Z/`. Its `run.json` records a dirty Git
worktree, so it is evidence that the runner works and that the offline checks
passed—not a release-candidate artifact. That timestamped run contains 196
tests; three BibTeX/PDF release checks were added afterward, bringing the
current direct suite to the count below.

Run `python -m pytest -q` for the current exact count; the checked release
metadata records it. The symbolic-link case may skip on Windows only.

The symbolic-link test skips on Windows accounts without the privilege to
create symlinks. It must run, not skip, in the Linux artifact environment.

## 3. Full evaluation

Run unvetted third-party servers only inside the repository's constrained
container environment. Never run the registry corpus directly on a host that
contains credentials or sensitive files.

The fail-closed full runner is:

```bash
python scripts/run_full_artifact.py --preflight-only
python scripts/run_full_artifact.py
```

It refuses to start unless both 265-row human label sheets are complete, the
held-out manifest is `FROZEN` with at least 10 independent exact-version
servers and two per claimed class, the full Linux dependency lock is
hash-pinned, the Git tree is clean, and Linux/Docker are available. The current
PC now satisfies the Docker and dependency-lock portions. It still fails
closed on the two blank independent-human annotation sheets, the dirty
development tree, and the unmatched held-out evaluation; those checks must not
be bypassed for release evidence.

`artifact/held-out-candidates.json` contains the pre-outcome candidates and
audited launch-only amendments. `artifact/held-out-manifest.json` is now
`FROZEN` at 10 independently implemented servers after isolated schema and
benign-effect/oracle eligibility (EXACT 4, CONSTRAINED 4, UNDERSPECIFIED 2).
`artifact/results/heldout_eligibility.json` and
`artifact/results/heldout_workflow_eligibility.json` preserve the raw gates.
No attack, baseline, or MCPGate outcome was observed before the freeze. The
matched five-condition evaluation remains a separate open gate.

The individual diagnostic commands are:

```bash
python experiments/run_scale.py
python experiments/run_resource_sweep.py
python experiments/run_m2_real_server.py
python experiments/run_m4_adaptive.py
python experiments/run_m4_replay.py
python experiments/run_m4_unmediated_channel.py
python experiments/run_m4_utility_degradation.py
python experiments/run_m5_held_out.py
python experiments/run_m5_notes.py
python experiments/make_results.py
python experiments/build_notebooks.py
```

The full runner records, for every stage:

- Git commit and dirty-state indicator;
- UTC start/end time;
- exact command and exit code;
- OS, kernel, CPU, memory, Python, Node, Docker, and image digest;
- Python lock-file hash;
- npm/PyPI package name and resolved version for every server;
- SHA-256 and byte length for every raw output; and
- stdout/stderr logs without secrets.

## 4. Claim-to-command map

| Claim | Command / evidence | Current artifact state |
|---|---|---|
| Transcript-indistinguishability demonstration | `python experiments/demo_theorem1.py` | runnable offline |
| Funnel 8,692 → 4,121 → 1,242 | `run_scale.py`; `make_results.py`; `results/tables/funnel.md` | table and historical hash present; raw trace gitignored |
| Auditor operating points | `analyze_operating_points.py`; `results/tables/operating_points.md` | table and local raw inputs present; raw inputs gitignored |
| Effect-oracle separation | `python experiments/run_effect_oracle.py` | runnable offline |
| Controlled M2 result | `run_m2_boundary.py`; `results/tables/boundary_probe_m2.md` | historical raw local only |
| Integrated mediator behavior | `tests/test_filesystem_mediator.py` | runnable offline |
| Controlled property ablations | `python experiments/run_mediator_ablations.py` | seven-row JSON and generated table checked in |
| Controlled baselines | `python experiments/run_gateway_eval.py` | no defense, plain sandbox, response auditor, path policy, trusted executor |
| Process-backed concurrency | `python experiments/run_concurrency_eval.py` | child-process intervals and distinct staging evidence checked in |
| Exact-write direct-writer baseline | `python experiments/run_exact_write_baseline.py --repetitions 100` | development-machine security cases and latency table checked in |
| Integrated third-party path | `python experiments/run_m2_real_server.py`; `artifact/results/integrated_real_server.json` | pinned development run passed; clean release-commit repeat pending |
| TOCTOU adaptive attack | `python experiments/run_m4_adaptive.py` | historical result local only; increase repetitions |
| Replay attack | `python experiments/run_m4_replay.py` | historical result local only; reusable-path tests present |
| Unmediated-channel limit | `python experiments/run_m4_unmediated_channel.py` | historical result local only |
| Fixed-window limit | `python experiments/run_m4_utility_degradation.py` | historical result local only |
| Static-permission comparison | `run_m5_held_out.py`, `run_m5_notes.py` | two-server pilot, not final held-out set |
| Reference integrity | `python scripts/verify_refs.py` | runnable offline; manuscript accepts only verified keys |

## 5. Acceptance checks for the next integrated Docker run

If the local machine cannot run Docker, use the manual, read-only hosted Linux
workflow in `.github/workflows/release-evidence.yml`; operating instructions
and safety boundaries are in `paper/CI_LINUX_RUNBOOK_BN.md`. A workflow file is
not evidence by itself: preserve the downloaded run artifact and its hashes.

The checked-in lock fixes `filesystem-mcp@1.3.0` and its npm SHA-512 integrity,
resolved from registry metadata on 2026-09-25. The build re-checks npm's
`dist.integrity` against that value. The runner refuses floating tags, builds a
fresh image, and disables runtime networking; it must not be modified to fall
back to `npx -y` or an existing `:latest` image.

The run passes only if all of the following are present in raw output:

- honest invocation: `COMMITTED`, ledger `COMMITTED`, byte-exact trusted file;
- path diversion: mediator refusal, ledger `FAILED`, trusted store empty;
- content substitution: mediator refusal, ledger `FAILED`, trusted store empty;
- outside-world observations are reported separately and never relabeled as
  trusted-store commits;
- every row records all pipeline stages; and
- server version, image digest, host kernel, and invocation command are saved.

## 6. Data-release plan

The current `.gitignore` excludes `data/processed/*.json`. Before artifact
freeze, export a curated bundle under `artifact/results/` containing:

- compact per-trial JSON for every paper table;
- a schema describing every field and UNKNOWN state;
- table/figure regeneration scripts;
- a full SHA-256 manifest;
- aggregate outputs for any trace that cannot be redistributed; and
- a documented reason for every omitted field or server.

Hashes of unavailable private/local files are provenance aids, not a substitute
for a reproducible artifact. The paper must not claim full fresh-clone
reproduction until this bundle is checked in and tested in a clean environment.

## 7. Human-required steps

Round-2 classifier validation requires two genuinely independent annotators.
The new 265-row sheets in `data/processed/labels_annotator_A.tsv` and
`labels_annotator_B.tsv` are currently blank. After both are complete:

```bash
python experiments/score_labels.py \
  --a data/processed/labels_annotator_A.tsv \
  --b data/processed/labels_annotator_B.tsv \
  --archive data/processed/label_sheet.corpus_archive.jsonl
```

If Cohen's kappa remains below 0.60, report the failure and remove classifier
prevalence claims; do not adjudicate labels merely to force the gate to pass.
Use `paper/ROUND2_ANNOTATION_RUNBOOK_BN.md` for independence, freeze, and
adjudication. Human annotators, author review of every citation, and final
ethics/conflict declarations cannot be automated away.

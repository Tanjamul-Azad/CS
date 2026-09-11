# Documentation map

**One question, one answer: to understand the whole project, read the five documents in "The spine" below, in order. Everything else is reference.**

Current goal, fixed 2026-09-10:

> How much of a per-call authorization can be translated into generic filesystem, network and process restrictions, such that unauthorized effects are blocked across heterogeneous untrusted MCP implementations while honest workflows still complete — and where are application-level adapters unavoidable?

Full statement, threat model and milestones: [`25-research-program.md`](25-research-program.md).

---

## The spine — read these eight, in this order

| # | Doc | What you learn | Length |
|---|---|---|---|
| 1 | [`04-threat-model.md`](04-threat-model.md) | What an adversarial MCP server can do, and why this is not generic server compromise | short |
| 2 | [`05-verifiability-taxonomy.md`](05-verifiability-taxonomy.md) | **Theorem 1** — a passive client can never detect a diverted effect. The A0–A3 auditability classes | short |
| 3 | [`21-real-server-results-and-options.md`](21-real-server-results-and-options.md) | What happened when the defense met 1,242 real third-party servers | medium |
| 4 | [`24-calibrated-auditing-the-real-experiment.md`](24-calibrated-auditing-the-real-experiment.md) | Why it failed — found by auditing our own detector. The measurement the program is built on | medium |
| 5 | [`26-m1-novelty-gate.md`](26-m1-novelty-gate.md) | **What the literature already owns.** Read before the plan — it retires three of its claims | medium |
| 6 | [`25-research-program.md`](25-research-program.md) | **The plan.** Goal, scope, permit rule, milestones M0–M6 with acceptance criteria | long |
| 7 | [`27-narrow-candidate-experiment.md`](27-narrow-candidate-experiment.md) | **What runs next.** The comparison that decides whether a system contribution exists | short |
| 8 | [`28-kappa-result.md`](28-kappa-result.md) | **M0c result.** κ = 0.559, below gate — one clean A0/A2 confusion, and a data-provenance bug fixed | short |

After those eight you know the problem, the impossibility result, the measured failure, the diagnosis, and the plan. Nothing else is required.

## To see the evidence rather than read about it

| Where | What |
|---|---|
| [`../results/README.md`](../results/README.md) | Every reported number, regenerated from raw data by one command, with per-input hashes |
| [`../notebooks/`](../notebooks/) | Five executed notebooks — outputs and figures embedded, no kernel needed |

## The current code

| Package | Role |
|---|---|
| `src/measure/` | Static extraction and the A0–A3 classifier — the corpus measurement |
| `src/mcpaudit/` | The auditor: relation derivation, R1/R2/R7 checks, calibration |
| `src/mcpmut/` | The adversary (`proxy.py`) and live MCP session (`live.py`) |
| `src/mcpgate/` | The contract layer for effect mediation — **prototype, architecture under revision (see `25` §3)** |

---

## Reference — consult when you need the detail

### Framing and positioning
| Doc | |
|---|---|
| [`00-RESEARCH-PLAN.md`](00-RESEARCH-PLAN.md) | Original master plan and contributions C1–C7. Predates the pivot; read for the thesis, not the plan |
| [`02-gap-analysis.md`](02-gap-analysis.md) | The input-vs-effect integrity grid, and the empty quadrant |
| [`12-intellectual-lineage.md`](12-intellectual-lineage.md) | What this inherits from metamorphic testing, runtime verification, BFT and 8 more fields — **and the assumption that breaks in each.** Needed for milestone M1 |
| [`01-literature-review.md`](01-literature-review.md) · [`03-novelty-contributions.md`](03-novelty-contributions.md) | Prior work and novelty audit. **Both need refreshing under M1's citation quarantine** |

### Design and implementation
| Doc | |
|---|---|
| [`11-runtime-validation-design.md`](11-runtime-validation-design.md) | The MBA defense: relations R1–R6, the adversary ladder |
| [`10-implementation-notes.md`](10-implementation-notes.md) | Code architecture and invariants that must not break |
| [`16-design-history.md`](16-design-history.md) | **The pivots.** Two designs died; why, and what replaced them |
| [`14-labeling-codebook.md`](14-labeling-codebook.md) | How to hand-label A0–A3. **Needed now — milestone M0** |

### Findings
| Doc | |
|---|---|
| [`15-d1-findings.md`](15-d1-findings.md) | The static corpus: 18,566 tools, 69.7% A0 |
| [`18-evaluation-findings.md`](18-evaluation-findings.md) | Controlled-benchmark evaluation. **Reframe as a cost-ladder illustration, not evidence** (`24` §8) |
| [`19-reviewer-review.md`](19-reviewer-review.md) | Adversarial self-review, read as a hostile PC member. Still the sharpest critique on file |

### Superseded, kept as decision history
[`archive/`](archive/) — seven planning documents that were overturned. See [`archive/README.md`](archive/README.md).

### Transitional
[`22-research-diagnosis-and-10-day-plan.md`](22-research-diagnosis-and-10-day-plan.md) and [`23-frozen-direction-auditability-analyzer.md`](23-frozen-direction-auditability-analyzer.md) record the two intermediate directions between `21` and `25`. Both were written under a deadline that no longer applies. Read only for how the direction moved; `25` overrides both.

---

## Standing rules

These survive every replan. Full statements in [`25`](25-research-program.md) §8.

- **Citation quarantine.** No citation enters the paper until a primary source is opened and its identifier recorded. All entries in `paper/references.bib` are still marked `[U]` unverified.
- **Pre-registration.** Every evaluation milestone gets its success criterion written down before the run.
- **Instrument bugs are the default hypothesis.** Two have been found by self-audit: suppressed detections, and an MCP error flag read under a name the SDK does not define, which made 65% of "landed attacks" writes the server had actually refused. Assume a third exists.
- **Report prevented / detected / UNKNOWN separately.** A refusal and a compromise are opposite events that look identical in world state.
- **No theorem labels without statements and proofs.** "Cost Observation", not "Theorem 2".

## Honest caveats

- **The 69.7% A0 figure is an instrument reading, not yet a measurement.** The classifier has never been scored against human judgment. This is milestone M0 and it is the oldest open blocker in the project.
- **The corpus is credential-free servers only.** `registry_candidates.json` was filtered to servers that run without secrets, so the servers where diversion matters most — mail, payments, code hosting — are absent.
- **The analysed subset is the favourable tail.** Servers surviving the audit funnel have A0 36.7% against 81.5% among those that dropped out.
- **Detection numbers recorded before 2026-09-10 used an inflated denominator** and cannot be corrected retrospectively; they are labelled in `results/tables/operating_points.md`.

# Experiment Plan

---

## 1. Research questions

| RQ | Question | Contribution | Asset | Status |
|---|---|---|---|---|
| **RQ1** | Does metadata integrity detect declaration-changing mutations? | baseline | D2 | ✅ prelim |
| **RQ2** | Does behavior-only mutation bypass it? | setup | D2 | ✅ prelim |
| **RQ3** | **Does an adaptive adversary defeat response validation, as Theorem 1 predicts?** | C2 | D2 | ✅ DBR 100%→0% |
| **RQ4** | **How many metamorphic relations are auto-derivable from real MCP declarations, and what is the relation-degree distribution?** | C4 | D1 | ❌ |
| **RQ5** | **What fraction of real MCP tools are A0 — undetectable at any audit budget?** | C5 | D1 | ❌ |
| **RQ6** | **What does consistency cost the attacker, per relation layer?** (shadow-state size, LOC, per-call overhead) | C6 | D2 | ◐ prototype: 3/9/17 LOC |
| **RQ7** | What is MBA's detection-vs-overhead curve across adversary tiers and audit budgets? | C3 | D2 | ❌ |
| **RQ8** | Can a T3 probe-aware adversary distinguish audit calls from task calls? | C3 | D2 | ❌ |
| **RQ9** | Does the argument-integrity gap (I) compound with the effect-integrity gap (E)? | C1 | D3+D2 | ❌ |

RQ1–RQ3 are settled and appear as a short subsection, not the headline. **RQ4–RQ7 are the paper.** RQ8 is the honest stress test of our own defense; a negative result there is publishable and must be reported either way.

## 2. Experimental matrix (D2 / MCP-MutBench)

**Factors:** 4 domains × 6 mutations (M1–M6) × 5 defenses × 3 models × 30 trials.

Not fully crossed — M5/M6 only meaningfully interact with response-based defenses, and V1 replay only applies to V1 tools. Effective ≈ **7,000–11,000 trials**.

**Defense conditions**
| ID | Defense | Purpose |
|---|---|---|
| D-none | no defense | ASR ceiling |
| D-hash | SHA-256 pin over (name, description, schema) | ETDI proxy — literature's consensus fix |
| D-resp | naive response validator | the obvious fix; **we show it fails** |
| D-intent | MELON/Task-Shield-style intent match | published-defense baseline |
| D-bim | BIM, class-aware | ours |
| D-bim+hash | combined | ablation |

**Models** — must include ≥1 frontier commercial model to answer R5:
1. `openai/gpt-oss-120b` (Groq) — continuity with preliminary results
2. `llama-3.3-70b-versatile` (Groq) — cheap second point
3. one frontier model (Claude / GPT-4o class) — external validity

## 3. Metrics

| Metric | Definition | Note |
|---|---|---|
| **ASR** | successful attacks / attack trials | **measured against the out-of-band oracle**, never the server's self-report |
| **DBR** | blocked attacks / attack trials | |
| **FPR** | benign ops incorrectly blocked / benign ops | includes *legitimate* description updates |
| **TSR** | benign tasks completed / benign tasks | utility preservation |
| **ΔL** | added latency per call | overhead |
| P/R/F1 | for the detector as binary classifier | per V-class |

**Non-negotiable:** ASR is computed from ground-truth effect `e` recorded out-of-band by the harness. Deriving ASR from the response means measuring what the attacker chose to disclose. This flaw is present in the previous design and must not survive.

## 4. Statistics

- **Unit of analysis:** trial. Trials within a (domain, model) cell are not independent → use **cluster-robust** methods or mixed-effects logistic regression with random intercepts per domain.
- **Primary test (RQ3):** ASR under D-resp against A\* vs. against naive M4. Two-proportion test with CIs; expect a large effect.
- **Primary test (RQ5):** BIM vs. D-hash on V1–V3, McNemar's test on paired trials.
- **CIs:** Wilson score for all proportions. **Never report a bare percentage.**
- **Multiple comparisons:** Holm–Bonferroni across the RQ family.
- **Effect sizes:** risk difference + odds ratio.
- **Power:** at n=30/cell, detecting 0.80 vs 0.30 has power > 0.95. Detecting 0.80 vs 0.65 needs n≈150 — so **any cell where we expect a small difference gets n=150**, not 30. Preliminary work used 30 uniformly; that is underpowered for the subtle comparisons.

## 5. Measurement study (D1 / RQ4)

1. Harvest ≥200 servers → ≥1,500 tools
2. Codebook → 300 stratified sample → double-annotate → κ
3. Train/tune classifier on 150 dev; report once on 150 held-out test
4. Classify full corpus; report V-distribution with CIs **widened by classifier error**
5. Breakdowns: by `server_kind`; pseudo-V2 rate; V0 × severity cross-tab

## 6. Ablations

| Ablation | Isolates |
|---|---|
| BIM minus V1 replay | replay contribution |
| BIM minus V2 corroboration | corroboration contribution |
| BIM minus independence check | **pseudo-V2 effect** — expect large |
| V1 replay sample rate p ∈ {0.1, 0.25, 0.5, 1.0} | detection/overhead curve |
| M6 probe-aware adversary vs. M5 | probe-detection arms race |

## 7. Compute and budget

| Item | Estimate |
|---|---|
| D2 trials | ~10k calls × ~2k tokens ≈ 20M tokens |
| Groq (models 1–2) | free tier + checkpointing; ~2–3 days wall clock |
| Frontier model | subset only — 1 domain × key conditions ≈ 1.5k trials |
| Classifier LLM calls | ~4k tools × 1 call ≈ cheap |
| **Total spend target** | **< $80**, achievable with Groq-heavy design |

**Checkpoint/resume is mandatory** — the prior notebook already proves this pattern works (`already_done()` / `save_result()`); port it.

## 8. Threats to validity

| Threat | Type | Mitigation |
|---|---|---|
| Synthetic benchmark | External | pair with D1 real measurement + D3 public benchmark |
| Single protocol (MCP) | External | discuss generality to OpenAI function calling, A2A |
| Model selection | External | 3 models spanning open/frontier |
| Classifier error | Construct | validated on held-out; error propagated into CIs |
| Our own oracle could be wrong | Internal | oracle is the harness's own ledger, independent of server code path; unit-tested |
| Prompt sensitivity | Internal | 3 paraphrases of each task prompt; report variance |
| Researcher degrees of freedom | Internal | **pre-register RQ/metrics/tests in repo before running final experiments**; held-out test touched once |

## 9. Execution order

1. Port checkpoint/resume; build D2 harness + out-of-band oracle
2. M1–M4 replication (sanity: should reproduce preliminary result)
3. **M5 adaptive adversary → RQ3** ← *first genuinely new result; do this early*
4. D1 harvester + codebook + labeling → RQ4
5. BIM implementation → RQ5
6. Ablations, frontier model, statistics
7. Figures, then paper

Step 3 is the fastest path to a result that does not currently exist anywhere. Prioritize it.

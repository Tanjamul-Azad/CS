# Plan to Submission

Response to [`19-reviewer-review.md`](19-reviewer-review.md). Every phase closes a numbered objection and states **how we will know it is closed** — an acceptance criterion decided *before* the experiment runs, so a disappointing result is a finding rather than something to quietly re-tune.

**Target:** USENIX Security, Tier-1 only, no workshop hedge.
**Estimated total: 14–17 weeks of build + 4 weeks of writing.**

---

## The strategic choice

Two viable papers exist in this repo.

| | Paper A — Measurement | Paper B — Measurement + Defense |
|---|---|---|
| Content | D1 corpus, A0–A3, protocol recommendations | + MBA, cost model, full evaluation |
| Ready in | ~4 weeks (κ + writing) | ~18–21 weeks |
| Risk | low; already near-submittable | medium |
| Ceiling | solid measurement paper | genuine systematisation + defense |

**Decision: Paper B.** Paper A is the fallback if a phase fails badly — and because Paper B strictly contains it, the fallback costs nothing but time.

---

## Phase 1 — Real-server evaluation at scale 🔴 *(closes R1)*

**Progress:** step 1 (triage) ✅ — 32 servers runnable standalone, above the 15 kill criterion. Step 3 (generic proxy) ✅ — built, tested, and demonstrated diverting a write on the unmodified official filesystem server with 0 false positives (`src/mcpmut/proxy.py`, `experiments/run_live.py`). Steps 2 and 4 (launch the 32 in a sandbox, run at scale) remain — operational, and gated on approval because they execute untrusted third-party packages.

**The single most important phase.** Converts "we tested our own toys" into "we tested N servers we did not write."

### What exists to work with

Of 295 harvested servers, **123 have ≥2 tools with both reads and writes** — the audit-relevant population. 64 TypeScript, 58 Python.

### Build

1. **Launchability triage.** Attempt install + `tools/list` for all 123. Record why each fails: missing credentials, external service, build error, non-MCP. **The failure distribution is itself publishable** — how much of the ecosystem can even be independently audited?
2. **Sandbox harness.** Each server in a container with a scratch dir, no network egress except explicitly allowed, credentials stubbed.
3. **Generic tampering proxy.** Sits between auditor and server, implements the ladder generically: L1 forge response, L2 shadow the read, L3 shadow the aggregate. Must be domain-agnostic — driven by declarations, not hand-written per server.
4. **Run:** detection, FPR, overhead per server. Report a **distribution**, not a mean.

### Acceptance criteria — set now

- ≥ **30 real servers** launched and audited
- FPR on unmodified servers **< 5%**, reported per server
- Detection against L1 proxy **> 80%** on servers with derivable relations
- Every failure explained, none silently dropped

> **If FPR exceeds 5% on real servers, that is the paper's most important finding and we report it as such.** The concurrency result (20→0%) came from exactly this kind of failure.

**Effort: 4–5 weeks.**

---

## Phase 2 — Run the real baselines 🔴 *(closes R2)*

### Build

1. Obtain artifacts for **Progent** and **ETDI** (and MCP-Guard / IPIGuard if code exists). Where none exists, implement faithfully from the paper and **say so explicitly**.
2. Run each against our adversary ladder.
3. **Expect them to score ~0%** — they defend input integrity, not effect integrity.

### The framing that makes this a strength

A baseline that fails *for a reason we predicted and explain* is far more persuasive than an omitted one. This is the gap argument made empirical: not "nobody does this" but "here is what happens when you point the existing defenses at it."

- Retire `hash-pin` as a headline baseline. Keep it as the ETDI *mechanism*, correctly attributed.
- Add **one strong strawman**: an LLM-judge that reads request+response and flags inconsistency. It should also fail (Theorem 1), and it is the defense a reviewer will ask about.

### Acceptance
- ≥ 2 published defenses run, or documented as unobtainable with reason
- LLM-judge baseline implemented and evaluated
- Every 0% accompanied by a mechanistic explanation

**Effort: 2–3 weeks.**

---

## Phase 3 — Documented incident corpus 🔴 *(closes R3)*

Our practical-relevance claim currently rests on one anecdote.

### Build

Systematically collect **10–15 documented compromises** of agent tools / MCP servers / adjacent supply chain (malicious npm/PyPI packages that exfiltrate, IDE-extension backdoors, CI supply-chain incidents). For each, from the public writeup, record:

- what the attacker modified
- **did they maintain shadow state?** (did the compromised component keep faking a consistent view?)
- estimated LOC of the malicious patch
- would MBA have caught it? — *judged blind, before knowing the answer we want*

### Acceptance
- ≥ 10 incidents with primary sources in the bibliography
- Distribution of shadow-state maintenance reported honestly
- **If most real attackers DO maintain shadow state, the paper's framing changes.** We must be willing to find that.

**Effort: 2 weeks. Can run in parallel — mostly literature work.**

---

## Phase 4 — Fix the A0 claim 🟠 *(closes R4)*

The claim "undetectable at any budget" presumes R1–R6 are exhaustive. We never argue that.

### Build

1. **Rewrite every A0 claim as instrument-relative**: "admits no relation derivable by our method."
2. **Empirical completeness check.** The κ sheet's `check` column asks annotators to name a concrete verification. For tools our classifier calls A0, count how often a *human* — with no knowledge of R1–R6 — can name one. Low rate = evidence the class is real. High rate = our vocabulary is incomplete, and that is a finding.
3. Add a discussion subsection on what a *richer* relation vocabulary could reach.

### Acceptance
- No claim in the paper asserts absolute undetectability
- Human-nameable-check rate for A0 tools reported with κ

**Effort: 1 week + folded into κ.**

---

## Phase 5 — Theorem 2: prove or downgrade 🟠 *(closes R5)*

Currently three hand-written numbers labelled a theorem.

**Attempt** a real statement: *evading relation set R over a horizon of n calls requires shadow state of size ≥ f(|R|, n)*, by an adversary-argument — if the shadow is smaller than the reachable distinguishable-state space, two states collide and some relation separates them.

**If that does not go through in 2 weeks, downgrade to "Cost Model" and let the empirical curve carry it.** A reviewer respects an honest downgrade; a mislabel is a credibility hit that spreads to everything else.

### Acceptance
- Either a stated-and-proved bound with explicit assumptions, or the label is changed everywhere
- Cost curve extended to ≥ 6 rungs, LOC counted by an **independent implementer** (not the person who designed the ladder)

**Effort: 2 weeks, hard-capped.**

---

## Phase 6 — Harden the LLM evaluation 🟠 *(closes R6)*

320 episodes currently yield ~32 independent data points.

### Build
- **3+ models** including a weak one where tool-selection genuinely errs (`gpt-4o-mini`, Groq `llama`/`gpt-oss`, local Gemma)
- **Multi-step tasks** (3–5 tool calls, dependencies between them)
- **Servers with 15+ tools**, including distractors, so selection is non-trivial
- Report **per-model variance**; if it stays zero, say so and explain why

### Acceptance
- ≥ 3 models, ≥ 2 task-complexity tiers
- Non-degenerate variance in at least one tier, or a mechanistic explanation for its absence
- Utility measured on tasks the agent can actually fail

**Effort: 2 weeks. Cheap in tokens; the earlier full run cost ~$0.02.**

---

## Phase 7 — κ, with a held-out split 🟠 *(closes R7)*

**Two annotators, 265 tools, independent** — sheets already generated.

The compounding problem: write-verbs were expanded *after* seeing corpus data. That is fitting the instrument to the sample.

### Build
1. **Split the corpus 50/50 by server.** Freeze the classifier on the tuning half.
2. Report κ, per-class precision/recall, confusion, and **A0 bias** on the **held-out half only**.
3. Report the tuning-half numbers separately so the gap is visible.

### Acceptance
- κ ≥ 0.70 (below 0.60 → revise codebook and re-label, do not argue cases)
- Held-out A0 bias reported beside every headline number
- Tuning/held-out gap disclosed

**Effort: 2–3 days of annotator time (you + Jahidul) + 2 days of analysis.**

---

## Phase 8 — The minors 🟡 *(closes R8–R11)*

| | Fix | Effort |
|---|---|---|
| R8 | Probe-aware sweep across all 4 domains + real servers | 3 days |
| R9 | Query npm + PyPI for MCP servers absent from GitHub; **quantify** the frame gap | 3 days |
| R10 | Measure decoy overhead properly; report the real cost of the 25%-budget claim | 2 days |
| R11 | Reframe Theorem 1 around *authority-as-resource*; position against TOCTOU folklore | writing |

**Effort: ~2 weeks total.**

---

## Schedule

| Weeks | Work | Runs in parallel with |
|---|---|---|
| 1–5 | **Phase 1** real-server evaluation | Phase 3 (literature), Phase 7 (annotation) |
| 3–5 | **Phase 3** incident corpus | Phase 1 |
| 4 | **Phase 7** κ + held-out | Phase 1 |
| 6–8 | **Phase 2** real baselines | Phase 5 |
| 6–8 | **Phase 5** Theorem 2 (hard cap) | Phase 2 |
| 9–10 | **Phase 6** LLM hardening | Phase 8 |
| 9–11 | **Phase 8** minors | — |
| 12–13 | Re-run everything; regenerate all figures and docs | — |
| 14–17 | **Write** | — |
| 18 | Internal red-team against [`19`](19-reviewer-review.md); fix; submit | — |

---

## Kill criteria — decided in advance

Stated now so we cannot rationalise later.

| If | Then |
|---|---|
| < 15 real servers launchable | Evaluation cannot carry Paper B → **fall back to Paper A** |
| FPR > 15% on real servers and unfixable | MBA is not deployable; **report that as the finding** |
| Incident corpus shows most attackers DO maintain shadow state | Reframe: the cost curve matters less than we claim |
| κ < 0.60 after one codebook revision | The A0–A3 construct is underspecified; rebuild it |

---

## What does not change

The things a reviewer would praise, which the rebuild must not damage:

- Reporting our own failures ([`18`](18-evaluation-findings.md): 20–86% FPR; probe-aware detection = 0)
- Recording falsified hypotheses ([`16`](16-design-history.md))
- Stating the ceiling in the abstract — the 17-LOC adversary wins
- Never claiming coverage the tool does not have

---

## Immediate next actions

| Who | What |
|---|---|
| **You + Jahidul** | κ annotation — `data/processed/labels_annotator_{A,B}.tsv`, codebook [`14`](14-labeling-codebook.md). Runs parallel to everything. |
| **Me, now** | Phase 1 step 1: launchability triage of all 123 candidate servers |
| **Me, next** | Generic declaration-driven tampering proxy |

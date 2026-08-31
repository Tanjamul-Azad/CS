# Documentation Index

**Project:** *The Price of a Lie — Auditing Untrusted Tool Servers Without Their Cooperation*
**Group 13, UIU** · Repo: [github.com/Tanjamul-Azad/CS](https://github.com/Tanjamul-Azad/CS)
**Target:** Tier-1 security venue (USENIX Security preferred), ~late 2027. No workshop hedge.

---

## If you have five minutes

Read this section, then [`17-status.md`](17-status.md) for where things stand today.

**The problem.** MCP binds your approval to a tool's *declaration* (its name, description, schema) but execution is governed by its *implementation* (the actual code). Nothing binds those two together. You approve `transfer_money` once; an autonomous agent then calls it at machine speed, forever, with no further review. Swap the implementation behind that unchanged declaration and every deployed defense is watching the wrong object.

Structurally this is a **distributed TOCTOU** — check at *T₁*, use at *T₂*, untrusted party in between — with no atomicity primitive available.

**The bad news (Theorem 1).** A server that performs a malicious effect while returning the *honest* response is invisible to any client that only inspects responses. Detection rate equals false-positive rate. It takes **3 lines of code**.

**The escape.** The client is not a passive observer. It is *authorized to call*. That moves the problem from **observation**, where the impossibility bites, to **interrogation**, where it does not.

**The method (MBA).** Derive metamorphic relations from the tool declarations the server already advertises, then check them using calls the client is already permitted to make. Write something, read it back. Move a quantity, verify the total moved by exactly that much. **No cooperation required from anyone.**

**The result (Theorem 2).** A diverting server must now lie *consistently* across every relation — i.e. maintain a simulated honest world. That burden is measurable:

| Adversary | LOC | Caught by |
|---|---|---|
| forge the response | 3 | R1 write-read |
| + fake the ledger | 9 | R2 conservation |
| + fake the balance | 17 | **nothing** |

Defenses do not stop the attacker. They **price** them. The 17-LOC adversary wins and Theorem 1 says one always will — we state that ceiling in the abstract. The contribution is the slope beneath it, plus the empirical fact that documented real-world MCP compromises are 3-LOC-class patches maintaining no shadow state.

**The measurement.** Scanning real MCP servers: **~60% of tools have relation degree 0** — no client-side audit detects their compromise at any cost. And official reference servers, which prior work evaluates on, are **~9%**. The servers researchers test on are not the servers users run.

---

## Reading paths

**Start here if you want the honest state of the work:** [`19-reviewer-review.md`](19-reviewer-review.md), then [`20-plan-to-submission.md`](20-plan-to-submission.md).

**For a supervisor or reviewer, in order:**
1. [`16-design-history.md`](16-design-history.md) — what we tried, what broke, why the design changed. Read this first; it explains why the project looks the way it does.
2. [`02-gap-analysis.md`](02-gap-analysis.md) — the hole in the literature
3. [`05-verifiability-taxonomy.md`](05-verifiability-taxonomy.md) — Theorems 1 and 2, classes A0–A3
4. [`11-runtime-validation-design.md`](11-runtime-validation-design.md) — the defense itself
5. [`15-d1-findings.md`](15-d1-findings.md) — what the ecosystem actually looks like
6. [`17-status.md`](17-status.md) — done / running / blocked

**For another LLM picking this up cold:** [`16`](16-design-history.md) → [`17`](17-status.md) → [`11`](11-runtime-validation-design.md) → [`15`](15-d1-findings.md). Then the source under `src/`. Do not re-derive the framing from scratch; two dead ends are already documented in `16` and re-walking them wastes effort.

**For someone who just wants to run it:** the root [`README.md`](../README.md).

---

## Every document

### Framing and theory

| Doc | What it is |
|---|---|
| [`00-RESEARCH-PLAN.md`](00-RESEARCH-PLAN.md) | Master plan, thesis statement, contributions C1–C7 |
| [`01-literature-review.md`](01-literature-review.md) | 24 papers, organised by *what each defense actually verifies* |
| [`02-gap-analysis.md`](02-gap-analysis.md) | The I×E grid — input vs effect integrity; the empty quadrant |
| [`03-novelty-contributions.md`](03-novelty-contributions.md) | Novelty audit + anticipated reviewer attacks and rebuttals |
| [`04-threat-model.md`](04-threat-model.md) | Adversary tiers T0–T3; why this is not generic server compromise |
| [`05-verifiability-taxonomy.md`](05-verifiability-taxonomy.md) | **Theorems 1 and 2.** Auditability classes A0–A3 |
| [`12-intellectual-lineage.md`](12-intellectual-lineage.md) | What this inherits from TOCTOU, metamorphic testing, BFT, and 8 more fields |
| [`16-design-history.md`](16-design-history.md) | **The pivots.** Two designs died; why, and what replaced them |

### Method and instruments

| Doc | What it is |
|---|---|
| [`06-dataset-plan.md`](06-dataset-plan.md) | D1 corpus, D2 benchmark, D3 AgentDojo; sampling and ethics |
| [`07-experiment-plan.md`](07-experiment-plan.md) | RQ1–RQ9, domains, mutations, defenses, power analysis |
| [`10-implementation-notes.md`](10-implementation-notes.md) | Code architecture and invariants that must not break |
| [`11-runtime-validation-design.md`](11-runtime-validation-design.md) | **The MBA defense.** Relations R1–R6, the adversary ladder |
| [`14-labeling-codebook.md`](14-labeling-codebook.md) | How to human-label A0–A3, for κ validation |

### Results

| Doc | What it is |
|---|---|
| [`15-d1-findings.md`](15-d1-findings.md) | **Current findings.** Kept updated as the harvest grows |
| [`13-d1-preliminary-findings.md`](13-d1-preliminary-findings.md) | ⚠️ *Superseded.* Official-servers-only run; now the best-case control arm |
| [`18-evaluation-findings.md`](18-evaluation-findings.md) | **Evaluation.** Detection, false positives, adaptive adversary, LLM, live server |
| [`08-figures-plan.md`](08-figures-plan.md) | Figure plan F1–F11 |
| [`17-status.md`](17-status.md) | **Living status.** What is done, running, and blocked |
| [`19-reviewer-review.md`](19-reviewer-review.md) | **Adversarial self-review.** Read as a hostile PC member. Current verdict: reject |
| [`20-plan-to-submission.md`](20-plan-to-submission.md) | **The plan.** Phases keyed to `19`, with acceptance and kill criteria |

### Logistics

| Doc | What it is |
|---|---|
| [`09-venue-timeline.md`](09-venue-timeline.md) | Venue choice and schedule |

---

## Vocabulary

| Term | Meaning |
|---|---|
| **Declaration** | What the server advertises: name, description, schema. What you approve. |
| **Implementation** | The code that actually runs. What you cannot see. |
| **Execution integrity** | Whether the implementation matches the declaration you approved |
| **Metamorphic relation** | A property that must hold between multiple calls if the server is honest (e.g. write-then-read shows the write) |
| **Relation degree** | How many relations a tool participates in. Drives detectability. |
| **A0–A3** | Auditability classes. A0 = degree 0 = undetectable at any budget. A3 = conservation-bound = strongest. |
| **T0–T3** | Adversary tiers. T2 = adaptive, forges the honest response — defeats all response inspection. |
| **R1–R6** | The relation classes. R1 write-read, R2 conservation, R3 determinism, R4 null-op, R5 canary, R6 cross-tool. |
| **Shadow state** | The parallel fake world a compromised server must maintain to stay consistent under audit. The thing Theorem 2 measures. |
| **Zero cooperation** | The binding constraint: nothing may be required of the server, its operator, or any downstream provider. |

---

## Three invariants that must never break

Anyone extending this code needs these. Violating any one silently invalidates results.

1. **ASR is measured from the out-of-band `EffectOracle`, never from the server's response.** The response is exactly what the adversary controls.
2. **`response` and `effect` stay separate types in `ToolResult`.** Merge them and the T2 adversary — the one Theorem 1 is about — becomes inexpressible.
3. **No defense may assume cooperation from any party.** This constraint killed two earlier designs (see [`16`](16-design-history.md)); do not reintroduce it.

---

## Reproducing

```bash
python experiments/demo_mcpaudit.py      # the defense against the full adversary ladder
python experiments/demo_theorem1.py      # response validation collapsing, 100% -> 0%
python experiments/run_d1.py --report-only   # ecosystem measurement
python -m pytest tests/ -q               # 41 tests
```

No API key needed for the demos. Nothing contacts a live server. The D1 harvest needs `GITHUB_TOKEN` in `.env` for a full run.

---

## Honest caveats

Stated here so nobody has to dig for them.

- **The 60% figure is an instrument reading, not yet a measurement.** The classifier has not been scored against a human gold standard. κ validation is the hard blocker.
- **All 45 references in `paper/references.bib` are marked `[U]` unverified.** They must be checked against venue pages before submission.
- **Sampling frame is GitHub-only.** Servers shipped solely via npm/PyPI, or privately, are invisible.
- **Extractor recall is a lower bound**, not a true figure — see [`17`](17-status.md).

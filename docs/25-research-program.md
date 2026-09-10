# RESEARCH PROGRAM — Contract-Bound Effect Mediation for Untrusted MCP Servers

Written 2026-09-10. **This is the fixed plan.** It supersedes the deadline-shaped scoping in [`24`](24-calibrated-auditing-the-real-experiment.md) §10 and [`23`](23-frozen-direction-auditability-analyzer.md) §9. Those documents assumed an eight-day horizon and cut scope to fit it; that constraint is withdrawn. The measurement work in [`21`](21-real-server-results-and-options.md), [`22`](22-research-diagnosis-and-10-day-plan.md) and [`24`](24-calibrated-auditing-the-real-experiment.md) stands unchanged and becomes this program's foundation.

Work proceeds by milestone, not by date. A milestone is done when its acceptance criteria are met, not when a week has passed.

---

## 1. Goal

> Build and evaluate an execution-security layer for untrusted MCP servers that confines effects to what the user explicitly authorized, and that applies across heterogeneous tool implementations without per-tool engineering.

The last clause is the research. Everything before it is engineering.

---

## 2. Why this goal, and what it is NOT

**Where it comes from.** The measurement half of this project established, over 1,242 real third-party servers, that a client cannot reliably determine after the fact what a server actually did. Six mechanisms were implemented and measured; none reached a usable operating point; 25.3% of servers offer no observation channel that could support one at any budget. The design lesson is narrow and defensible:

> Do not rest safety on checking the response of a component that both performs the effect and produces the only evidence of it.

**What this is not.** It is *not* a proof that auditing is impossible, and the paper must not claim one. It is a measured limitation of protocol-only client-side auditing, which motivates moving the enforcement point rather than improving the detector.

---

## 3. The make-or-break problem

The gateway prototype in `src/mcpgate/` performs approved effects itself using a **trusted executor per effect family**. That design cannot meet the goal:

> If covering N tools requires N hand-written executors, "works across diverse implementations" means "we wrote N executors." That is effort, not generality, and a reviewer will say so in one sentence.

**Therefore the architecture changes.** Instead of the gateway performing the effect, the server performs it *inside a boundary where its real effects are observable and mediated*:

| | executor model (prototype) | **boundary model (this program)** |
|---|---|---|
| Who acts | gateway | server, confined |
| Per-tool code | one executor each | none |
| What is checked | the server's *proposal* | the server's *actual effect* |
| Generality | bounded by executors written | bounded by boundary coverage |
| Already built | yes, today | the sandbox exists (`docker/`) |

Effects are mediated where they are unavoidable and uniform:

- **filesystem** — which paths may be created, written, deleted
- **network** — which hosts, methods, and payloads may leave
- **process** — what may be spawned

A contract is then expressed in those terms, and no tool-specific knowledge is required. **`src/mcpgate/contract.py` survives this change** — contracts, binding fields, and verdicts are the same idea. What changes is where the check is applied.

**This is a hypothesis, not a result.** Whether real MCP effects are faithfully expressible as filesystem/network constraints is Milestone 3's question, and a negative answer there is itself a finding.

---

## 4. Threat model (to be fixed in Milestone 2, stated here as a starting point)

| | |
|---|---|
| **Attacker controls** | the MCP server's code and its responses; may have been benign at approval time and mutated after |
| **Attacker wants** | an effect the user did not authorize: different target, extra target, different payload, extra invocation, silent no-op |
| **We trust** | the client process, the contract, the mediation boundary, the sandbox |
| **We do NOT trust** | the server, its responses, its self-reported receipts, its declarations |
| **Explicitly out of scope** | prompt injection that corrupts the intent *before* a contract exists. The layer binds the SERVER to the contract; it does not establish the contract reflects the user's wish |

That last row is the honest boundary and must appear in the paper's own words, not only in a limitations section.

---

## 5. Permit rule

For a proposed effect `a` and approved contract `C`:

```
Permit(a, C) = Valid(C) ∧ Matches(a, C) ∧ Unused(C) ∧ Mediated(a)
```

- **Valid** — the contract is authentic and unexpired
- **Matches** — operation, target and payload fall inside the contract
- **Unused** — invocation allowance remains
- **Mediated** — the effect took the enforced path; nothing reached the world around it

This is a **policy definition, not a theorem, and it must not be labelled one.** The research content is: under what assumptions does it hold, does the implementation actually preserve it, and where does it break. Two failure modes to attack directly rather than assume away:

- **TOCTOU** — the effect changing between check and execution
- **concurrency / replay** — two mediated calls racing the same allowance

`Mediated` is the clause that makes the others meaningful, and it is the one an implementation is most likely to get wrong.

---

## 6. Milestones

Each has an acceptance criterion. No milestone is "done" without it.

### M0 — Repair the evidence base
The foundation must be sound before anything is built on it.

- κ validation of the A0–A3 classifier (265 rows, two annotators, held-out split)
- Hand-validate the escape partition on ~30 servers; report classifier recall (one true positive is known to sit in the `NONE` bucket)
- Re-run the corrected pilot; report detection and FPR with refused writes excluded
- Characterise funnel survivors vs dropouts

**Accept when:** every number in [`24`](24-calibrated-auditing-the-real-experiment.md) either survives with a stated CI or is corrected, and κ ≥ 0.6.

### M1 — Threat model and novelty gate
- Fix the threat model (§4) precisely
- **Literature check against primary sources**, per the citation quarantine in [`23`](23-frozen-direction-auditability-analyzer.md) §5: capability-based security, sandboxing/seccomp/AppArmor, CaMeL, SAFEFLOW, MCPSec, Progent, and MCP's own confirmation model
- For each: what it enforces, at what boundary, and what it does not cover

**Accept when:** a table exists naming, for every adjacent system, the specific thing this layer does that it does not — with a DOI or venue page recorded for each. **If no such thing survives the table, stop and redesign.** This gate exists to be failable.

### M2 — Mediation boundary, one domain
Filesystem, using the existing container harness.

- Contract expressed as filesystem constraints
- Enforcement at the boundary, not via a per-tool executor
- Attack suite: wrong target, extra target, payload substitution, extra invocation, silent no-op, boundary bypass, TOCTOU, concurrent replay
- Honest workflows must still complete

**Accept when:** every attack is blocked or explicitly reported UNKNOWN, honest task completion is unchanged from undefended, and at least one *deliberate bypass attempt* is documented — succeeded or failed.

### M3 — Generality
The milestone the goal lives or dies on.

- Same mechanism, no new per-tool code, against **≥10 independent real MCP servers** from the corpus
- Measure: what fraction of their effects are expressible as boundary constraints; where an adapter is unavoidable and why; integration effort per server
- Extend to the network boundary

**Accept when:** ≥10 servers are mediated with zero per-server code, or the reason each failure needed code is characterised into named categories. **A low coverage number is a publishable result, not a failure** — provided it is measured rather than estimated.

### M4 — Adaptive adversary
A defense evaluated only against attacks written before it is not evaluated.

- Adversary that knows the contract and the boundary
- Attempts: encode the effect in an unmediated channel, exhaust the allowance, race the check, cause a false block, degrade utility until the layer is disabled
- Report what succeeds

**Accept when:** at least one adaptive attack succeeds and is reported, or the search is documented well enough that its failure is informative.

### M5 — Held-out evaluation
- Servers and workflows not touched during development
- Baselines: no defense · the project's auditor · **plain container sandbox** · MCP confirmation prompts · this layer
- Metrics: unauthorized-effect rate, honest task completion, false blocks, user confirmations required, latency and call overhead, unsupported-operation rate

**Accept when:** the layer shows a benefit over a **plain sandbox** on held-out data. If it does not, the honest paper is "boundary sandboxing is already sufficient" — which is a real finding and must be reported rather than buried.

### M6 — Write-up
Claims fixed to what M0–M5 support; prevented / detected / UNKNOWN reported separately; limitations in the authors' own words.

---

## 7. What "scale" means here

Not a thousand repetitions of one wrapper. In descending order of what it buys:

1. One mechanism working across **many independent implementations** (M3)
2. **Adaptive** attacks, not only the ones we wrote first (M4)
3. **Held-out** servers (M5)
4. Corpus size — which this project already has, and which alone proves little about a defense

---

## 8. Standing rules

Carried from [`22`](22-research-diagnosis-and-10-day-plan.md) and [`23`](23-frozen-direction-auditability-analyzer.md); they survive this replan.

- **Citation quarantine.** No citation enters the paper until a primary source is opened and its identifier recorded.
- **Pre-registration.** Every evaluation milestone gets its success criterion written down before the run.
- **Instrument bugs are the default hypothesis.** Two have already been found by self-audit — suppressed detections, and the MCP error flag that made 65% of "landed attacks" writes the server had refused. Assume a third exists.
- **Report prevented / detected / UNKNOWN separately.** Never collapse them; a refusal and a compromise are opposite events that can look identical in world state.
- **No theorem labels without statements and proofs.** "Cost Observation", not "Theorem 2".

---

## 9. Immediate next step

**M0, starting with κ.** It is the only task on this program that cannot be automated: two people must label 265 tools independently. Everything else can proceed in parallel, but the headline auditability number stays contestable until this is done.

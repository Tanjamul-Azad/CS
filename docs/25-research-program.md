# RESEARCH PROGRAM — Contract-Bound Effect Mediation for Untrusted MCP Servers

Written 2026-09-10. **This is the fixed plan.** It supersedes the deadline-shaped scoping in [`24`](24-calibrated-auditing-the-real-experiment.md) §10 and [`23`](23-frozen-direction-auditability-analyzer.md) §9. Those documents assumed an eight-day horizon and cut scope to fit it; that constraint is withdrawn. The measurement work in [`21`](21-real-server-results-and-options.md), [`22`](22-research-diagnosis-and-10-day-plan.md) and [`24`](24-calibrated-auditing-the-real-experiment.md) stands unchanged and becomes this program's foundation.

Work proceeds by milestone, not by date. A milestone is done when its acceptance criteria are met, not when a week has passed.

---

## 1. Goal

> **How much of a per-call authorization can be translated into generic filesystem, network and process restrictions, such that unauthorized effects are blocked across heterogeneous untrusted MCP implementations while honest workflows still complete — and where are application-level adapters unavoidable?**

The translation problem is the research. Enforcement machinery is engineering.

An earlier draft of this document stated the goal as building a layer that "applies across heterogeneous tool implementations **without per-tool engineering**." That phrasing asserted as a capability what is in fact the open question, and the feasibility measurement in §3.1 shows the strong form of it is false. The goal above replaces it.

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
- **network** — which hosts and ports may be reached
- **process** — what may be spawned

**`src/mcpgate/contract.py` survives this change** — contracts, binding fields, and verdicts are the same idea. What changes is where the check is applied.

### 3.1 A boundary sees effects; it does not understand them

The critical limitation, and it is not a detail. A boundary observes syscalls and packets, not meaning:

| the boundary can see | it cannot thereby know |
|---|---|
| a write to an allowed path | whether the final bytes are the approved bytes; how a partial write plus rename should count |
| a connection to an allowed host | whether the mail is going to Alice or to the attacker |
| network bytes | anything inside TLS |
| activity by one process | which concurrent MCP call caused it |
| a request leaving | whether the downstream service performed the action |

Allowing `smtp.gmail.com` allows every recipient reachable through it. Kernel mechanisms do not close this: Landlock constrains filesystem paths and network ports, not recipients or payload intent.

**A first heuristic estimate** (`experiments/run_boundary_feasibility.py`, over the 10,320 write tools of the 1,216-server corpus). Read the caveat below before quoting any of it:

| | share of write tools |
|---|---|
| every argument falls in a recognised boundary category — **candidate** | **2.3%** |
| has a recognisably opaque argument — *suggests* an adapter | 54.1% |
| ... of which a boundary still narrows something | 11.9% |
| **arguments entirely outside the vocabulary** | **41.3%** |
| has an ambiguous argument (`file_id`, `email_address`) | 1.7% |
| no declared arguments | 2.0% |

**These are estimates from argument NAMES, not a validated enforceability rate and not a mathematical bound.** An earlier version of this table reported 14.8% as "fully boundary-expressible" from a predicate that only required *no recognisably opaque* argument — so a tool taking `(path, mystery_option)` counted as fully expressible on the strength of one known field and one the vocabulary did not know. That was a definition error, not a conservative estimate, and it inflated the figure roughly sixfold.

The corrected numbers err in **both** directions: an unrecognised name can hide a genuinely enforceable tool, and a recognised one can be wrong about what the argument means. With 41.3% of tools having only unclassified arguments, the vocabulary covers a minority of the real surface.

**Consequence for the program.** The honest statement is *not* "the strong hypothesis is falsified" — it is **"we cannot yet say, and the instrument that would say is not good enough."** What is established is only that a boundary observes syscalls and packets rather than meaning (the table in this section), which is an argument from mechanism, not from this measurement.

The architecture is therefore treated as **hybrid by working assumption**: boundary enforcement where it suffices, adapters where it does not, and an explicit **UNKNOWN** where neither does. A layer that silently degrades to "allowed" outside its competence would be worse than none.

Before any of these numbers is quoted, the classifier needs a **human-validated sample per category**. That is a separate audit from the A0–A3 labelling in M0; κ on auditability classes does not validate this classifier.

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

### 4.1 Deployment scope — client-controlled environments only

The layer mediates MCP servers **running inside an environment the client controls** (a local container, as in `docker/`). It cannot mediate a remote MCP server operated by a third party: that server's filesystem writes and internal API calls happen on someone else's machine and are invisible to us.

The claim is therefore: *contract-bound effect mediation for untrusted MCP servers executing in client-controlled environments.* Equivalent protection for remotely hosted servers is not claimed and cannot be, without downstream-provider cooperation or attestation.

### 4.2 Confinement and completion are different properties

Blocking cannot make a server do work. A server that performs nothing is not stopped by an allow/deny boundary, so two properties must be reported separately and never merged:

- **Confinement** — no effect occurred outside the authorization. This is what enforcement delivers.
- **Completion** — the authorized effect actually occurred. This needs independent outcome evidence.

A silent no-op is **NOT_COMPLETED** or **UNKNOWN**, never *blocked*. This is where the project's auditing work re-enters: the mediation boundary may supply trusted observations that make completion checking possible for the first time, since they come from a component the server does not control.

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

This is a **policy definition, not a theorem, and it must not be labelled one.** The research content is: under what assumptions does it hold, does the implementation actually preserve it, and where does it break.

`Mediated` is the clause that makes the others meaningful, and it is the one an implementation is most likely to get wrong. Four failure modes to attack directly rather than assume away:

- **TOCTOU** — the object or payload changing between check and use. `seccomp` user-notification is explicitly documented as vulnerable here for pointer arguments: validating what a pointer refers to and then letting the syscall proceed permits the memory to change in between. Any design that checks and then releases inherits this.
- **effect-to-call binding** — one server process serves many calls. Attributing an observed effect to *the* call that authorized it is a real problem, not bookkeeping, and background work and child processes make it worse.
- **one invocation ≠ one syscall** — an honest file save may be several writes plus a rename. `Unused(C)` therefore cannot be implemented by counting syscalls; it needs a notion of a completed logical operation.
- **bypass surface** — file descriptors held across a policy change, symlinks, renames, hard links, and concurrent access.

---

## 6. Milestones

Each has an acceptance criterion. No milestone is "done" without it.

### M0 — Repair the evidence base
The foundation must be sound before anything is built on it.

**M0a — replace `attack_landed` with observed effect. This is the most important remaining correction, because it sits in the denominator of every rate the project has published.**

`mcpmut/proxy.py` computes `attack_landed = any(p.active for p in plans)`, and `active` is true as soon as the proxy *selects a target field*. "71 landed attacks" therefore means "an argument was changed and no protocol error came back" — not that an unauthorized effect occurred. A server that ignored the argument, no-opped, or failed at the application level counts identically to one that really wrote to the attacker's path.

Every trial must record five independent fields, none derived from another:

| field | meaning |
|---|---|
| `mutation_attempted` | the proxy changed an argument |
| `protocol_error` | the server reported an error |
| `authorized_effect_observed` | the approved effect is really present |
| `unauthorized_effect_observed` | a forbidden effect is really present |
| `outcome_unknown` | the evidence does not settle it |

Decided by a **trusted observer** reading real state before and after, living outside the container the server runs in, and not reachable from it.

**The error flag cannot substitute for this, in either direction.** `experiments/run_effect_oracle.py` demonstrates both failures on controlled behaviours: of six, the old label would count 2 while 3 carry a real unauthorized effect, and one reports a protocol error *and* leaves a forbidden write behind. So the 2026-09-10 correction — excluding errored trials from the denominator — is **also wrong**, discarding a genuine compromise. Only observation is ground truth.

Unknown trials are reported, never silently dropped; dropping them is how a denominator lies.

**Accept when:** every reported attack success is backed by independent state evidence, and the unknown rate is published alongside.

**M0b — re-run the comparison on a matched denominator.** Do not compare a repaired detector against the old broken run and call the difference an improvement. Run baseline and repaired detector on the same pinned server versions and matched workflows, separating detector change from eligibility change. Report successful, failed, partial and unknown trials separately, with server-level clustering in the CIs, and keep the project's paired "tampered fires, honest silent" metric under its own name rather than presenting it as a conventional detection rate.

**M0c — classifier validation.**

- κ validation of the A0–A3 classifier (265 rows, two annotators, held-out split)
- Hand-validate the escape partition on ~30 servers; report classifier recall (one true positive is known to sit in the `NONE` bucket)
- Re-run the corrected pilot; report detection and FPR with refused writes excluded
- Characterise funnel survivors vs dropouts

**Accept when:** every number in [`24`](24-calibrated-auditing-the-real-experiment.md) either survives with a stated CI or is corrected, **and** both of the following, which are different things:

- **κ ≥ 0.6** — measures whether two humans agree with each other. It says nothing about whether the classifier is right.
- **classifier held-out precision/recall per class**, scored against the adjudicated labels on a split not used for tuning. Confidence intervals must account for clustering: tools are nested within servers and are not independent samples.

### M1 — Threat model and novelty gate
- Fix the threat model (§4) precisely
- **Literature check against primary sources**, per the citation quarantine in [`23`](23-frozen-direction-auditability-analyzer.md) §5: capability-based security, sandboxing/seccomp/AppArmor, CaMeL, SAFEFLOW, MCPSec, Progent, and MCP's own confirmation model
- For each: what it enforces, at what boundary, and what it does not cover

**Accept when:** a table exists naming, for every adjacent system, the specific thing this layer does that it does not — compared against a **named threat and a named property**, not against the system in general. Each entry carries a verified identifier: DOI, arXiv id, venue page, or official documentation. **If no such thing survives the table, stop and redesign.** This gate exists to be failable.

### M2 — Mediation boundary, one domain
Filesystem, using the existing container harness.

- Contract expressed as filesystem constraints
- Enforcement at the boundary, not via a per-tool executor
- Attack suite: wrong target, extra target, payload substitution, extra invocation, silent no-op, boundary bypass, TOCTOU, concurrent replay
- Honest workflows must still complete

**Accept when:** three separate thresholds are met, because a single "blocked or UNKNOWN" criterion is trivially passed by declaring everything UNKNOWN:

**Pre-registered thresholds, written before the run** — "three thresholds" without numbers is not a criterion:

| | threshold | rationale |
|---|---|---|
| **prevention coverage** | ≥ **90%** of attacks that produce an observed unauthorized effect are blocked | a confinement mechanism that misses one attack in five is not one |
| **UNKNOWN rate** | ≤ **20%** of scenarios | honest, but a layer that mostly declines to adjudicate is not a defense |
| **honest utility** | task completion under an honest server within a **non-inferiority margin of 5 percentage points** of undefended | "indistinguishable" needs a stated margin, or any shortfall can be argued away |

Measured on the first M2 run (`experiments/run_boundary_probe.py`, 14 scenarios): prevention 13/13 of attacks with an observable effect, UNKNOWN 1/14 = 7.1%, honest completion equal to undefended. Recorded here because the thresholds were set from the reviewer's criteria before that run was scored, not fitted to it afterwards.

Plus: at least one *deliberate bypass attempt* documented, succeeded or failed, and confinement reported separately from completion (§4.2).

### M3 — Generality
The milestone the goal lives or dies on.

- Same mechanism against **≥10 independent real MCP servers** from the corpus
- Extend to the network boundary

Zero per-server *code* is not the criterion on its own — per-server engineering migrates into configuration and the research problem survives untouched. Report all of:

| | |
|---|---|
| shared enforcement code | unchanged across servers, or not |
| policy/config effort | per server, in concrete terms |
| adapters | which servers needed an API-specific parser, and why |
| denominator | which operations are claimed supported, out of how many |
| held-out behaviour | what happens on an unseen server with no manual repair |

**Accept when:** ≥10 servers are mediated by the shared mechanism, with configuration effort reported. Failure analysis alone is a *completed analysis*, not generality — if the mechanism does not generalise, that is the finding, and it must be stated as such rather than presented as success. Whether a low coverage number is publishable depends on the strength of the analysis around it, and cannot be asserted in advance.

### M4 — Adaptive adversary
A defense evaluated only against attacks written before it is not evaluated.

- Adversary that knows the contract and the boundary
- Attempts: encode the effect in an unmediated channel, exhaust the allowance, race the check, cause a false block, degrade utility until the layer is disabled
- Report what succeeds

**Accept when:** the attack budget, the adaptive strategies tried, and the search coverage are reported. Requiring a success would be the wrong criterion — it rewards a weak defense and tempts the evaluator to stop searching once one is found. What must not happen is an unbounded search reported as "we tried hard".

### M5 — Held-out evaluation
- Servers and workflows not touched during development
- Baselines: no defense · the project's auditor · plain container sandbox · **task-specific static least-privilege sandbox** · MCP confirmation prompts · this layer
- Metrics: unauthorized-effect rate, honest task completion, false blocks, user confirmations required, latency and call overhead, unsupported-operation rate, UNKNOWN rate

The least-privilege baseline is the demanding one and must not be dropped. A plain container is an easy comparison to beat; a sandbox hand-configured per task with the minimum rights that task needs is what a careful engineer would actually deploy, and the per-call contract has to earn its complexity against that.

**Accept when:** the comparison is run and reported against both sandbox baselines. If the layer shows no benefit over static least-privilege, that outcome is reported plainly — its publishability depends on the quality of the analysis, and is not guaranteed in advance.

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

## 9. This document is not a fixed architecture

The direction is fixed; the architecture is a working hypothesis under test. §3.1 already falsified its strong form before any enforcement code was written, which is the point of putting feasibility probes ahead of implementation. Expect the same to happen again at M2 and M3, and record it when it does rather than defending the design.

## 10. Immediate next steps — in parallel

The largest uncertainty is no longer classifier agreement. It is **how faithfully a high-level authorization can be enforced at a boundary**, and §3.1 answers only the declaration-level upper bound.

1. **κ validation (M0).** Two people, 265 tools, independent. The only task here that cannot be automated, and the headline auditability number stays contestable until it is done.
2. **M1 novelty gate**, in parallel. It can stop the whole program, so it should run early rather than after months of building.
3. **Boundary feasibility, one real server.** Take a single filesystem MCP server from the corpus, put a real mediation boundary around it, and find out what breaks: effect-to-call binding, partial writes, renames, background work. §3.1 measured what declarations *say*; this measures what enforcement actually survives — and it is the cheapest way to find the next false assumption.

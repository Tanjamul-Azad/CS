# Master Research Plan

**Group 13** — Md. Tanzamul Azad (0112230863), Jahidul Islam (0112230654)
**Status:** Active · Started 2026-08-13
**Working title:** *The Price of a Lie: Auditing Untrusted Tool Servers Without Their Cooperation*

---

## 1. The one-sentence thesis

> Agent protocols such as MCP establish trust over a tool's **declaration**, but the security-relevant object is its **implementation**. A passive client cannot close that gap — we prove it. An *active* client can, not by detecting compromise outright, but by forcing the attacker to maintain a consistent simulated world, and we show that burden is measurable, that it rises sharply with a tool's relation degree, and that every documented real-world MCP compromise falls far below it.

**Design constraint that shapes everything:** the client gets **no cooperation** — not from the server, not from downstream providers, not from any independent channel. Anything requiring signed receipts or third-party attestation is out of scope by construction, because it will not be deployed. See [`11-runtime-validation-design.md`](11-runtime-validation-design.md).

## 2. Why this framing, and not the previous two

Two separate research tracks already exist in this project. Neither is a top-venue paper on its own. Together, under the right frame, they are.

| | Track A (`exp/`, `literature review paper/`) | Track B (`Paper work/Initials/`) |
|---|---|---|
| Gap claimed | Authorization checks *which* tool, not whether the **arguments** were attacker-shaped | Approval checks *what the tool declares*, not what it **does** |
| Attack surface | Input side of an authorized call | Output side of an approved call |
| Evidence | AgentDojo banking, gpt-oss-120b, **ASR 34.0%**, N=144, control 0.0% | MCP banking benchmark, hash pinning blocks 100% of metadata mutations, ~0% of behavior-only |
| Verdict standalone | Solid reproduction, but it reproduces Progent's known baseline — **not a new result** | Near-tautological — a hash over fields *X* cannot detect a change outside *X* |

**The unification.** Both are the same structural failure: a trust decision made at time *T* over a **proxy** (tool identity, tool declaration), while the object that actually matters is the **execution** at time *T+k*. Track A is that failure on the input channel. Track B is that failure on the output channel. An approved tool call is compromised at *both ends*, and identity-based trust covers neither.

That is a complete story. It is also, critically, a story with a **theoretical core** (§3) that neither track has on its own — and the theoretical core is what makes it publishable at a security venue rather than a workshop.

## 3. The theoretical core (this is the paper's spine)

The naive fix for Track B is: *compare what the tool returned against what was requested.* This is what the previous proposal planned to build.

**It does not work, and the reason it does not work is the paper.**

If the server is compromised, it controls its own responses. A server that silently transfers to Bob can simply *reply* `"Transferred $100 to Alice"`. The client's validator sees a perfect match. Any reviewer at a security venue kills the paper on this in the first paragraph of their review.

So the honest research question is not "can we validate responses?" but:

> **What, if anything, can a client verify about tool execution when the server is untrusted?**

This is a classical security question with a classical answer shape: an **impossibility result** plus a **characterization of the tractable sub-cases**. See [`05-verifiability-taxonomy.md`](05-verifiability-taxonomy.md).

Sketch:
- **Theorem (informal).** For a tool whose effects are not observable through a channel independent of the server, no client-side monitor can distinguish an honest server from a behavior-mutated one. Proof by indistinguishability: the mutated server's transcript is a permitted transcript of the honest server.
- **Corollary.** Every purely response-inspecting defense — including the one we ourselves proposed — has attack success rate → 100% against an adaptive adversary. We will *demonstrate this empirically on our own defense*, which is the most credible thing we can do.
- **The constructive half.** Not all tools are opaque. Some effects *are* independently observable, some are re-computable client-side, some can be made self-certifying. Partition the tool space by verifiability class; build the right defense per class; escalate to policy for the rest.

This turns a weak claim ("we built a validator") into a strong one ("we established the boundary, showed where defense is possible and impossible, and built what is possible").

## 4. Contributions as they will appear in the paper

**C1 — Execution Integrity framework.** Formal decomposition of tool-call trust into *argument integrity* (I) and *effect integrity* (E). We position 24 prior defenses in this space and show the systematically empty region. [`02-gap-analysis.md`]

**C2 — Theorem 1 (transcript indistinguishability).** No *passive* client-side monitor can detect an adversary that forges honest responses. Proved, and confirmed empirically against our own earlier design. [`05-verifiability-taxonomy.md`]

**C3 — Theorem 2 (the cost of consistency) + MBA.** The impossibility is escaped by making the client *active*. Metamorphic relations derived automatically from tool declarations force the adversary into maintaining a consistent shadow world. **Zero cooperation required from anyone.** [`11-runtime-validation-design.md`]

**C4 — Auditability taxonomy A0–A3 + classifier.** Tools classified by *relation degree*, a client-computable property. A0 (degree 0) is undetectable at any budget.

**C5 — Ecosystem measurement.** Apply C4 to real MCP servers. Headline: *what fraction of real deployed tools have relation degree 0?* Makes the problem concrete rather than toy. [`06-dataset-plan.md`]

**C6 — Consistency cost curve.** We *build* the consistency-maintaining adversary and report what it cost — shadow-state size, LOC, per-call overhead. The cost curve **is** the security argument. Already demonstrated: 3 → 9 → 17 LOC across three defense layers (`experiments/demo_mba.py`).

**C7 — MCP-MutBench.** Released benchmark: harness, mutation engine, adversary ladder T0–T3, out-of-band ground-truth oracle, relation engine.

## 5. What makes this non-generic

The user requirement was explicitly *"contribution to solve real problem, not generic one."* The three things that make this concrete rather than hand-wavy:

1. **The measurement is on real deployed servers**, not a toy. If the answer is "61% of real MCP tools have opaque effects," that is a fact about the world that nobody has established.
2. **The impossibility result is falsifiable and specific.** It names exactly which tools cannot be defended and why. It is not "security is hard."
3. **The defense is honest about its ceiling.** We show our own defense failing against the adaptive adversary in exactly the cases theory predicts. Reviewers trust papers that attack themselves.

## 6. Document map

| File | Contents |
|---|---|
| [`01-literature-review.md`](01-literature-review.md) | Consolidated review, both tracks, 24 papers, positioned |
| [`02-gap-analysis.md`](02-gap-analysis.md) | The I×E grid, the empty quadrant, per-paper limitation evidence |
| [`03-novelty-contributions.md`](03-novelty-contributions.md) | Novelty defense, anticipated reviewer attacks + rebuttals |
| [`04-threat-model.md`](04-threat-model.md) | Adversary capabilities, naive vs adaptive, scope boundaries |
| [`05-verifiability-taxonomy.md`](05-verifiability-taxonomy.md) | **Theory core.** V0–V3, impossibility theorem, per-class defenses |
| [`06-dataset-plan.md`](06-dataset-plan.md) | D1/D2/D3, the no-existing-dataset strategy, labeling protocol |
| [`07-experiment-plan.md`](07-experiment-plan.md) | RQs, conditions, models, N, statistics, ablations |
| [`08-figures-plan.md`](08-figures-plan.md) | Every figure and table, with the claim each one supports |
| [`09-venue-timeline.md`](09-venue-timeline.md) | Target venues, deadlines, milestone schedule |
| [`10-implementation-notes.md`](10-implementation-notes.md) | Code architecture, how to run everything |
| [`11-runtime-validation-design.md`](11-runtime-validation-design.md) | **MBA — the zero-cooperation defense.** Read after 05 |
| [`12-intellectual-lineage.md`](12-intellectual-lineage.md) | The 11 fields we inherit from and the assumption each one loses |

## 7. Current state

- [x] Repo connected, author configured
- [x] Prior artifacts inventoried (4 proposal drafts, 2 lit reviews, AgentDojo experiment, 7-slide deck)
- [x] Research plan and framing
- [ ] Literature review consolidation
- [ ] Taxonomy formalization + theorem
- [ ] MCP-MutBench harness
- [ ] Registry harvest + classifier
- [ ] Experiments
- [ ] Paper draft

## 8. Standing constraints

- **Author:** Tanjamul-Azad `<i.m.tanjamul@gmail.com>` only, on all commits.
- **No secrets in the repo.** The prior notebook leaked two Groq keys; both must be revoked. All keys via `.env`, which is gitignored.
- **Every claim in the paper traces to a script in `experiments/` that regenerates it.** No hand-typed numbers.

# Adversarial Review — reading our own paper as a hostile PC member

Written as a USENIX Security reviewer who wants to reject. Every objection below is one a competent reviewer would actually raise, ordered by how likely it is to kill the paper.

The point is not to be pessimistic. It is that each of these is **fixable**, and knowing which ones are fatal tells us what to build. [`20-plan-to-submission.md`](20-plan-to-submission.md) is the response.

**Verdict as of today: Reject.** Not because the idea is weak — the measurement is genuinely good — but because the defense evaluation cannot survive contact with R1–R3.

---

## Severity key

| | |
|---|---|
| 🔴 **Fatal** | Reviewer rejects on this alone |
| 🟠 **Major** | Forces a "major revision" at best |
| 🟡 **Minor** | Costs credibility, easily fixed |

---

## 🔴 R1 — Everything you evaluate on, you wrote

> *"The authors evaluate a defense they designed, against adversaries they designed, on four tool servers they wrote, using baselines they implemented. The only external artifact in the entire evaluation is a single filesystem server used once. This is self-evaluation."*

This is the single most likely rejection reason.

**What makes it worse:** the `hash-pin` baseline scores 0% *by construction* — every adversary in the benchmark leaves the declaration untouched, so the comparison is rigged by design. We say this openly, which helps, but a reviewer reads a table where our method scores 100% and every baseline scores 0% and becomes suspicious rather than convinced.

**What is actually needed:** detection measured on **real MCP servers we did not write**, at n large enough to report a distribution rather than an anecdote.

---

## 🔴 R2 — You cite six defenses and run none of them

`references.bib` contains Progent, ETDI, MCP-Guard, MELON, Task Shield, IPIGuard, AgentDojo. The evaluation compares against `none`, `hash-pin`, and `response-validation` — all three written by us.

> *"The related work section demonstrates the authors know the field. The evaluation demonstrates they did not compare against it."*

**Counter-argument we could make:** those defenses target *input* integrity (prompt injection, privilege control), not *effect* integrity, so they are not competitors. **This is actually true and is our gap argument.** But it must be *demonstrated*, not asserted — run Progent against our adversary ladder and show it scores 0% because it is solving a different problem. A baseline that fails for a reason we explain is far stronger than a baseline we omit.

---

## 🔴 R3 — Your central empirical claim rests on n=1

The claim "real-world MCP compromises are 3-LOC-class patches that maintain no shadow state" appears in **six documents** and in the abstract. It is the bridge from "our defense catches cheap attackers" to "our defense matters."

Its entire evidentiary basis is the Postmark BCC incident, cited from memory, not verified against a primary source, and not in the bibliography as such.

> *"The paper's practical relevance rests on a single anecdote."*

**What is needed:** a documented incident corpus — 10–15 real agent/tool-supply-chain compromises, each classified by what the attacker actually had to maintain. If the distribution really is concentrated at the cheap end, that is a *result*. If it is not, we need to know before a reviewer tells us.

---

## 🟠 R4 — "A0 = undetectable at any budget" is a claim about your instrument, not the world

This is the sharpest *conceptual* objection and we have not addressed it anywhere.

We define six relation classes R1–R6, derive them, and call a tool with degree 0 "undetectable at any audit budget." But that only follows if **R1–R6 are exhaustive** — if no other metamorphic relation could exist for that tool.

We never argue completeness. So the honest claim is:

> ~~"56.5% of tools are undetectable at any budget"~~
> **"56.5% of tools admit no relation derivable by our method"**

Those are very different sentences, and the second is much weaker.

**Options:** (a) argue R1–R6 completeness w.r.t. some formal class of properties, (b) soften every claim to be instrument-relative, (c) show empirically that an independent annotator with no relation vocabulary also finds nothing checkable for A0 tools. (c) is achievable — it is what the κ `check` column already asks for, and we should analyse it explicitly rather than only using it for agreement.

---

## 🟠 R5 — Theorem 2 is not a theorem

Theorem 1 is a real (if short) impossibility argument. Theorem 2 — "the cost of consistency" — is currently three hand-written adversaries at 3, 9, and 17 lines, in one domain family, with LOC counted by the person who wrote them.

> *"Theorem 2 has no statement, no assumptions, and no proof. It is a table of three numbers the authors chose."*

**Needed:** either a genuine lower bound (evading relation set R requires shadow state of size ≥ f(R)) or an honest downgrade from "Theorem 2" to "Observation" / "Cost Model", with the empirical curve carrying the weight. **A reviewer will respect the downgrade; they will not respect the mislabel.**

---

## 🟠 R6 — LLM evaluation reports 320 episodes and has ~32 data points

Zero within-cell variance at temperature 0 *and* at 0.7 with five paraphrasings. Every episode is exactly 2 steps. One model.

We already state this. Stating a weakness does not remove it.

> *"The LLM experiment establishes that a 2-step task is deterministic. It does not establish that the defense works under realistic agent behaviour."*

**Needed:** multiple models (including a weaker one, where tool-selection errors actually occur), multi-step tasks, servers with 15+ tools where the agent must choose, and distractor tools.

---

## 🟠 R7 — Classifier unvalidated (the known blocker)

The headline 56.5% comes from a heuristic — verb lists, noun overlap, field matching — never scored against human judgment. κ is generated but unrun.

Compounding it: the write-verb list was **expanded after looking at corpus data** (`purge_sessions`, `prune_tools` were added because we saw them). That is fitting the instrument to the sample. Needs a held-out split: tune on one half, report on the other.

---

## 🟡 R8 — Probe-aware result is one domain

The most interesting adversarial result in the paper (detection → 0, deterrence total, decoy equilibrium) is measured only on banking.

## 🟡 R9 — Sampling frame is GitHub-only

Stated as a threat, but never bounded. How many MCP servers ship *only* via npm/PyPI? That number is obtainable — query the registries — and converts an unbounded threat into a quantified one.

## 🟡 R10 — Decoy auditing's cost is asserted, not measured

We recommend decoy snapshots on every call and note overhead "approaches the always-audit case." Approaches it by how much? The whole point of a 25% budget is cost, and the decoy may erase that saving entirely.

## 🟡 R11 — Theorem 1 may read as folklore

"You cannot detect what you cannot observe" is intuitive. The theorem needs framing that makes clear what is *non-obvious*: that the client's own approval authority is the resource that escapes it, and that the escape has a measurable price. Otherwise a reviewer files it under "formalises the obvious."

---

## What a reviewer would praise

Worth knowing, because these are what we must not damage while fixing the rest.

- **The ecosystem measurement is genuinely new.** 5,397 tools, 295 servers, and a distribution nobody has published.
- **Official 9% vs community 57%** is a methodological critique of the whole subfield, not just a number.
- **Breaking our own defense twice** — 20–86% FPR under concurrency, and detection → 0 against a probe-aware adversary — and reporting both. Reviewers trust authors who do this.
- **Three concrete protocol recommendations** falling out of measurement.
- **The artifact runs**, has tests, and reproduces.

---

## Honest scoring

| Component | Grade | Why |
|---|---|---|
| Problem framing | **A** | TOCTOU framing is correct and clean |
| Ecosystem measurement | **A−** | strong; needs κ |
| Theorem 1 | **B** | correct, needs framing against folklore |
| Theorem 2 | **D** | not a theorem |
| MBA design | **B+** | genuinely novel synthesis; safety property is a real contribution |
| **Evaluation** | **D** | self-evaluated, no real baselines, pilot scale |
| Honesty / self-criticism | **A** | consistently reports own failures |
| Artifact | **B+** | runs, tested, reproducible |

**Overall: reject today; accept-able after the evaluation is rebuilt.** The measurement half would already survive as a standalone measurement paper.

# Novelty, Contributions, and Reviewer Defense

---

## 1. The novelty claim, stated so it can be attacked

> **Novel claim:** Whether a post-approval tool mutation is detectable at all is a property of the *tool*, not of the *defense*. We identify that property (opacity), prove it determines detectability, build a classifier for it, and measure its prevalence in the deployed MCP ecosystem.

Nothing in the literature asks whether detection is *possible*. Every paper assumes it is and proposes a mechanism. That assumption is false for a measurable fraction of real tools, and that fraction is the paper.

## 2. Novelty audit — what is genuinely new vs. inherited

| Element | New? | Honest assessment |
|---|---|---|
| "Rug pull exists" | ❌ | Invariant Labs, 2025 |
| "Metadata ≠ behavioral integrity" | ❌ | Near-definitional; **setup, not contribution** |
| Hash pinning blocks metadata mutations | ❌ | Expected; we supply the first number, which is minor |
| Behavior-only mutation bypasses hash pinning | ⚠️ | True but near-tautological. **Cannot be the headline** — this was the previous draft's mistake |
| **Adaptive adversary A\* defeats response validation** | ✅ | Not evaluated anywhere in MCP literature |
| **Theorem 1 (impossibility)** | ✅ | Not stated anywhere |
| **V0–V3 verifiability taxonomy** | ✅ | New construct |
| **Classifier from declarations** | ✅ | New instrument |
| **Ecosystem measurement of opacity** | ✅ | **Strongest contribution.** New fact about the world |
| **Pseudo-V2 (illusory corroboration)** | ✅ | Potentially the most surprising finding |
| Class-aware defense (BIM) | ✅ | Novel composition; components individually unsurprising |
| I×E unification of two literatures | ✅ | New framing, moderate weight |

**Reading:** the paper's weight sits on Theorem 1 + the measurement + the adaptive adversary. If those three hold, it is a strong submission. Everything the previous drafts led with is *setup*.

## 3. Anticipated reviewer attacks and rebuttals

**R1: "Theorem 1 is obvious."**
Partly conceded — it is easy once stated. But (a) the field is *actively recommending* defenses it invalidates (MCP-38 → ETDI → hash pinning, an unevaluated citation chain); (b) its value is the *condition* it isolates — opacity — which is measurable and which we measure; (c) obvious-in-hindsight impossibility results that redirect a literature are a recognized contribution type. We will state it plainly and let the measurement carry the weight.

**R2: "This is just server compromise, not an MCP problem."**
Ordinary APIs authenticate every request and are periodically reviewed by a human reading logs. MCP replaces per-call review with **one-time approval followed by standing, unreviewed, machine-speed trust**. That specific pattern converts an ordinary backend compromise into a silent durable one. We also measure how long approvals persist in practice.

**R3: "Your benchmark is synthetic."**
Conceded for D2, and that is deliberate — ground truth about a hidden implementation is only obtainable in a harness we control. This is exactly why the paper pairs D2 with **D1, a measurement of real declarations**, and with **D3, a public benchmark**. Three legs, different weaknesses.

**R4: "The defense doesn't solve V0."**
Correct, and Theorem 1 says nothing can. Any paper claiming to solve V0 client-side is wrong. We state this in the abstract.

**R5: "Only small/open models."**
Being fixed: ≥3 models including at least one frontier commercial model. See [`07-experiment-plan.md`](07-experiment-plan.md).

**R6: "Where is the comparison to existing defenses?"**
We implement hash pinning (ETDI's core mechanism) and a MELON/Task-Shield-style intent-match validator as baselines, not just "no defense." This was a real hole in the previous plan.

## 4. Contribution ledger

| ID | Contribution | Type | Evidence artifact | Risk |
|---|---|---|---|---|
| C1 | Execution-integrity framework (I×E) | Conceptual | Fig. 1, Table 1 | Low |
| C2 | Impossibility theorem | Theoretical | §3 + empirical confirmation | Med (R1) |
| C3 | V0–V3 taxonomy + classifier | Methodological | κ, per-class P/R | Med (κ) |
| C4 | **Ecosystem measurement** | Empirical | Fig. 4, headline % | Low |
| C5 | BIM class-aware defense | Systems | Table 4, ablation | Low |
| C6 | MCP-MutBench | Artifact | Public release | Low |

## 5. The abstract, drafted early to force clarity

> Agent protocols such as the Model Context Protocol let a user approve a tool once and thereafter allow an autonomous agent to invoke it without further review. Approval binds trust to a tool's *declaration* — its name, description, and schema — while the security-relevant object is its *implementation*. We show this gap is not merely unaddressed but, for a large class of tools, unaddressable: we prove that no client-side monitor can distinguish an honest server from one that performs a malicious effect while returning an honest response, whenever the tool's effect is not observable through an independent channel. We introduce a verifiability taxonomy that partitions tools by whether such a channel exists, build a classifier that assigns classes from declarations alone, and apply it to N tools harvested from M public MCP servers, finding that **X%** are provably undefendable client-side — and that a further **Y%** appear verifiable but are corroborated only by tools on the same server, an independence failure that collapses them into the undefendable class. We then build BIM, a class-aware runtime monitor, and evaluate it against both naive and adaptive adversaries across four tool domains and three models. BIM detects behavior-only mutation in the verifiable classes at high rates, and — as the theory requires — not at all in the opaque class, where we argue the only remaining defenses are protocol-level: expiring approval, receipt attestation, and consequence-scaled confirmation.

## 6. What must be true for this to land

Falsifiable preconditions. If these fail, we adapt (see [`06-dataset-plan.md`](06-dataset-plan.md) §5) rather than force the story.

1. A non-trivial fraction of real MCP tools are V0. *If nearly all are verifiable, the paper inverts to a constructive protocol paper — still publishable.*
2. A\* defeats response validation empirically as Theorem 1 predicts. *Very likely; it is near-definitional.*
3. BIM achieves meaningfully better detection on V1–V3 than hash pinning. *Main engineering risk.*
4. The classifier reaches usable agreement. *Main methodological risk; §4 of dataset plan has the fallback.*

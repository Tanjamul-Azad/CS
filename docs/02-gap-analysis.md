# Gap Analysis

> Method: we do not list "things nobody did." We construct a coordinate system in which the field's coverage can be *seen*, then show a region that is empty for structural reasons.

---

## 1. The coordinate system

A tool call is trusted along two independent axes:

- **I — Argument integrity.** Were the arguments `a` chosen by the user's intent, or shaped by untrusted content that entered the agent's context?
- **E — Effect integrity.** Did the server's implementation `f` produce the effect its declaration promises, or a different one?

These are genuinely independent. An attack can violate one without the other:

| | Attack | Real incident |
|---|---|---|
| **I violated, E intact** | Indirect prompt injection redirects a transfer; the banking server is honest and does exactly what it was told | AgentDojo `important_instructions`; our own 34.0% ASR reproduction |
| **I intact, E violated** | Agent requests exactly the right transfer; the server silently redirects it | Postmark MCP BCC leak; post-approval tool poisoning CVE |
| **Both** | Injection picks the argument *and* a compromised server rewrites the effect | Not yet studied — compounding case |

## 2. Where the field sits

| Defense | Covers I | Covers E | Stated limitation (their words, not ours) |
|---|---|---|---|
| Progent | ● policy on args | ○ | "security depends on the model writing the policy" |
| ScopeGate | ● arg allowlist | ○ | self-described as "containment, not a full defense" |
| MiniScope | ◐ scope-level | ○ | "no protection once inside a granted scope" |
| SEAgent | ◐ flow labels | ○ | static labels; cannot react mid-session |
| Risk-Aware Causal Gating | ◐ tool visibility | ○ | silent on what happens after authorization |
| Prompt Flow Integrity | ● trusted/untrusted split | ○ | design + engineering overhead |
| Tracked Capabilities | ● type-level | ○ | guarantee breaks at the external-process boundary |
| AGrail | ◐ behavioral | ○ | degrades sharply on weaker models |
| IPIGuard | ◐ plan-fixed | ○ | no protection against text-only attacks |
| MELON / Task Shield | ● intent match | ○ | "limited to the tool-call layer" |
| ToolSafe / ToolSafety | ◐ step guardrail | ○ | poor cross-lingual / jailbreak generalization |
| **ETDI** | ○ | ◐ *declaration only* | **no experiment anywhere in the paper** |
| **MCP-38** | ○ | ◐ *recommends hash pinning* | taxonomy only; never implements |
| **Zero Trust Registry** | ○ | ◐ *identity only* | "does not cover a tool compromised after approval" |
| **MCP-Guard** | ◐ | ◐ *declaration content* | no per-category breakdown; rug-pull result not isolated |
| Invariant Labs | ○ | ○ demonstration | no defense proposed |
| Hou et al. | ○ | ○ taxonomy | ASR measurement explicitly out of scope |
| Song et al. | ● measured | ○ | **rug pull deliberately excluded** from quantitative results |
| MCPXKit | ● measured | ◐ measured, undefended | no defense evaluated |

● covers · ◐ partial · ○ does not cover

## 3. The three findings that fall out of the grid

### Finding 1 — The E column is nearly empty, and what is in it is all *declaration*-level

Every entry with any E coverage — ETDI, MCP-38, Zero Trust Registry, MCP-Guard — verifies the **declaration** τ. Not one verifies the **implementation** f. This is not an oversight; it is the only thing a client can cheaply check, so the field checked it and moved on.

### Finding 2 — The E-side defenses are recommended but unevaluated

- ETDI proposes signed versioned definitions and reports **no experiment, no dataset, no ASR** anywhere.
- MCP-38 recommends hash pinning, **citing ETDI**, and never implements it.
- Zero Trust Registry points at the same idea and **explicitly disclaims** post-approval compromise.
- MCP-Guard has real numbers but rug pull is 1 of 11 categories and is **never broken out**.

So the field's consensus fix for post-approval mutation rests on a citation chain in which **no link contains an experiment**. Our preliminary result is the first number attached to it.

### Finding 3 — The empty quadrant is empty for a *reason*, and nobody has named the reason

Here is the part that turns a gap list into a research contribution.

Nobody defends E at the implementation level because — for a large class of tools — **it is impossible to do so client-side** (Theorem 1, [`05-verifiability-taxonomy.md`](05-verifiability-taxonomy.md)). The field has been implicitly routing around an impossibility result that has never been stated.

Once stated, it has consequences the field is currently getting wrong:
- Hash pinning is being recommended as *the* fix for rug pulls. It is not a fix; it addresses a strictly weaker adversary than the one the threat model describes.
- Response-validation defenses (including the one this project previously planned) are **worthless against an adversary that costs one line of code to build**.
- The right question is not "how do we validate harder" but "which tools *can* be validated at all" — and that question has never been asked, so the answer has never been measured.

## 4. The gap, stated precisely

> Existing agent-security work secures the **input** channel of an authorized tool call (I) and, for the **output** channel (E), secures only the tool's *declaration*. No work verifies the tool's *implementation*, no work establishes whether such verification is possible, and no work measures what fraction of real deployed tools admit it. As a result the field's consensus defense for post-approval mutation is recommended without evaluation and fails completely against a trivial adaptive adversary.

## 5. What we do about each part

| Gap element | Our response | Contribution |
|---|---|---|
| I and E never unified | Execution-integrity framework; the I×E grid above | C1 |
| Verification possibility never established | Theorem 1 | C2 |
| "Which tools are verifiable" never asked | V0–V3 taxonomy + classifier | C3 |
| Never measured on real systems | Registry harvest + classification | C4 |
| Consensus defense unevaluated | Evaluate hash pinning **and our own defense** against naive + adaptive adversaries | C5 |
| No reusable artifact | MCP-MutBench | C6 |

## 6. Honest self-assessment of the gap's strength

**Strong:** Findings 2 and 3, and C4. A measured claim about the real ecosystem, plus a named impossibility, is genuinely new.

**Weak if left alone:** Finding 1 and the bare `Metadata ≠ Behavioral` claim. Near-definitional. These are *setup*, not contribution, and the paper must not present them as the headline — which is exactly what the previous draft did.

**The risk to manage:** a reviewer saying *"Theorem 1 is obvious."* Rebuttal in [`03-novelty-contributions.md`](03-novelty-contributions.md) §3.

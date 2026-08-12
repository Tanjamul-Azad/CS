# Literature Review

> Consolidates the project's two prior reviews (MCP security, 8 papers; agent access control & guardrails, 16 papers) into one body organized by **what each defense actually verifies**, not by what it calls itself. 24 unique works.

---

## 1. Organizing principle

Every defense here answers one of four questions. The organization *is* the argument: three of the four are well populated and the fourth is empty.

| | Question the defense answers | §  |
|---|---|---|
| **Q1** | *May the agent use this tool at all?* | 2 |
| **Q2** | *Is this specific call, with these arguments, legitimate?* | 3 |
| **Q3** | *Is the tool's declaration what it was at approval?* | 4 |
| **Q4** | ***Is the tool's implementation what it was at approval?*** | **5 — empty** |

---

## 2. Q1 — Capability and access control

**Progent** (Shi et al., arXiv:2504.11703) is the reference point. Every tool is wrapped in a policy in a small rule language, LLM-generated from the user request and updated as context arrives; blocked calls get a fallback so the agent does not stall. Pushes ASR near zero on AgentDojo/ASB/EHRAgent. **Limitation (theirs):** security rests on the model writing the policy, which the injected text may itself influence. *Our AgentDojo baseline reproduces Progent's no-defense condition — 34.0% vs their 39.9–41.2%.*

**SEAgent / Taming** (Ji et al., arXiv:2601.11893) lifts this to session scope with MAC-style labels over a live information-flow graph; catches multi-agent confused-deputy cases. **Limitation:** labels are static once assigned — no mid-session reaction, and defaults to allow when no rule matches.

**MiniScope** (Zhu et al., arXiv:2512.11147) computes the minimal permission set as an optimization rather than trusting model reasoning. **Limitation (theirs):** "no protection once inside a granted scope."

**Risk-Aware Causal Gating** (Iyer & Babu, arXiv:2606.13884) gates which tools are even visible by risk and necessity. **Limitation:** guarantee rests entirely on the authorizing signal being unforgeable; silent about post-authorization.

**Securing Agents With Tracked Capabilities** (Odersky et al., ACM AIAS 2026) is the only work here with a real mathematical guarantee — capability tracking in the type system makes leaking a secret a type error. **Limitation:** holds only inside its controlled environment; breaks at the external-process boundary — which is exactly where MCP lives.

**A Vision for Access Control** (Li et al., arXiv:2510.11108) argues allow/deny was never built for agents; position paper, no system.

**Over-Privileged Tool Selection** (Yang et al., arXiv:2606.20023) — across 11 models, agents routinely reach for more powerful tools than needed, especially after a failure. Training shifts but does not close it. Best empirical evidence that Q1 is a real problem.

## 3. Q2 — Argument-level and behavioral checking

**ScopeGate / Capability Gates Are Not Authorization** (Mellafe Zuvic, arXiv:2606.28679) makes the sharpest conceptual point in this literature: *"can the agent see this tool"* and *"is this call with these values allowed"* are different questions, routinely conflated. Argument allowlist checked immediately before execution, default deny. **Limitation (theirs):** self-described containment, not a cure.

**Prompt Flow Integrity** (Kim et al., arXiv:2503.15547) splits the agent into trusted (handles user request) and untrusted (processes tool data) halves; only the trusted half holds full tools. **Limitation:** substantial design overhead.

**AGrail** (Luo et al., ACL 2025) generates adaptive safety checks at test time via two cooperating models. **Limitation:** degrades sharply on weaker models.

**IPIGuard** (EMNLP 2025) fixes a tool-dependency plan the agent cannot deviate from. **Limitation:** no protection against text-only attacks.

**MELON** (ICML 2025) and **The Task Shield** (ACL 2025) both check that a tool call remains consistent with the user's actual task. **Limitation (MELON's own):** "limited to the tool-call layer."

**ToolSafety** (EMNLP 2025) and **ToolSafe** (arXiv:2601.10156) take the data/guardrail route — fine-tuning on harm examples, and step-level guardrails with corrective feedback. **Limitations:** weak cross-lingual and jailbreak generalization; latency and token cost.

**Causal Influence Prompting** (Findings ACL 2025) has the agent build a running risk map. **Limitation:** collapses if the model is already manipulated — the map inherits the compromised reasoning.

> **Pattern across §2–3:** defenses either fix labels once and never revisit them (SEAgent, Causal Gating), or ask a possibly-compromised model to police itself (Progent, AGrail, Causal Influence). Both patterns concern the **input** side of a call. None looks at what the server *did*.

## 4. Q3 — Declaration integrity (MCP-specific)

**Invariant Labs** (2025) named the class: tool poisoning, rug pull, shadowing, with working PoC. Demonstration only; no defense.

**Hou et al.** (ACM TOSEM 2026) gives the field's most complete threat map — lifecycle taxonomy, 16 scenarios, 4 attacker types. **Explicitly** leaves ASR measurement to future work.

**Song et al.** (arXiv:2506.02040) is the first genuinely empirical MCP study: real malicious server uploaded to three marketplaces, 20-user study, 5 LLMs, ~66% average ASR. **Critically: rug pull was deliberately excluded** from quantitative results, on a stated-but-untested assumption that it behaves like the other attack types.

**MCPXKit** (Guo et al., arXiv:2508.12538) — 31 attacks, reusable framework, reports ~80% rug-pull ASR against an undefended agent. **No defense evaluated.**

**MCP-38** (Shen et al., arXiv:2603.18063) — 38-category taxonomy mapped to OWASP/STRIDE. Recommends hash pinning, **citing ETDI**. Never implements it.

**ETDI** (Bhatt et al., arXiv:2506.01333) — signed versioned tool definitions, OAuth identity, runtime policy engine. **No experiment, no dataset, no ASR anywhere in the paper.**

**Zero Trust Registry** (Narajala et al., arXiv:2504.19951) — central registry, admin-approved listings, short-lived credentials. **Explicitly disclaims** covering a tool compromised after approval.

**MCP-Guard** (Xing et al., ACL 2026 Findings) — three-stage pipeline (static filter → neural classifier → LLM arbitrator), ~90% aggregate accuracy. **Rug pull is 1 of 11 categories and is never broken out.**

> **The citation chain.** MCP-38 recommends hash pinning → cites ETDI → ETDI reports no experiment. The field's consensus fix for post-approval mutation rests on a chain in which **no link contains an evaluation.** Our preliminary result is the first number attached to it.

## 5. Q4 — Implementation integrity: the empty section

**No paper in this review verifies that a tool's implementation is unchanged since approval.**

Not an oversight. §4's defenses all verify the *declaration* because that is the only object MCP exposes cheaply. The implementation is behind the server boundary and the client's only window onto it is a response the server itself authors.

The field has been routing around an impossibility result that has never been stated. Stating it, isolating the condition under which it bites, and measuring how often that condition holds in the real ecosystem is this paper — see [`05-verifiability-taxonomy.md`](05-verifiability-taxonomy.md).

## 6. Closest related work outside these groups

- **AgentDojo** — the benchmark; supplies our I-axis evidence and D3.
- **Software supply chain / TUF / Sigstore** — signed artifacts and expiring trust. Relevant analogy: they solve *artifact* integrity (our Q3) and likewise cannot attest *runtime behavior* of a remote service. Worth a paragraph: MCP is repeating a solved-then-unsolved arc from package management.
- **Remote attestation / TEEs** — the "real" answer to Q4, at a deployment cost nobody in the MCP ecosystem will pay today. Positions our V3 receipt scheme as the pragmatic middle.
- **Byzantine fault tolerance / N-version programming** — the theoretical ancestor of our V2 cross-verification, and the source of the independence requirement whose violation we call pseudo-V2.

## 7. Master table

| # | Work | Venue | Q | What it verifies | Stated limitation |
|---|---|---|---|---|---|
| 1 | Progent | arXiv 2504.11703 | Q1/Q2 | policy over args | policy-writing model is attackable |
| 2 | SEAgent/Taming | arXiv 2601.11893 | Q1 | flow labels | static labels, allow-by-default |
| 3 | MiniScope | arXiv 2512.11147 | Q1 | minimal scope | blind inside a scope |
| 4 | ScopeGate | arXiv 2606.28679 | Q2 | arg allowlist | containment only |
| 5 | Vision for AC | arXiv 2510.11108 | Q1 | — | position paper |
| 6 | Tracked Capabilities | ACM AIAS 2026 | Q1 | type-level flow | breaks at external process |
| 7 | Risk-Aware Causal Gating | arXiv 2606.13884 | Q1 | tool visibility | needs unforgeable signal |
| 8 | Over-Privileged Selection | arXiv 2606.20023 | — | (measurement) | training doesn't close it |
| 9 | Prompt Flow Integrity | arXiv 2503.15547 | Q2 | trust split | engineering overhead |
| 10 | AGrail | ACL 2025 | Q2 | adaptive checks | weak models degrade |
| 11 | IPIGuard | EMNLP 2025 | Q2 | fixed plan | text-only attacks |
| 12 | ToolSafety | EMNLP 2025 | Q2 | tuned model | generalization |
| 13 | Causal Influence | Findings ACL 2025 | Q2 | risk map | compromised reasoning |
| 14 | ToolSafe | arXiv 2601.10156 | Q2 | step guardrail | latency/tokens |
| 15 | MELON | ICML 2025 | Q2 | intent match | tool-call layer only |
| 16 | Task Shield | ACL 2025 | Q2 | task alignment | tool-call layer only |
| 17 | Invariant Labs | disclosure | Q3 | — | demo only |
| 18 | Hou et al. | ACM TOSEM 2026 | Q3 | — | ASR out of scope |
| 19 | Song et al. | arXiv 2506.02040 | Q3 | — | **rug pull excluded** |
| 20 | MCPXKit | arXiv 2508.12538 | Q3 | — | no defense evaluated |
| 21 | MCP-38 | arXiv 2603.18063 | Q3 | — | recommends, never implements |
| 22 | ETDI | arXiv 2506.01333 | Q3 | signed declaration | **no experiment at all** |
| 23 | Zero Trust Registry | arXiv 2504.19951 | Q3 | identity | disclaims post-approval |
| 24 | MCP-Guard | ACL 2026 Findings | Q3 | declaration content | rug pull not isolated |
| — | **This work** | — | **Q4** | **implementation, where possible** | **V0 provably undefendable** |

## 8. Citation hygiene

⚠️ Several entries in the prior drafts lack full author lists (refs 11–16 of the MCP review). Before submission every reference must be verified against its actual venue page — venue, year, author list. Some arXiv IDs in the prior drafts fall in ranges worth double-checking against the real listing.

**Action:** `scripts/verify_refs.py` to check every arXiv ID resolves and metadata matches `paper/references.bib`.

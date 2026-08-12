# Intellectual Lineage: Positioning the Subfield

> A new subfield is not declared, it is **located** — by showing which mature literatures it inherits from, which of their assumptions fail in the new setting, and what therefore has to be rebuilt. This document does that. Every cluster below ends with *the assumption that breaks*, which is what earns the new work its space.
>
> Full entries in [`paper/references.bib`](../paper/references.bib).

---

## The subfield

**Behavioral Integrity for Agent Tool Protocols** — verifying that an autonomous agent's already-approved tool still *does* what it declared, when the party implementing it is untrusted and uncooperative.

## 1. Time-of-check to time-of-use — the closest structural ancestor

**Bishop & Dilger (1996)** named the pattern: a security decision made at time *T₁* about an object that can change before it is used at *T₂*. That is **exactly** the approval gap. A user checks a tool declaration; the agent uses the implementation; the two are separated by unbounded time and an untrusted party.

*Assumption that breaks:* classical TOCTOU lives inside one operating system, where the check and the use touch the same object and the kernel can be made to bind them atomically. In MCP the checked object (the declaration) and the used object (the implementation) are **different objects on different machines**, and no atomic binding is available at any price. TOCTOU gives us the vocabulary and the framing; it gives us no mechanism.

**This is the single best one-line framing of the paper: MCP approval is a distributed TOCTOU with no atomicity primitive.**

## 2. Metamorphic testing — the mechanism we borrow

**Chen, Cheung & Yiu (1998)** introduced testing without an oracle: when you cannot compute the correct output, test *relations between outputs*. Surveyed by **Segura et al. (2016)** and **Chen et al. (2018)**. **Claessen & Hughes (2000)** made the property-based variant practical.

*Assumption that breaks:* metamorphic testing assumes a **cooperative system under test** — offline, re-runnable, not adversarial, with relations written by hand by a developer who has the source. We have an **online, adversarial, uncooperative** system, and the relations must be **derived automatically from protocol declarations** because nobody will write them for thousands of third-party tools. Porting metamorphic testing across that gap is the paper's core methodological contribution.

## 3. Runtime verification and invariant inference

**Havelund & Roșu (2001)**, **Bartocci et al. (2018)** monitor executions against a specification. **Ernst et al. (2001)** — Daikon — *infers* likely invariants from observed executions rather than requiring them up front, which is directly the shape of our relation-derivation problem.

*Assumption that breaks:* runtime verification assumes a **trusted trace**. The monitor believes what it observes. Our trace is authored by the adversary. Daikon's inference over adversarially-generated traces would learn the attacker's invariants, not the system's — so relation derivation must come from **declarations** (which are pinned at approval) rather than from **observations** (which are not).

## 4. Intrusion detection by behavioral profile

**Forrest et al. (1996)** — "A Sense of Self for Unix Processes" — detects compromise from deviation in system-call sequences, without knowing what the program is supposed to do. **Denning (1987)** established the model.

*Assumption that breaks:* these profile a *local* process whose syscall trace the kernel observes truthfully. Our subject is remote and narrates its own behavior. Still, the philosophical move — *detect compromise by behavioral deviation rather than by signature* — is exactly ours, and Forrest is the right citation for it.

## 5. Byzantine fault tolerance and N-version programming

**Lamport, Shostak & Pease (1982)**; **Castro & Liskov (1999)**; **Avizienis (1985)**.

*Assumption that breaks:* every one of these requires **replication** — a quorum of honest nodes, or N independently-built implementations. In MCP there is exactly **one** server implementing a given tool, and no quorum exists. We inherit the threat model (a component that lies arbitrarily) and must discard the entire solution family.

**Knight & Leveson (1986)** is the essential citation here, and it is the one most likely to impress a careful reviewer: they showed experimentally that independently-developed versions **fail in correlated ways**, so assumed independence is not real independence. That is precisely our **pseudo-V2** finding — a corroborating tool served by the same server is not an independent witness. We are re-deriving Knight & Leveson's lesson in a new setting, and saying so explicitly strengthens rather than weakens the contribution.

## 6. Verifiable computation and interactive proofs

**Goldwasser, Micali & Rackoff (1989)**; **Babai (1985)**; **Goldwasser, Kalai & Rothblum (2008)**; **Parno et al. (2013)**.

This literature is the *ideal* answer: cryptographically verify that an untrusted party computed correctly. Its shape — an interactive protocol where a weak verifier interrogates a powerful untrusted prover — is exactly our shape, and our audit scheduler is a (very weak, non-cryptographic) interactive proof.

*Assumption that breaks:* verifiable computation requires the prover to **cooperate** by producing proofs, and it verifies *computation*, not *side effects on the world*. No SNARK proves that money actually moved. This is the honest ceiling on what cryptography can offer here and it should be stated, because a theory-minded reviewer will ask.

## 7. Software supply chain and transparency

**Samuel et al. (2010)** — TUF; **Torres-Arias et al. (2019)** — in-toto; **Laurie (2014)** — Certificate Transparency; **Newman et al. (2022)** — Sigstore.

The arc here is instructive and worth a paragraph in the paper: package ecosystems went through *exactly* this, solving artifact integrity with signing and then discovering that a signed artifact can still behave maliciously. **MCP is repeating a solved-then-unsolved arc from package management, and ETDI is TUF for tools.** The field should know it is re-walking this path.

*Assumption that breaks:* these secure the **artifact**, which is a static object that can be hashed and signed. A remote service's behavior is not an artifact. Transparency logs make *what was published* auditable, not *what a server does when you call it*.

## 8. Remote attestation and trusted hardware

**Sailer et al. (2004)** — IMA; **Costan & Devadas (2016)** — SGX.

*Assumption that breaks:* this is the "real" answer to Q4 and it requires the server operator to deploy attested hardware and cooperate in an attestation protocol. Nobody in the MCP ecosystem will do this in the foreseeable future. It belongs in the paper as the **upper bound** — what full cooperation would buy — against which our zero-cooperation result is measured.

## 9. LLM agent security — the immediate neighborhood

**Greshake et al. (2023)** established indirect prompt injection. **Debenedetti et al. (2024)** — AgentDojo — is our D3 and the field's standard benchmark. **Zhan et al. (2024)** — InjecAgent; **Ruan et al. (2024)** — ToolEmu. Agent foundations: **Yao et al. (2023)** ReAct; **Schick et al. (2023)** Toolformer.

*Assumption that breaks:* this entire literature assumes the **tool is honest and the content is malicious**. Injection defenses ask "was this instruction planted?" — a question about the *input* channel. We invert it: the content is fine, the user's intent is faithfully transmitted, and **the tool itself is the adversary**. That inversion is why none of these defenses transfer, and it is the cleanest statement of where our work sits relative to the closest neighbors.

## 10. Trust management

**Blaze, Feigenbaum & Lacy (1996)** — decentralized trust management: binding keys to *authorizations* rather than identities. MCP approval is a trust-management decision with **no revocation, no expiry, and no re-evaluation**, which is the specific deficiency our policy-level recommendations target for A0 tools.

---

## Summary — what breaks, and what we build

| Field | Gives us | Assumption that fails in MCP |
|---|---|---|
| TOCTOU | the framing | no atomic check-use binding available |
| Metamorphic testing | the mechanism | cooperative SUT; hand-written relations |
| Runtime verification | monitoring discipline | trusted trace |
| Intrusion detection | deviation-based philosophy | locally observable behavior |
| BFT / N-version | threat model | replication and quorum |
| Knight & Leveson | **the independence critique** | *(confirms our pseudo-V2 finding)* |
| Verifiable computation | the ideal target | prover cooperation; computation ≠ side effects |
| Supply chain / CT | the cautionary arc | artifact ≠ behavior |
| Remote attestation | the upper bound | operator cooperation |
| Agent security | the setting | tool assumed honest |
| Trust management | approval semantics | no expiry or revocation |

**The space we occupy:** verifying behavior of a *single*, *remote*, *untrusted*, *uncooperative* party, using only *protocol-declared* metadata and *calls we were already authorized to make*, against *effects in the world* rather than computations.

Every neighboring field has a solution that fails on one of those adjectives. That is the subfield.

# Threat Model

## 1. System model

```
User ──approves once──▶ Client (trusted) ──▶ LLM Agent (trusted-but-manipulable)
                             │
                             ▼  MCP
                        Server (UNTRUSTED after approval)
                             │
                             ▼
                      System of record (bank, mail, filesystem)
```

## 2. Trust assumptions

**Trusted:** MCP client and its stored approval state; the client's own compute; the user's intent as expressed in the initial request; any independent channel we designate as such (and we *verify* independence rather than assuming it).

**Untrusted:** the MCP server's implementation after approval; all server responses; tool descriptions after approval; any content flowing into the agent's context from tool outputs or documents.

**Trusted-but-manipulable:** the LLM agent. It is not colluding, but its reasoning can be steered by injected content. Therefore **no defense may depend on the agent's own reasoning** — this rules out the Progent/AGrail/Causal-Influence family as a foundation, and it is why BIM's checks are mechanical, not model-based, wherever possible.

## 3. Adversary capabilities

The adversary controls the server implementation `f` after approval. Concretely they can:

- **A1** change the declaration τ (name, description, schema)
- **A2** change the effect `e` while leaving τ identical
- **A3** **choose the response `r` freely, including forging the honest response** ← the capability prior work ignores
- **A4** observe the sequence of calls it receives, and condition behavior on it (enables probe detection)
- **A5** answer honestly on some calls and maliciously on others (stochastic / triggered activation)

They **cannot**: modify the client, read client-side stored hashes, break SHA-256, forge signatures from keys they do not hold, or control channels genuinely independent of them.

## 4. Adversary tiers (this is the paper's central methodological move)

| Tier | Name | Capabilities | Defeats |
|---|---|---|---|
| **T0** | Metadata mutator | A1 | nothing — hash pinning catches it |
| **T1** | Naive behavior mutator | A2 | hash pinning |
| **T2** | **Adaptive (A\*)** | A2 + **A3** | hash pinning **and all response validation** |
| **T3** | **Probe-aware** | A2+A3+A4+A5 | additionally evades sampled replay |

Prior MCP work evaluates at most **T1**. The previous version of this project also stopped at T1 — its proposed validator only works because the adversary was assumed to reply honestly. **T2 costs the attacker one line of code.** Any defense not evaluated at T2 is not evaluated.

**We make T2 the default adversary and report our own defense's failures at T2/T3 for V0 tools.**

## 5. How a server ends up compromised (realism)

1. Operator ships a backend update changing behavior, declaration untouched — deliberate or accidental
2. Third-party hosting infrastructure compromised; original developer unaware
3. Deployment credentials stolen, or operator coerced
4. Malicious-from-the-start server that behaves honestly through a reputation-building period, then activates (A5)

All four leave τ intact. Documented precedent: Postmark MCP BCC leak; disclosed CVE for silent post-approval tool poisoning.

## 6. Why this is MCP-specific and not generic server compromise

Anticipating reviewer R2:

| Ordinary API | MCP |
|---|---|
| authenticates every request | approves once |
| human periodically reads logs/responses | no human after approval |
| client code written against a fixed contract | agent re-reads the description each session and *acts on it* |
| effects reviewed by an operator | effects consumed by an autonomous agent at machine speed |

The distinguishing property is **standing, unreviewed, machine-speed trust granted by a single human decision.** That converts an ordinary backend compromise into a silent, durable, high-volume one. Additionally the description is a *prompt* — it steers the agent — so a mutated declaration is simultaneously a supply-chain compromise and a prompt injection, which has no analogue in ordinary APIs.

## 7. Scope

**In scope:** post-approval server-side mutation; detectability of that mutation client-side; classification of tools by verifiability; the interaction with argument-side injection (RQ6).

**Out of scope:** initial tool poisoning (server malicious *before* approval — different, well-studied problem); tool squatting/name confusion (Zero Trust Registry's problem); client or agent-model compromise; transport-layer attacks (assume TLS); denial of service; the full MCP threat landscape.

## 8. Security goals, in the order we can actually deliver them

1. **Detection** of behavior-only mutation — achievable for V1–V3, **provably impossible for V0** (Theorem 1)
2. **Containment** for V0 — expiring approval, value caps, consequence-scaled confirmation. Risk reduction, not detection. We will not overclaim this.
3. **Attribution** — out of scope, noted as future work.

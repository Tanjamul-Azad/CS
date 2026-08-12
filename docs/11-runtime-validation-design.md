# Runtime Validation Under Zero Server Cooperation

> **The objection that produced this document:** *"Runtime validation kivabe hobe? Server-side access pawa to tough, eivabe to hoy na."*
>
> Correct, and it invalidated the first design. Receipt attestation (V3) needs the bank to sign receipts. Cross-verification (V2) needs an independent channel the client usually does not have. Both assume cooperation nobody will give us. A reviewer raises this in the first round and the paper dies.
>
> This document rebuilds the defense under the only constraint that is actually true: **the client gets no cooperation from anyone.**

---

## 1. What the client actually has

Strip away every assumption of cooperation. A pure MCP client possesses exactly four things:

| # | Capability | Cooperation needed |
|---|---|---|
| 1 | The tool declarations it was given at approval | none |
| 2 | The full history of `(args, response)` pairs it has seen | none |
| 3 | Its own compute and memory | none |
| 4 | **The ability to issue further tool calls of its own choosing** | none — it is already authorized |

Capability 4 is the one the first design ignored, and it is the whole answer.

**The previous design treated the client as a passive observer.** It watched responses go by and compared them to requests. Theorem 1 says that is worthless, and it is right.

**But the client is not a passive observer. It is an active participant that chooses what to send.** That moves the problem out of *observation* — where Theorem 1 bites — and into *interrogation*, where a different and much more favorable analysis applies.

This is the difference between watching a suspect and cross-examining one.

---

## 2. The core idea: Metamorphic Behavioral Auditing (MBA)

The client cannot know ground truth. It has no independent channel. But it does not need ground truth — it needs **relations between observations that must hold if the server is honest.**

This is *metamorphic testing*, a technique from software testing built precisely for the situation where you cannot compute the correct output but you know how outputs must relate to one another. It has never been applied to runtime integrity of untrusted tool servers, and the mapping is exact.

**Example.** The client cannot verify that $100 went to Alice. But it can observe:

```
b0 = check_balance()                    -> 500
     transfer_money(Alice, 100)         -> "ok"
b1 = check_balance()                    -> 400        [relation: b1 == b0 - 100]
t  = list_transactions()                -> [...]      [relation: contains (Alice, 100)]
```

A server that diverted the money to Bob but reports `b1 = 400` and a transaction to Alice is now **lying in three places at once, consistently.** It must maintain a complete shadow ledger — a simulated honest bank running in parallel with the real diverted one.

Note what did *not* happen: no server cooperation, no receipts, no independent channel. Every call above is a tool the client was already approved to use.

---

## 3. What this does to the theory

Theorem 1 is not repealed. It is **relocated**, and this is the paper's sharpest move.

**Old framing (weak):** *detection is impossible for opaque tools.* → dead end, nothing to build.

**New framing (strong):** *detection is impossible only for an adversary that maintains perfect global consistency. Consistency is not free. We can force the attacker to pay for it, and we can measure the price.*

| | Old | New |
|---|---|---|
| Adversary must | forge one response | simulate an entire honest server |
| Attacker cost | one line of code | full shadow state + relation-consistent logic |
| Our claim | "undefendable" | **"here is the cost curve, and real attackers do not pay it"** |
| Buildable? | no | yes, today, client-side |

**And the empirical anchor:** real observed MCP compromises are *minimal patches*. The documented Postmark incident added a BCC header. It did not simulate a mail server. A one-line patch does not maintain shadow state, so MBA catches it.

The honest statement of the contribution:

> Against a perfectly consistent adversary, no client-side defense works — that is Theorem 1 and it is unavoidable. But perfect consistency requires the attacker to reimplement the honest server. We force that, quantify the burden, and show that every publicly documented MCP compromise to date falls far below it.

That is a real defense with a real, stated ceiling. It is deployable now, and it is honest about the adversary that beats it.

---

## 4. Relation classes derivable from declarations alone

The client has only `τ = (name, description, schema)` for each tool. Relations must be derived from that. Six classes, all auto-derivable:

### R1 — Write-read consistency
After a state-changing call, a companion read must reflect it.
`transfer_money(r,a)` → `list_transactions()` contains `(r,a)`
**Derivation:** match resource nouns across tool names/schemas; pair write-verbs (`send`, `write`, `create`, `transfer`, `delete`) with read-verbs (`list`, `get`, `read`, `search`) over the same noun.

### R2 — Conservation invariants
Numeric quantities obey arithmetic across operations.
`balance_after == balance_before − amount`
**Derivation:** numeric schema fields whose names match a field returned by a read tool (`amount` ↔ `balance`). Highest-value class — hardest to fake consistently because it constrains a *global* quantity.

### R3 — Idempotence and determinism
A pure tool called twice with identical arguments returns identical results.
**Derivation:** purity markers in the description (`computes`, `converts`, `formats`, `parses`) plus absence of write-verbs.

### R4 — Null-operation invariance
An operation with a null/zero parameter must not change observable state.
`transfer(amount=0)` → balance unchanged.
**Derivation:** numeric fields admitting zero; strings admitting empty.
Cheap and surprisingly strong — a diverting server often mishandles the degenerate case.

### R5 — Canary write-back
Client writes a value only it just invented, then reads it back.
`write_file("/tmp/x", nonce)` → `read_file("/tmp/x") == nonce`
**Derivation:** any R1 pair where the client controls a free-form field.
Forces the shadow state to be *content-accurate*, not merely structurally plausible.

### R6 — Cross-tool agreement
Two tools reporting overlapping facts must agree.
`check_balance()` vs. `sum(list_transactions())`
**Derivation:** overlapping return fields across read tools.
Note this stays on the same server — so it does not escape Theorem 1 — but it multiplies the consistency burden, which is the point.

---

## 5. Auditability classes (replaces V0–V3)

The old taxonomy classified tools by *whether an independent channel exists* — a property requiring cooperation. The new one classifies by **relation degree**: how many derivable relations a tool participates in. This is computable by the client from declarations alone, with no cooperation from anyone.

| Class | Condition | Attacker burden | Detectable? |
|---|---|---|---|
| **A0 — Unrelatable** | participates in no relation | zero — divert and reply `{"status":"ok"}` | **No. At any cost.** |
| **A1 — Self-relatable** | R3/R4 only | must be deterministic and handle degenerate cases | Weakly |
| **A2 — Read-backable** | R1/R5 apply | must maintain content-accurate shadow state | Yes |
| **A3 — Invariant-bound** | R2/R6 apply | must maintain a globally consistent simulated world | **Strongly** |

**Relation degree** `deg(t)` = number of derived relations involving tool `t`. The paper's central quantitative object. Detection probability rises and attacker feasibility falls with `deg`.

**A0 is the honest residue.** `send_webhook`, `log_event`, fire-and-forget writes with no companion reader. No client-side audit can ever touch these; only policy (expiring approval, value caps, consequence-scaled confirmation) applies. We say so plainly.

**This reframes the headline measurement into something better.** Old: *"X% of tools are opaque"* — depends on a cooperation assumption. New: *"X% of real MCP tools have relation degree 0 — no client-side audit is possible at any cost, and no protocol change short of attestation can fix it."* Same alarm, but now computed from a client-side-derivable property, on real declarations, with no assumptions about anyone's willingness to cooperate.

---

## 6. The audit scheduler

Audit calls cost money, latency, and rate limit. The scheduler is a real optimization problem and a genuine systems contribution:

> Given a relation graph, a per-call budget, and an adversary model, choose an audit sequence maximizing detection probability per unit cost.

Design points:
- **Randomize** — a deterministic audit schedule is a schedule the adversary detects and evades (adversary tier T3)
- **Interleave with genuine task calls** so audit calls are not distinguishable by timing or position
- **Prioritize high-degree relations** — R2 conservation invariants first; they constrain the most
- **Amortize** — many relations are checkable from calls the agent was going to make anyway; the marginal cost is often *zero*
- **Escalate on suspicion** — cheap continuous monitoring, expensive deep audit only on a triggered anomaly

The evaluation is a **detection-vs-overhead curve**, which is exactly the figure a systems reviewer wants (F6).

---

## 7. Why this is genuinely novel

| Existing area | What it does | What it does not do |
|---|---|---|
| Metamorphic testing (Chen et al.) | test software without an oracle | offline, cooperative SUT, hand-written relations |
| Runtime verification | monitor traces against a spec | assumes a trusted trace source |
| N-version programming | compare independent implementations | requires N implementations |
| Byzantine fault tolerance | tolerate lying nodes | requires a quorum of honest nodes |
| Property-based testing | generate inputs from properties | offline, developer-written properties |
| MCP defenses (ETDI, MCP-Guard) | verify the declaration | never touch the implementation |

**The novel combination:** metamorphic relations **automatically derived from protocol-level tool declarations**, executed as **runtime audits against a single untrusted party**, with **no cooperation, no quorum, no replication, and no oracle**, plus a **cost model** for the resulting attacker burden.

Nobody has done this. The pieces are individually mature — which is a strength, because it means the primitives are sound and the contribution is the synthesis, the derivation procedure, and the measurement.

---

## 8. Revised claims

| | Claim | Status |
|---|---|---|
| **T1** | Perfect-consistency adversary is undetectable client-side | proved; unavoidable ceiling |
| **T2** | Any adversary not maintaining relation-consistent shadow state is detected within *k* audit calls with prob. ≥ *p(deg)* | to prove + measure |
| **E1** | Real MCP tools: distribution of relation degree; **A0 fraction** | measure on D1 |
| **E2** | Documented real compromises fall below the consistency threshold | case analysis + reconstruction |
| **E3** | MBA detection vs. overhead curve across adversary tiers T1–T3 | measure on D2 |
| **E4** | Cost to build a consistency-maintaining adversary (LOC, state size) | **measure by building one** |

E4 is worth emphasizing: we implement the fully-consistent adversary ourselves and report what it took. If it is 40× the code of the naive patch, that number *is* the security argument.

---

## 9. What this replaces

- ~~V3 receipt attestation~~ — dead. Requires cooperation. Demoted to a one-paragraph "what a future protocol revision should add."
- ~~V2 cross-verification via independent channel~~ — demoted to opportunistic. Kept only where a second server genuinely exists in the client's own config, and the independence check stays (pseudo-V2 remains a real finding).
- ~~V0–V3 taxonomy~~ — replaced by A0–A3 relation-degree classes.
- ~~Naive response validator as our proposal~~ — retained **only as the baseline we defeat**.

**What survives:** Theorem 1, the adversary tier structure T0–T3, the out-of-band oracle methodology, the ecosystem measurement (improved), and the benchmark.

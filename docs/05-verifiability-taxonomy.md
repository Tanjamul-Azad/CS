# Theory: Transcript Indistinguishability and the Cost of Consistency

> **Revision note (2026-08-13).** The first version of this document built a taxonomy on *"does an independent observation channel exist"* and proposed receipt attestation as the fix. That was wrong in a way that mattered: it assumed cooperation from servers and downstream providers that will not be given. This version rebuilds the theory around what a client can do **alone**, and the result is stronger — the impossibility becomes a *cost boundary* rather than a dead end. See [`11-runtime-validation-design.md`](11-runtime-validation-design.md).

---

## 1. Model

A tool is a declaration **τ = (n, d, σ)** with a hidden implementation **f**. A call produces two things:

```
(r, e) = f(a)      r = response returned to client
                   e = effect in the world
```

The client sees `r`. Never `e`. Approval binds a human decision to `τ`; execution is governed by `f`; **nothing in the protocol binds `f` to `τ`.**

**Session transcript** after *k* calls:

```
T_k = ⟨(a_1, r_1), (a_2, r_2), ..., (a_k, r_k)⟩
```

This — plus the declarations — is the client's *entire* epistemic position. Any client-side defense is a function of `T_k`.

## 2. Theorem 1 — transcript indistinguishability

**Definition.** Implementations `f` and `f*` are **transcript-indistinguishable** under client policy Π if, for every call sequence Π may issue, the induced distributions over `T_k` are identical.

---

**Theorem 1.** *Let M be any client-side monitor whose input is `T_k` together with the declarations and client-side state. If `f` and `f*` are transcript-indistinguishable under the client's policy, then M's detection rate against `f*` equals its false-positive rate against `f`.*

**Proof.** M's input is identically distributed under `f` and `f*`, hence so is M's output. Therefore `P[flag | f*] = P[flag | f]`. ∎

---

**What Theorem 1 kills.** Every passive response-inspecting defense. Including the one this project originally proposed. Against an adversary that returns the honest response while performing a malicious effect, detection is not *reduced* — it is information-theoretically absent. Empirically confirmed in `experiments/demo_theorem1.py`: DBR 100% → 0% across that single change.

**What Theorem 1 does *not* say.** It does not say the problem is unsolvable. It says the client cannot win **while remaining passive**. The hypothesis of the theorem is transcript-indistinguishability *under the client's policy* — and the client chooses its policy.

**This is the hinge of the entire paper.** The client is not restricted to watching. It is authorized to *call*. It can choose sequences that make indistinguishability expensive to maintain.

## 3. Theorem 2 — the cost of consistency

Let **R** be a set of metamorphic relations over tools, each a predicate on a transcript fragment that holds for every honest implementation (see [`11-runtime-validation-design.md`](11-runtime-validation-design.md) §4).

**Definition (R-consistency).** `f*` is **R-consistent** if every transcript it can produce satisfies every relation in R.

**Lemma.** Transcript-indistinguishability under an auditing policy that checks R **requires** R-consistency.
*Immediate: a violated relation is an observable difference.*

---

**Theorem 2 (informal).** *Let `f*` divert effects and not be R-consistent, with `f*` violating relation ρ ∈ R. A client auditing policy that issues ρ's witnessing call sequence with probability q per session detects `f*` with probability 1 − (1−q)^m over m sessions.*

**Corollary.** For an adversary to remain undetectable it must be R-consistent — which requires maintaining **shadow state**: a simulated honest world consistent with every relation the client might check, sustained for the lifetime of the compromise.

---

**Definition (consistency burden).** `B(R, f)` = the state and logic an adversary must maintain to be R-consistent while diverting effects. Measured concretely as: shadow-state size, lines of code, and per-call overhead — **quantities we obtain by building such an adversary ourselves** (claim E4).

## 4. The reframing this produces

| | Passive framing (v1) | Active framing (v2) |
|---|---|---|
| Question | can we detect? | what does evading detection **cost**? |
| Answer | no, for opaque tools | a full honest-server simulation |
| Attacker effort | 1 line | shadow state + relation logic |
| Contribution | "undefendable" | **cost curve + real adversaries fall below it** |
| Buildable | no | yes, client-side, today |

The impossibility result is retained in full. It is repositioned as the **ceiling** of a cost landscape rather than the whole story.

**The empirical anchor that makes this more than theory.** Documented real MCP compromises are minimal patches — the Postmark incident added a BCC header. It did not simulate a mail server. Real adversaries operate far below the consistency threshold. MBA catches them; a nation-state adversary who reimplements the server defeats it. The paper states both.

## 5. Auditability classes A0–A3

Classified by **relation degree** `deg(t)` — the number of derivable relations tool *t* participates in. Computable by the client from declarations alone; **requires cooperation from nobody.**

| Class | Relations | Attacker burden | Detectable |
|---|---|---|---|
| **A0** Unrelatable | ∅ | none | **No — at any cost** |
| **A1** Self-relatable | R3 determinism, R4 null-op | be deterministic; handle degenerate inputs | weak |
| **A2** Read-backable | R1 write-read, R5 canary | content-accurate shadow state | yes |
| **A3** Invariant-bound | R2 conservation, R6 cross-tool | globally consistent simulated world | **strong** |

**A0 is the honest residue.** Fire-and-forget writes with no companion reader — `send_webhook`, `log_event`, `notify`. Theorem 1 applies with full force and no audit policy escapes it. Only policy-level mitigation remains: expiring approval, value caps, consequence-scaled confirmation. Risk reduction, not detection. We will not overclaim it.

## 6. Headline measurement, restated

Old (cooperation-dependent, and therefore soft):
> ~~*X% of MCP tools are opaque.*~~

New (client-computable, and therefore hard):
> **X% of real MCP tools have relation degree 0 — no client-side audit can detect their compromise at any cost or any budget.**

Same alarm; now derived from a property the client can compute itself, measured on real declarations, assuming nobody's cooperation. Strictly stronger claim, strictly weaker assumptions.

## 7. Open theoretical questions

1. **Tight bound on Theorem 2.** Detection probability as a function of `deg(t)`, audit budget, and session length. Is there a clean closed form?
2. **Minimum relation set.** Given a budget of *b* audit calls, which subset of R maximizes expected detection? Submodular — likely admits a greedy approximation with a provable ratio.
3. **Adaptive adversary equilibrium.** T3 evades audits it can recognize; the client randomizes. This is a signaling game. Is there a computable equilibrium, and what is the value to the defender?
4. **Composition.** Do relations compose across *servers* — can a second MCP server unknowingly witness the first's lie? This is the surviving, non-cooperative remnant of the old V2 idea, and it may be the most interesting question in the list.
5. **Is `deg` gameable?** A malicious server author controls its own declarations and could publish tools engineered to have degree 0. If so, low `deg` becomes a *signal* clients should treat as suspicious — which flips a limitation into a defense.

Question 5 is the most promising and should be developed: it turns the taxonomy into an actionable trust heuristic rather than only a measurement instrument.

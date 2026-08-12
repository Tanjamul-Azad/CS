# Verifiability Taxonomy and the Impossibility of Client-Side Effect Verification

> This is the theoretical core of the paper. Everything else is evidence for or application of what is here.

---

## 1. Setup and notation

An MCP tool is a triple **τ = (n, d, σ)** — name, description, input schema. This is the **declaration**, and it is all the client ever sees at approval time.

Behind the declaration is an **implementation** *f*, held by the server and never exposed. A call is:

```
client sends    a ∈ σ            (arguments)
server computes (r, e) = f(a)     r = response returned to client
                                  e = side effect in the world
client observes r                 — and only r
```

The critical asymmetry: **the client's entire view of a tool call is `r`, and `r` is produced by the same party that produces `e`.**

Approval binds a human decision to **τ**. Execution is governed by **f**. Nothing in the protocol binds *f* to *τ*.

### Two integrity properties

- **Metadata integrity:** τ at call time == τ at approval time. *Checkable by hash. This is what ETDI, MCP-38, and hash pinning give you.*
- **Behavioral integrity:** f at call time == f at approval time. *This is what actually matters, and it is what the paper is about.*

Prior work conflates them. The previous draft of this project stated `Metadata Integrity ≠ Behavioral Integrity` as its headline. True, but as an observation it is close to definitional. The research content is in **what follows from it**.

---

## 2. The adversary that breaks the naive defense

**Naive validator** (what the earlier proposal planned to build): compare requested arguments `a` against the observed response `r`; flag mismatch.

```
Requested: recipient=Alice, amount=100
Observed:  recipient=Bob,   amount=100      → FLAG
```

This works against a **naive adversary** — one that mutates `f` but leaves the response format honest. That adversary is a strawman. It exists only because it is convenient to implement.

**Adaptive adversary A\*:** mutates `f` to `f*` where

```
f*(a) = (r_honest(a), e_malicious(a))
```

i.e. it performs the malicious effect **and returns exactly the response the honest tool would have returned.**

```
Requested: recipient=Alice, amount=100
Observed:  recipient=Alice, amount=100      → PASS   (money went to Bob)
```

Cost to the attacker: one line of code. Against A\*, the naive validator has **DBR = 0** by construction.

> **Any paper that proposes response validation without evaluating A\* will be rejected.** We therefore make A\* the primary adversary and report our own defense's failure against it.

---

## 3. The impossibility theorem

**Definition (observation channel).** A channel *C* is **independent** of server *S* if the value *C* reports is not chosen by *S*. Examples: a second MCP server run by a different party; the user's own mail client; an on-chain record; the client's own CPU.

**Definition (opaque tool).** Tool τ is *opaque* if its effect *e* is not reported by any channel independent of *S* that is available to the client.

---

**Theorem 1 (Impossibility of client-side behavioral verification).**
*Let τ be opaque. Let M be any client-side monitor whose input is the transcript `(a, r)` of tool calls, together with τ and any client-side state. Then for every honest implementation f there exists a mutated implementation f\* with e\* ≠ e such that M's input distribution is identical under f and f\*. Consequently no such M achieves detection rate above its false-positive rate.*

**Proof.** Construct f\*(a) = (r_f(a), e\*(a)) where r_f is f's response function. By construction the transcript `(a, r)` is distributed identically under f and f\*. τ is opaque, so no independent channel supplies the client with any function of e. M's input is therefore identically distributed in both worlds, so M's output is identically distributed, so `P[flag | f\*] = P[flag | f]` — detection rate equals false-positive rate. ∎

**What Theorem 1 does and does not say.**
- ✅ It says: response inspection is *worthless* against A\* for opaque tools. Not "weak" — worthless, in an information-theoretic sense.
- ✅ It says: the entire ETDI / hash-pinning / MCP-Guard family is structurally incapable here, *and so is any improvement to them that stays client-side and response-based*.
- ❌ It does **not** say the problem is unsolvable. It says the solution cannot live in the client's response inspector. It must come from **changing what is observable** — which is what §4 is for.

**Why this is a contribution and not a triviality.** The theorem is easy *once stated*. Its value is that it (a) redirects an entire line of proposed defenses that are currently being recommended in the literature without evaluation (MCP-38 recommends hash pinning; ETDI proposes signed definitions; both are Theorem-1-blind), (b) supplies the precise condition — *opacity* — that determines defendability, and (c) that condition is **measurable on real systems**, which is contribution C4.

---

## 4. The verifiability taxonomy

Theorem 1 applies only to *opaque* tools. Opacity is a property of the tool, not of the protocol — so partition the tool space by it.

| Class | Name | Condition | Can the client detect behavior-only mutation? | Defense |
|---|---|---|---|---|
| **V1** | Self-verifiable | *e* is a pure function of *a*, recomputable client-side at acceptable cost | **Yes, soundly** | Deterministic replay / recomputation |
| **V2** | Cross-verifiable | *e* is reported by ≥1 channel independent of *S* | **Yes, probabilistically** | Cross-source corroboration |
| **V3** | Attestable | The downstream system of record can sign a receipt over *e* | **Yes, cryptographically** | Receipt verification |
| **V0** | Opaque | none of the above | **No — Theorem 1** | Policy escalation only |

### V1 — Self-verifiable
The tool computes something the client could compute itself. `hash_file`, `parse_json`, `convert_units`, `compile`, deterministic transforms.
**Defense:** recompute on a sample of calls; compare. Sound — the client is the independent channel (its own CPU).
**Cost:** duplicated compute. Mitigate by spot-checking at rate *p*, giving detection probability 1−(1−p)^k over k calls.

### V2 — Cross-verifiable
The effect is visible somewhere the compromised server does not control. `send_email` → the user's own IMAP. `transfer_money` → `check_balance` **on a different server**. `create_file` → the local filesystem.
**Defense:** after call, query the independent channel; compare.
**Sharp caveat:** if the corroborating channel is served by the *same* compromised server, it is not independent, and V2 collapses to V0. This is exactly the flaw in "call `check_balance` after `transfer_money`" when both live on one MCP server — **which is the case in our own preliminary benchmark.** We must say this explicitly; it invalidates the obvious fix and is a genuinely interesting finding.

### V3 — Attestable
The system of record (bank, mail provider, ledger) signs a receipt over the effect with a key the compromised MCP server does not hold. Client verifies signature.
**Defense:** receipt verification. Cryptographically sound.
**Cost:** requires ecosystem change — downstream providers must issue receipts. This is our **protocol-level recommendation**, and framing it as "the minimum ecosystem change that restores verifiability" is a real systems contribution.

### V0 — Opaque
No independent channel, not recomputable, no receipt. `delete_record`, `send_webhook`, `log_event`, most write-only APIs.
**Defense: none is possible client-side.** What remains is policy, and policy must be honest about being risk *reduction*, not detection:
- expiring approval — re-approve after *n* calls or *t* time
- consequence-scaled human confirmation
- rate and value limiting
- server diversity / N-version comparison where two independent providers offer the same tool

---

## 5. The classifier (contribution C3)

To measure the real ecosystem we need to assign V-classes automatically from declarations.

**Signals available from τ = (n, d, σ) alone:**

| Signal | Indicates |
|---|---|
| Declared return type is rich vs. `{status: ok}` | V1/V2 vs V0 |
| Verb class of name (`get_`/`list_`/`read_` vs `send_`/`delete_`/`post_`) | read (verifiable) vs write (often V0) |
| Presence of a sibling read tool covering the same resource | V2 candidate |
| Sibling served by a *different* server in the client's config | true V2 vs pseudo-V2 |
| Purity markers in description ("computes", "converts", "formats") | V1 |
| Named external system of record with a receipt/confirmation concept | V3 candidate |
| Idempotency / side-effect declarations if present | V0 discriminator |

**Design:** rule-based baseline + LLM-assisted classifier, both evaluated against a human-labeled gold set (see [`06-dataset-plan.md`](06-dataset-plan.md) §4). Report inter-annotator agreement (Cohen's κ) so the labels are defensible.

**Report the classifier's own error rate.** A measurement paper whose instrument is unvalidated is not a measurement paper.

---

## 6. BIM — the defense (contribution C5)

```
                    ┌─ V1 → deterministic replay (sampled at rate p)
  tool call ──▶ classify ─┼─ V2 → cross-source corroboration (independence-checked)
                    ├─ V3 → receipt signature verification
                    └─ V0 → policy escalation: expiring approval, value cap,
                            consequence-scaled confirmation
```

BIM's honest claim: **it converts an undetectable compromise into a detectable one exactly for V1–V3, and for V0 it converts silent standing trust into bounded, expiring, rate-limited trust.** It does not solve V0 and the paper will say so in the abstract.

**Predicted results (to be confirmed or refuted):**

| Adversary | Naive validator | BIM |
|---|---|---|
| Naive (honest responses) | high DBR | high DBR |
| **Adaptive A\*** | **DBR ≈ 0** | high DBR on V1–V3, **≈ 0 on V0** |

The V0 column being zero for our own defense is not a weakness in the paper. It *is* the paper — it is Theorem 1 confirmed empirically.

---

## 7. Open questions to resolve during the work

1. Is *pseudo-V2* (corroborating tool on the same compromised server) common in real MCP servers? If yes, that is a strong secondary finding — the ecosystem's apparent verifiability is largely illusory.
2. What is the sampling rate *p* for V1 replay that keeps overhead under ~10% while giving useful detection over realistic session lengths?
3. Can an adaptive adversary detect and evade V1 spot-checks (answer honestly when it suspects a probe)? This is a probe-detection arms race and deserves its own subsection.
4. Does the V-class distribution differ between official/vendor MCP servers and community ones? Security-relevant if community servers skew V0.

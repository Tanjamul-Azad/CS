# Design History — What Broke and Why

This project has been rebuilt twice, has had one of its own hypotheses falsified, and has had another falsified prematurely and then restored. This document records all of it, in order, with the reasoning.

It exists for three reasons. A reviewer will ask why the design looks the way it does, and "we tried the obvious thing and it failed for this reason" is a much stronger answer than silence. Anyone extending the work — human or LLM — will otherwise re-walk the same dead ends. And the discarded versions are themselves evidence: a design that survived three serious attempts to kill it is worth more than one that was never attacked.

**Read this before proposing changes.** Several natural-looking ideas are already ruled out below.

---

## Timeline

| # | What changed | Cause |
|---|---|---|
| 0 | Original framing: *"metadata integrity ≠ behavioral integrity"* | near-tautological; could not carry a paper |
| 1 | → Theory-anchored, Theorem 1 at the centre | needed a result, not an observation |
| 2 | Defense v1: receipt attestation + cross-channel verification | **killed — required cooperation nobody will give** |
| 3 | → MBA: active interrogation using already-authorized calls | the client is not passive |
| 4 | Taxonomy V0–V3 → A0–A3 | V-classes secretly assumed cooperation |
| 5 | Annotation critique inverted | data: hints are *unused*, not merely unverifiable |
| 6 | Tool-count hypothesis "falsified", then **un-falsified** | partial data misled us; full data restored it |
| 7 | Resource cohesion → read coverage | metric failed to discriminate |

---

## Pivot 0 → 1: from observation to theorem

**The original framing** was that MCP verifies metadata while what matters is behavior, so metadata integrity is insufficient.

**Why it failed.** True, but nearly tautological. A reviewer reads it and says *"yes, obviously"* — there is no result, only a restatement of the problem. The consensus defense (hash pinning) already implicitly concedes it.

**What replaced it.** A theorem with a sharp edge: not *"pinning is insufficient"* but *"here is precisely what no client-side monitor can do, and here is the 3-line program that proves it."* Theorem 1 turns a complaint into a boundary.

---

## Pivot 2 → 3: the design that required cooperation

**This is the most important pivot in the project.**

Defense v1 proposed two mechanisms:

- **V3 receipt attestation** — the downstream provider (a bank, a mail host) signs a receipt for each effect, and the client verifies the signature.
- **V2 cross-verification** — the client confirms the effect through an independent second channel.

**Why it failed.** Both require cooperation the client cannot obtain.

> *"Runtime validation kivabe hobe? like server side access pawa to tough, eivabe to hoy na."*
> — the project supervisor, and they were right

No bank will sign receipts for your AI agent. No mail provider will deploy attestation because an agent framework would like it to. And V2's "independent channel" is usually just *another tool on the same server* — which is not independent at all.

We had designed defenses that work only in a world that does not exist. A reviewer would have said exactly the same thing, and it would have been fatal in round one rather than recoverable.

**The constraint that came out of it, now binding:**

> **Zero cooperation.** Nothing may be required of the server, its operator, or any downstream provider. Client-side only. Deployable today.

**What replaced it — and why the constraint made the paper better.**

The reframe was noticing that Theorem 1 constrains a **passive** client, one that inspects responses. But an MCP client is not passive: it holds *approval to call*. That single observation moves the problem out of observation, where the impossibility is total, into interrogation, where it is not.

Hence **Metamorphic Behavioral Auditing** — relations derived from the declarations the server already advertises, checked with calls the client is already permitted to make.

Theorem 1 was not repealed. It was **relocated**, and became the ceiling of a cost curve instead of a dead end. The question changed from *"can we detect this?"* (no) to *"what does evading detection cost?"* (a full honest-server simulation). That is a strictly better paper, and we would not have found it without the objection.

**Do not reintroduce cooperation-dependent mechanisms.** If a proposal needs the server to do anything at all, it is out of scope by construction.

---

## Pivot 4: V0–V3 → A0–A3

The old taxonomy classified tools by "opacity", but its upper classes were *defined in terms of the cooperation mechanisms that had just been deleted* — V2 meant "has an independent channel", V3 meant "supports receipt attestation". With those gone the ladder had no top.

**A0–A3 is keyed on relation degree**, which the client computes for itself from declarations alone, assuming nothing about anyone:

| | |
|---|---|
| **A0** | no relation derivable — undetectable at any budget |
| **A1** | self-relatable (determinism, null-op) |
| **A2** | read-backable (write-read, canary) |
| **A3** | invariant-bound (conservation) — strongest |

The dangerous cell is **A0 ∧ mutating**: consequential *and* uncheckable. That is where policy has to substitute for detection, and the deployed tool says so explicitly rather than implying coverage it lacks.

---

## Pivot 5: the annotation critique, inverted by data

**What we claimed** (in [`13`](13-d1-preliminary-findings.md)): MCP defines behavioral hints — `readOnlyHint`, `destructiveHint`, `idempotentHint` — describing exactly the properties this work is about, and they are **self-declared by the party being audited**. A compromised server sets `readOnlyHint: true` and a trusting client stops looking. Unverifiable by construction: it is metadata, so hash pinning confirms only that the lie has not changed since approval.

That reasoning is sound, and on the official reference servers the hints appear on 51–74% of tools, which made it look important.

**What the ecosystem data showed** (full harvest, n=5,397): `readOnlyHint` appears on **3.1%** of tools. `outputSchema` on **1.2%**.

**The correction.** The story is not *"the protocol trusts the attacker's self-report"* so much as *"the protocol's one behavioral channel is dead on arrival."* Both are findings; the second is larger, and it *inverts* the framing rather than refining it — which is why `13` is marked superseded rather than quietly edited.

**It also strengthened our own position.** We feared our classifier leaned on attacker-controlled metadata. Dual derivation — classifying once trusting the hints, once ignoring them — moves only **2.3 points**. Measured auditability barely depends on the attacker's word, because the attacker's word is almost never given.

---

## Pivot 6: our own hypothesis, "falsified" — then un-falsified

This one reverses twice, and the reversal is the lesson.

**What we predicted** ([`13`](13-d1-preliminary-findings.md) §4): relations are derived *between* sibling tools, so a server with one tool is A0 by construction. A0 rate should therefore fall monotonically as servers ship more tools.

**What the partial data said** (n=1,153, 130 of 500 repos):

| tools/server | A0 rate |
|---|---|
| 1 | 83.3% |
| 2–3 | 87.5% |
| 4–7 | 65.3% |
| 8–15 | 45.3% |
| **16+** | **62.9%** ← rises again |

Not monotonic. We wrote it up as falsified, with a mechanism that sounded convincing: large servers are bundles of unrelated tools rather than cohesive services.

**What the full data said** (n=5,397, all 500 repos):

| tools/server | A0 rate |
|---|---|
| 1 | 88.0% |
| 2–3 | 84.6% |
| 4–7 | 72.4% |
| 8–15 | 55.6% |
| 16+ | 54.5% |

Monotonic decreasing. **The reversal was small-sample noise, and our falsification was premature.** The original hypothesis holds.

**Why this is retained rather than deleted.** It is the cleanest available argument for the discipline this project keeps insisting on — do not draw conclusions from a partial corpus. We violated that rule on our own data and were wrong within the hour. Every "do not cite these figures" warning elsewhere in these documents is there because of exactly this failure mode, and it is more persuasive with a worked example than without.

It also cost us nothing except a wrong paragraph, because the corpus was regenerable. That is the argument for keeping `data/processed/` gitignored and rebuilding rather than committing snapshots.

**What survived:** read coverage (pivot 7) is still the better predictor — 92.8% A0 for servers with no reads, against 88.0% for single-tool servers — and it is mechanistic rather than correlational. Tool count is a proxy; read coverage is the actual mechanism. Both hold; one explains the other.

---

## Pivot 7: resource cohesion → read coverage

**First replacement attempt:** *resource cohesion* — what fraction of a server's tools share vocabulary with a sibling.

**Why it failed:** nearly every server scored above 0.8. Almost any two tools share a token like `id` or `name`, so the metric did not discriminate at all — 59 of 65 servers landed in a single band.

The lesson generalises: **sharing vocabulary is not sharing a resource**, and only the latter can support a relation.

**Second attempt, which worked:** *read coverage*. Every relation needs a **read** to corroborate a **write**. A server exposing twenty writes and no reads is unauditable at any size.

| reads / tools | A0 rate |
|---|---|
| **none** | **96.1%** |
| <20% | 56.5% |
| 20–40% | 48.8% |
| **40–60%** | **43.3%** ← minimum |
| >60% | 58.2% |

Spearman ρ = −0.300. The curve is **U-shaped**: read-heavy servers rise again because a read also needs a write to corroborate *it*. What predicts auditability is **balance**.

This is mechanistic rather than correlational — it is the derivation rule made visible in ecosystem data — and it yields concrete advice: **ship a read for every write.**

---

## Four instrument bugs, each of which produced a confident wrong number

None raised an error. Each returned a plausible, publishable-looking figure. They are the argument for validating an instrument against real data rather than against fixtures you wrote yourself.

| Bug | What it produced |
|---|---|
| Multi-tool files collapsed to one — `filesystem/index.ts` declares 14, extractor returned 1 | Destroyed the sibling read/write pairs relations derive *from*. Corpus read **100% A0**. |
| Inline `inputSchema` returned zero fields — the region scanner stopped at the first *nested* key instead of the next *sibling* key | Suppressed R2 and R5 everywhere. Field resolution went **23% → 72%** on fixing. |
| Field bleed between adjacent TS declarations | One tool's schema merged into its neighbour's |
| Write detection missed `purge_sessions`, `prune_tools`, `approve_prompt` | The **dangerous** direction — policy waved mutating tools through as harmless |

The last one exposed a design principle worth stating: **the two vocabularies must be tuned in opposite directions.** Relation derivation wants *precision* (a spurious relation is a false alarm and inflates measured auditability); write detection wants *recall* (a missed write is an unprotected dangerous call). Tuning both the same way is wrong in one of them, necessarily.

Every bug above is now pinned by a regression test whose docstring states what it broke.

---

## Ideas already ruled out

Do not propose these without new information.

| Idea | Why not |
|---|---|
| Ask the server to sign receipts | Cooperation. Killed in pivot 2. |
| Verify effects through an independent channel | The client usually has none; "independent" tools on the same server are not independent |
| Trust `readOnlyHint` to decide what to audit | Self-declared by the audited party — *and* present on only 3.1% of real tools |
| Derive relations across servers | Different trust domain; agreement there proves nothing here. See Knight & Leveson (1986) on correlated failure in supposedly independent versions ([`12`](12-intellectual-lineage.md)) |
| Probe with synthetic writes by default | A probe write is a **real** write. `transfer_money` "tests" move real money |
| Use tool count as an auditability proxy | Falsified in pivot 6 |
| Measure vocabulary overlap as cohesion | Does not discriminate; pivot 7 |

---

## What has survived every attack so far

- **Theorem 1** — the impossibility for passive clients
- **Active interrogation** — the client's authority to call is the resource the defense spends
- **Cost, not prevention** — defenses price attackers rather than stopping them
- **Zero cooperation** — the constraint that killed v1 and improved everything after
- **Honesty about the ceiling** — the 17-LOC adversary wins, and that is in the abstract

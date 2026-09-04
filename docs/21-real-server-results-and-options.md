# Real-Server Results and Options — Where We Actually Are

Written 2026-09-04, after the first full real-server evaluation completed (L1, then L2/L3 follow-up). This supersedes the acceptance criteria and phase plan in [`20-plan-to-submission.md`](20-plan-to-submission.md), which was written before any of this ran and predicted numbers (>80% detection) the real data does not support. Read this one doc first — it links out to everything else.

---

## 1. Objective (short version)

Full framing: [`00-RESEARCH-PLAN.md`](00-RESEARCH-PLAN.md), [`04-threat-model.md`](04-threat-model.md), [`05-verifiability-taxonomy.md`](05-verifiability-taxonomy.md).

A client calling an MCP tool server is authorized to *call* it, not just read its response. **Theorem 1**: a passive client (inspects responses only) can never detect a server that performs a different effect than it claims. The escape is that the client can issue *extra, legitimate* calls — reads it was already allowed to make — to check whether the world looks like the response claimed. **Metamorphic Behavioral Auditing (MBA)** derives these checks automatically from a server's own tool declarations: write-read consistency (**R1**), conservation of a numeric quantity (**R2**), determinism (**R3**), and canary round-trips (**R5**). The **A0–A3** taxonomy classifies each tool by whether any such relation is derivable at all — A0 tools are provably undetectable by this method, at any budget.

The open empirical question this session answered: **does any of this actually work against real, unmodified, third-party MCP servers — not ones we wrote?**

---

## 2. Data collected

### D1 — static corpus (what tools exist, what class they're in)

Static extraction only, never contacts a live server. **18,566 tools, 2,846 real GitHub repositories.**

| Class | Share | Meaning |
|---|---|---|
| A0 | **69.7%** [CI 69.1–70.4] | undetectable by this method, at any budget |
| A1 | 7.8% | self-relatable (determinism / null-op) |
| A2 | 22.2% | read-backable (write-read / canary) |
| A3 | 0.3% | conservation-bound (strongest) |

Full table, per-server breakdown, and the trusting-vs-skeptical-of-self-declared-hints sensitivity check: `data/processed/d1_bigrun2.log` (search `AUDITABILITY CLASS DISTRIBUTION`).

### Scale run — live audit (does the defense actually catch anything)

Sampling frame: the **official MCP Registry** (`registry.modelcontextprotocol.io`), walked in full — 26,589 entries, 8,691 runnable-without-credential candidates. This replaced an earlier, much weaker GitHub-keyword-search pool (32 candidates) after direct pushback that the earlier pool wasn't a defensible sample for a top-tier venue.

**Funnel:**

| Stage | Count | % of candidates |
|---|---|---|
| Registry candidates | 8,692 | 100% |
| Actually launched | 4,121 | 47.4% |
| Usable write tool, both trials completed ("ok") | 1,242 | 14.3% |
| Attack actually **landed** (L1) | 128 | 1.5% |

**Headline result, honest and triple-checked:**

| Level | Landed | Raw "detected" | **True detection (after cross-check)** |
|---|---|---|---|
| L1 (forge response) | 128 | 2 (1.6%) | **0/128 = 0%** |
| L2 (+ skim, launder itemised) | 127 | 2 (1.6%) | **0/127 = 0%** |
| L3 (+ launder aggregate — Theorem 1's ceiling) | 127 | 2 (1.6%) | **0/127 = 0%** |

**FPR (false alarm on an honest server): 16/1209 = 1.3%** — well under a 5% bar, and stable across all three tamper levels (measured on the honest trial, level-independent).

The "cross-check" that turned 1.6% into 0% at every level: the same 2 flagged servers (`io.github.Dave-London/npm`, `io.github.Dave-London/pare-npm`) are *also* flagged on the **honest** trial — a persistently broken relation pairing (an `install`/`list` tool pair that happens to share a field name, `registry`, without the read actually reflecting per-call state), not a real catch. Once excluded, not one clean "silent on honest, caught on tampered" case exists anywhere in the corpus, at any level.

Full method, per-server examples, and the before/after comparison against the buggy pre-fix data (47.5% FPR, apparent-but-spurious 57.6% detection) are in the memory file `mcp_scale_run_status.md` and this conversation's transcript. `data/processed/scale_run.json` (L1, full corpus) and `data/processed/scale_run_levels.json` (L2/L3, the 1,242-server subset) are the raw data.

---

## 3. Gaps found (in order of how much they cost, biggest first)

1. **Relation *derivation* is the real bottleneck, not the checking logic.** `measure/classify.py`'s `derive_for_server` links a write to a read whenever they share *either* an output-field name *or* merely a noun in their name/description. A noun-only pairing (`create_order` ↔ `search_products`, sharing only "product") routinely names a reader that cannot possibly corroborate the write — wrong resource type, different index, eventually consistent. Even *field-name* overlap isn't sufficient (`post(url=X)` / `get()` on a generic HTTP-client-style server: both declare `url`, but `get` is not tied to what a specific `post` call did). Fixed the noun-only case this session (downgrade to non-counted warning); the field-name-but-still-wrong case is not yet fixed and is very likely why L1 detection is 0% rather than merely low.

2. **The tampering proxy's attack vocabulary is narrow.** `TARGET_FIELDS`/`NUMERIC_FIELDS` in `mcpmut/proxy.py` are a fixed, small English-word list (`path`, `recipient`, `url`, `amount`, …). 90% of real write tools (1,114/1,242) had **no field the proxy could even divert** — the attack never executed at all, regardless of what the auditor could or couldn't catch. This bounds every detection number above: they are measured on the ~10% of servers where an attack was even possible to mount with the current proxy.

3. **R2 (conservation) is domain-conditional, and that domain is rare in practice.** R2 needs a write tool with a numeric, money/quantity-shaped argument AND a derivable quantity-reader relation. Only 84/1,242 servers (6.8%) have *any* tool classified A3 anywhere; of the 127 servers where an L2 attack landed, only 14 (11%) even had an A3 tool present at all. The 0% L2/L3 detection therefore reflects two separate facts: R2 rarely applies to real MCP tools, *and* in the few cases sampled here it still didn't produce a clean catch — the second claim has too small an n to generalize on its own.

4. **Three infrastructure bugs**, all fixed and documented (Docker `HOME` misconfiguration filling the host disk; non-atomic checkpoint writes destroying a completed run mid-crash; a leaked-container bug from killing the wrong name on a timeout). These cost real time this session but are now closed and don't affect the numbers above — noted here only because "we found and fixed real bugs by running at scale" is itself a defensible methods claim for the paper.

---

## 4. Model/output artifacts, where they live

- `experiments/demo_mba.py` — the original hand-built cost-ladder demo (4 domains we wrote ourselves; still valid as a controlled illustration, but not evidence about the real world)
- `src/mcpaudit/` — the deployable auditor (`Auditor`, relation derivation via `measure/classify.py`, policy)
- `src/mcpmut/proxy.py` — the declaration-driven adversary (`TamperingProxy`, L1/L2/L3 ladder)
- `docker/run_one.py`, `experiments/run_scale.py`, `experiments/run_scale_levels.py` — the real-server harness (Docker-sandboxed, resumable, atomic-checkpointed)
- `data/processed/d1_corpus.jsonl` — 18,566 statically-extracted tools
- `data/processed/scale_run.json` / `scale_run_levels.json` — the live audit results (L1 full corpus; L2/L3 subset)
- `data/processed/registry_candidates.json` — the 8,691-server sampling frame
- 94 passing unit tests (`tests/`) pin the fixed bugs as regressions

---

## 5. Where this leaves the paper — options, not a decision

The measurement half (D1 + the scale run) is strong and close to submittable on its own (Paper A in docs/20's framing) — a real, defensible, honestly-reported result: most MCP tools are unauditable by construction (A0 69.7%), and the specific defense mechanism proposed for the auditable rest catches essentially nothing in the wild, for reasons now understood mechanistically rather than mysteriously.

The open question is what to do about the **defense** half. Three non-exclusive directions the data supports, without picking one:

**A. Fix relation derivation, re-measure.** Attack the actual bottleneck (finding #1) — replace noun/field-name matching with something that verifies the reader genuinely reflects the *specific instance* the write touched (e.g. requiring the write's return value or an identifier to appear in a follow-up read keyed by that identifier, not just field-name co-occurrence). Re-run the same 1,242-server harness. This is the most direct way to find out whether the 0% is a derivation-layer artifact or a deeper ceiling.

**B. Report the negative result as the finding.** Reframe the paper around "we built the most complete zero-cooperation behavioral auditor proposed to date, evaluated it honestly at real scale, and it does not work — here is exactly why, mechanistically, with the ecosystem prevalence numbers to back each reason." This is a legitimate, publishable systematization/measurement contribution and doesn't require the defense to succeed. Lowest additional build cost; highest need for very careful, unflinching writing.

**C. Broaden the taxonomy.** If direction A still comes back weak, the R2/R3 "conservation" idea itself may need generalizing beyond money-shaped quantities (finding #3) — e.g. any monotonic or set-membership invariant a resource obeys, not just numeric conservation — before re-measuring again.

None of these has been started. This document is the handoff point: everything above is what exists and what it means; the next step is picking (or combining) a direction and building against it.

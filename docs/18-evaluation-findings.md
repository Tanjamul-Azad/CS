# Evaluation Findings

Results from `experiments/run_eval.py` (detection, false positives, overhead) and `experiments/run_probe_aware.py` (adaptive adversary).

Simulated servers; no LLM in the loop yet. See [`17-status.md`](17-status.md) for what that does and does not license us to claim.

---

## 1. Detection across four domains

The same malicious effect in every cell. The declaration never changes, so the deployed defenses are inspecting an object that is byte-identical between honest and compromised servers.

| Domain | Adversary | LOC | none | hash-pin | response-val | **MBA** |
|---|---|---|---|---|---|---|
| banking | forge response | 3 | 0% | 0% | 0% | **100%** |
| banking | + shadow ledger | 9 | 0% | 0% | 0% | **100%** |
| banking | + shadow balance | 17 | 0% | 0% | 0% | 0% |
| email | forge response | 3 | 0% | 0% | 0% | **100%** |
| email | + shadow sent-list | 9 | 0% | 0% | 0% | 0% |
| files | forge response | 3 | 0% | 0% | 0% | **100%** |
| files | + shadow directory | 9 | 0% | 0% | 0% | 0% |
| compute | forge response | 3 | 0% | 0% | 0% | **100%** |
| compute | + shadow job list | 9 | 0% | 0% | 0% | **100%** |
| compute | + shadow credits | 17 | 0% | 0% | 0% | 0% |

**hash-pin is structurally zero, not merely low.** Every adversary here leaves the declaration untouched, so the consensus MCP defense cannot fire even in principle. This makes the paper's gap executable rather than argued.

**email and files miss at 9 LOC for a real reason, not a bug.** `send_email(to, subject, body)` and `write_file(path, content)` declare no numeric field, so no conserved quantity exists and R2 is underivable. That mirrors the ecosystem: A3 = 0.4%, 32 conservation relations across 5,397 tools ([`15`](15-d1-findings.md)). The benchmark reproduces the property rather than assuming it away.

---

## 2. False positives — the result that forced a redesign

Measuring FPR against a deterministic single-client server is a tautology. Honest servers therefore run with **legitimate concurrent activity**: another client, a cron job, a human moving the same quantity.

### The naive check collapsed

| concurrency | FPR (banking) | FPR (compute) |
|---|---|---|
| 10% | 20.0% | 18.5% |
| 30% | 69.0% | 43.5% |
| 50% | 86.5% | 78.0% |

**At any detection rate, this is not a deployable detector.** We found it by attacking our own defense; otherwise a reviewer would have.

### Two fixes

**Reconcile against the itemised ledger, not against our own call.** Ask whether the quantity moved by the sum of every transaction the server *admits to*. Concurrent honest activity appears there too and cancels out. A skim does not appear there — that is what skimming means.

**Decline when the window is not quiet.** MCP has **no atomic multi-read**. The quantity and the ledger genuinely describe different instants, and no arithmetic reconciles them. So: read the ledger, read the quantity, read the ledger again; if it moved, **skip the check**.

> Under concurrency the conservation relation degrades to *"sometimes unavailable"* rather than *"often wrong."* That is the only acceptable direction for a security tool. A missed check costs coverage; a false alarm costs the user's trust, and they spend that once.

**Result: 0% FPR at 0 / 10 / 30 / 50% concurrency, detection unchanged.**

### A protocol recommendation falls out

Conservation auditing is concurrency-safe **only when the server exposes an itemised ledger of the conserved quantity**. Banking itemises `amount` per transaction but aggregates to `balance` — one quantity under two names — so a client cannot mechanically link them. **Name the itemised field and the aggregate relatably**, or conservation cannot be audited under concurrency at all.

---

## 3. Overhead

| Domain | extra tool calls per task call |
|---|---|
| email | 1.0 |
| files | 1.0 |
| banking | 7.0 |
| compute | 10.0 |

The stability double-read is not free, and domains with two quantity readers pay most. Reported as a real cost — the detection/overhead trade is the practitioner's to make, not ours to hide.

---

## 4. The probe-aware adversary — attacking our own defense

MBA assumes the server cannot distinguish an audit call from a task call. **That assumption is false, and our own fix made it worse.**

The auditor snapshots *before* the write, and since the stable-window fix it reads the ledger twice:

```
list_transactions, check_balance, list_transactions, transfer_money
\________________ the tell _____________________/
```

The prelude arrives while the server still gets to choose whether to cheat on the write that follows.

### Results (banking, 25 sessions × 40 calls)

| Arm | budget | thefts | caught | DR |
|---|---|---|---|---|
| blind attacker | 25% | 1000 | 262 | 26.2% |
| blind attacker | 100% | 1000 | 1000 | 100.0% |
| **probe-aware** | 25% | 547 | 0 | **0.0%** |
| **probe-aware** | 100% | 0 | 0 | 0.0% |
| **probe-aware vs decoy** | 25% | **0** | 0 | 0.0% |
| bold (knows decoys) | 25% | 1000 | 262 | 26.2% |

### Reading

**MBA's detection rate against a probe-aware adversary is exactly zero.** Not low — zero. It never cheats while watched, so there is nothing to detect on the calls we audit, and we do not audit the others. Stated plainly because it is the honest result.

**But detection is the wrong metric here.** Theft *volume* tracks the audit rate: 1000 → 547 → 232 → 56 → 0. Against this adversary the audit works as a **deterrent**, not a detector.

**Decoy auditing.** Snapshot on *every* call and complete the audit only sometimes, so the prelude carries no information about which calls are checked. Theft drops to **0 at every budget**, including 25%.

**The equilibrium — this is the actual result.** A rational adversary that works out decoys are in use stops treating the prelude as evidence, and is then exactly a blind attacker, caught at the audit rate:

| Adversary's choice | Outcome |
|---|---|
| believe the prelude | suppressed to **zero theft** |
| ignore the prelude | **detected at the audit rate** |

Neither branch is good for the attacker. That is a stronger and more honest claim than the "our detector works" it replaces.

### Caveats

- Suppression assumes a loss-averse adversary. One that values a single theft above the cost of being caught attacks regardless.
- The decoy's cost is a snapshot on *every* call, not only audited ones — overhead approaches the always-audit case even when the audit rarely completes.
- Only banking is swept so far.

### Two artifacts in the first run, fixed rather than reported

The auditor's probe-volume cap throttled mid-session and confounded the budget sweep. And the detector's history ran across the whole session, so it suppressed on everything — an attacker that never attacks is not probe-aware, it is broken, and it would have flattered our defense.

---

## 5. What this changes

The paper is no longer "we measured the ecosystem." It is:

1. **Attack** — 3 LOC defeats every deployed defense, across four domains
2. **Defense** — MBA catches it, and catches the 9-LOC escalation wherever conservation is derivable
3. **Limit** — 17 LOC wins, and Theorem 1 says one always will
4. **Practicality** — 0% FPR under concurrency, *after* our first design failed that test
5. **Adaptivity** — against a probe-aware adversary detection is zero, deterrence is total, and decoys force an unfavourable equilibrium

---

## 6. Reproduce

```bash
python experiments/run_eval.py --trials 30 --fp-trials 300
python experiments/run_probe_aware.py
```

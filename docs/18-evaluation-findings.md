# Evaluation Findings

Results from `experiments/run_eval.py` (detection, false positives, overhead), `experiments/run_probe_aware.py` (adaptive adversary), and `experiments/run_llm.py` (LLM in the loop).

Sections 1-5 use simulated servers; section 6 audits a real MCP server end to end. See [`17-status.md`](17-status.md) for what these results do and do not license us to claim.

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

## 5. LLM in the loop

Everything above used a scripted caller. This puts a real model in front of the server and lets it choose the tool calls. 320 episodes, `gpt-4o-mini`, 4 domains x (honest + 3 adversaries) x (audit off/on), 0 errors.

| Domain | Adversary | ASR | DR (audited) | utility off -> on |
|---|---|---|---|---|
| banking | L1 forge | 100% | **100%** | 100% -> 100% |
| banking | L2 shadow ledger | 100% | **100%** | 100% -> 100% |
| banking | L3 shadow balance | 100% | 0% | 100% -> 100% |
| email | L2 shadow sent-list | 100% | 0% | 100% -> 100% |
| files | L2 shadow directory | 100% | 0% | 100% -> 100% |
| compute | L2 shadow job list | 100% | **100%** | 100% -> 100% |
| *honest* | — | 0% | **0% FP** (n=40) | 100% -> 100% |

**The LLM harness reproduces the scripted harness exactly.** That agreement is the point: it means the earlier numbers were not an artifact of scripted calling.

### The result only an LLM run can produce

> **Utility delta: +0.0 points.** The agent completes its task at the same rate with auditing on as off.

This was previously a *claim* — the auditor's probes go to the server directly and never through the model, so the agent should not notice them. It is now measured.

Cost: **4.8 probe calls and 386 tokens per episode**; the full 320-episode run is roughly $0.02.

### Two deliberate design choices

- **The agent is not told the server might be compromised.** Telling it would measure prompt engineering rather than the auditor.
- **Ground truth stays with the out-of-band oracle.** The model's account of what happened is exactly as untrustworthy as the server's.

### A methodological caveat we hold ourselves to

At temperature 0 with one fixed phrasing per task, the agent is **deterministic**: all 32 cells showed *zero* within-cell variation and every episode took exactly 2 steps.

**So n=10 per cell is one outcome repeated ten times, not ten samples.** A confidence interval over it would imply sampling variation that does not exist. What 320 episodes establish is reproducibility and the absence of API flakiness — not robustness.

This is stated because it would have been easy, and wrong, to present "100% (n=10)" as though it carried statistical weight.

### 5.1 Variance probe — the outcomes hold

Re-run at **temperature 0.7** with **five distinct phrasings per task** (320 episodes, recorded per-episode):

| | temp 0, fixed phrasing | temp 0.7, 5 phrasings |
|---|---|---|
| cells with outcome variation | 0 / 32 | **0 / 32** |
| episode length | always 2 steps | **always 2 steps** |
| every headline number | — | **unchanged** |

Varying both the sampling temperature and the wording of the request moves nothing. At temperature 0 we could not distinguish *"the setup is deterministic"* from *"the result is robust"*; with the input actually varied and the outcomes still fixed, this is evidence for the second.

**What it means.** Detection depends on the *server*, not on how the agent phrases its call — which is what the design predicts, since relations are derived from declarations and checked against effects, neither of which the agent controls.

**What it does not mean.** These tasks are unambiguous and each domain exposes 3–4 tools. A larger tool surface, ambiguous instructions, or multi-step tasks would introduce agent-side variance that this design cannot exhibit. The claim is bounded to: *within this task difficulty, the result is phrasing- and temperature-stable.*


---

## 6. A real MCP server (E3)

Everything above used servers we wrote. This drives the **official filesystem reference server** over stdio — unmodified, real declarations, real files on a real disk — and interposes the **generic, declaration-driven tampering proxy** (`src/mcpmut/proxy.py`, the same one used against the benchmark, not specialised to this server). It plays the L1 adversary: divert the write to an attacker-controlled path, report the path that was requested.

| Run | probes | violations | outcome |
|---|---|---|---|
| honest real server | 1 | **0** | `confirmed via read_file` |
| tampering proxy | 1 | **1** | `read_file reports the target of this write does not exist, yet the response claimed success` |

Ground truth on disk confirms it: after the tampered run the sandbox contains `exfil.txt`, not the `report.txt` the response claimed.

From the live declarations the auditor derived **44 relations across 14 tools**, A0 = 0 — every tool on that server admits at least one check. Latency for the audit was ~0.05 s.

**Detection works against declarations we did not author, with no false alarm on the genuine server.**

### Three bugs only a live server could expose

Every simulated reader in the benchmark was parameterless and never returned an error. Real ones are neither, and each of these produced a *confident wrong answer* rather than a crash:

| Bug | Effect |
|---|---|
| The auditor called readers with **no arguments**. `read_file(path)` needs the path just written; called bare it errors. | False positive on an honest server |
| R1 required **every** write argument to appear in the read-back. `read_file(path)` returns *content* — the path is the query, not the answer. | False positive on every honest write |
| Error responses were treated as one thing. | Either loses all detections or fabricates them |

The third is the subtle one. An error means two opposite things depending on why:

- **"the file you just wrote is not there"** → the strongest evidence the auditor can obtain
- **"you called me wrong"** → no evidence at all

Collapsing them loses every detection *or* fabricates them. They are now separated: absence is a violation, an unusable probe is a warning that says the call went **unverified** rather than implying it was checked.

### Why the generic proxy matters

The adversary here is built from the live declarations alone — the same input the defense receives — so this is not the defense being tested against an attacker tuned to it. The proxy reproduces the benchmark's L1/L2/L3 detection semantics with no domain-specific code (`tests/test_proxy.py`), which is what lets a real third-party server sit on the same cost axis as the hand-written benchmark.

### Caveat

The proxy is still our own code, not a compromised third-party server found in the wild. What this establishes is that derivation and checking work against **declarations we did not write**; it is not a discovery of a real compromise.


---

## 7. What this changes

The paper is no longer "we measured the ecosystem." It is:

1. **Attack** — 3 LOC defeats every deployed defense, across four domains
2. **Defense** — MBA catches it, and catches the 9-LOC escalation wherever conservation is derivable
3. **Limit** — 17 LOC wins, and Theorem 1 says one always will
4. **Practicality** — 0% FPR under concurrency, *after* our first design failed that test
5. **Adaptivity** — against a probe-aware adversary detection is zero, deterrence is total, and decoys force an unfavourable equilibrium

---

## 8. Reproduce

```bash
python experiments/run_eval.py --trials 30 --fp-trials 300
python experiments/run_probe_aware.py
python experiments/run_llm.py --episodes 10                    # temperature 0
python experiments/run_llm.py --episodes 10 --temperature 0.7        --out experiments/results/llm_eval_t07.json             # variance probe
python experiments/run_live.py --sandbox /path/to/scratch      # real MCP server
```

`run_live.py` needs `pip install mcp` and Node (it launches the reference
server via `npx`). It only touches the sandbox directory you pass.

`run_llm.py` needs `OPENAI_API_KEY` in the environment or `.env`. It talks to
the chat-completions API over httpx, so any provider with the same shape
(Groq, vLLM, together) works by changing `base_url`.

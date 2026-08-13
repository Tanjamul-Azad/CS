# The Price of a Lie

**Auditing untrusted tool servers without their cooperation.**

MCP binds approval to a tool's *declaration* and execution to its *implementation*, and nothing binds those two together. A user approves `transfer_money` once; an autonomous agent then calls it at machine speed, forever, with no further review. If the implementation behind that declaration is swapped, every existing defense is looking at the wrong thing.

This is a distributed TOCTOU with no atomicity primitive. Check at *T₁*, use at *T₂*, untrusted party in between.

---

## The result, in one table

Same theft every time. The declaration never changes, so hash pinning is blind throughout. Only the attacker's machinery changes:

| Adversary | LOC | Shadow state | Caught by |
|---|---|---|---|
| forge the response | **3** | none | R1 write-read |
| + fake the ledger | **9** | ledger | R2 conservation |
| + fake the balance | **17** | ledger + balance | **nothing** |

Defenses do not stop the attacker. They **price** them.

The 17-LOC adversary wins, and Theorem 1 says one always will — that ceiling is stated in the abstract, not buried. The contribution is the *slope below it*, plus one empirical fact: documented real-world MCP compromises are 3-LOC-class patches that maintain no shadow state at all.

```bash
python experiments/demo_mcpaudit.py    # the ladder, through the deployable defense
python experiments/demo_theorem1.py    # response validation: 100% -> 0% against T2
python experiments/demo_mba.py         # relation-by-relation escalation
```

No API key needed. Nothing contacts a live server.

---

## Two theorems

**Theorem 1 — Transcript Indistinguishability.** A *passive* client cannot detect a server that performs a malicious effect while returning the honest response. Detection rate equals false-positive rate. Response validation is defeated by 3 lines.

**The escape:** the client is not passive. It is *authorized to call*. That moves the problem from observation, where the impossibility bites, to interrogation, where it does not.

**Theorem 2 — The Cost of Consistency.** A client that checks metamorphic relations forces a diverting server to lie *consistently* across all of them — that is, to maintain a simulated honest world. That burden is measurable, in lines and in shadow-state size.

---

## The constraint that shaped everything

**Zero cooperation.** Not from the server, not from its operator, not from any downstream provider.

An earlier design proposed receipt attestation and cross-channel verification. Both require cooperation nobody will give — banks will not sign receipts for your agent. That design was scrapped. Everything here works with declarations the server already advertises and calls the client is already authorized to make.

---

## `mcpaudit` — the deployable defense

```bash
PYTHONPATH=src python -m mcpaudit scan --tools tools.json
PYTHONPATH=src python -m mcpaudit scan --stdio "npx -y @modelcontextprotocol/server-filesystem /tmp"
```

Real output, against a real community server from the corpus:

```
  20 tools  A0=11  A1=0  A2=9  A3=0   (55% unverifiable)
  UNVERIFIABLE MUTATIONS: set_license, save_custom_rules

  class   deg  policy    tool
  A0        0  confirm   set_license  <-- unverifiable mutation
  A0        0  allow     estimate_cost
  A2        7  audit     list_sessions
  A2        1  audit     purge_sessions
```

### The safety rule that shapes the design

Auditing works by **calling tools**, and a probe write is a *real* write. An auditor that "tests" `transfer_money` has moved real money; one that probes `delete_file` has destroyed a real file.

So: **the auditor never issues a write the agent did not ask for.** Verification is built only from extra *reads*, and from reads taken before and after the agent's own writes. That costs coverage — synthetic canaries and null-op probes are off by default because both mutate — and it is the correct trade for something people run against production. `allow_probe_writes=True` opts back in, explicitly.

### What it will not pretend to do

A tool with no derivable relation (**A0**) cannot be checked, ever, at any budget. `mcpaudit` reports these loudly instead of implying coverage it lacks. For A0 the remedy is policy — restrict the call, or put a human in front of it — not detection.

---

## Auditability classes

Keyed on **relation degree**, which the client computes for itself. No assumptions about anyone.

| | Meaning |
|---|---|
| **A0** | no relation derivable — undetectable at any budget |
| **A1** | self-relatable (determinism, null-op) |
| **A2** | read-backable (write-read, canary) |
| **A3** | invariant-bound (conservation) — strongest |

The dangerous cell is **A0 ∧ mutating**: consequential *and* uncheckable. Default policy sends it to a human; strict mode denies it.

---

## Ecosystem measurement (D1)

```bash
python experiments/run_d1.py --target 500      # checkpoints; --resume to continue
python experiments/run_d1.py --report-only
```

Static extraction from public source. **No live server is ever contacted.** One GitHub trees call per repo, then unmetered raw fetches. Discovery stratifies by star bucket so the long tail is represented — A0 rate appears to track server tool-count, and sampling only the popular head would bias the headline toward auditability.

⚠️ **Numbers in `docs/13` are pipeline validation, not results** — a single repo of official reference servers, i.e. best case. Do not cite them. The full harvest is what the paper reports.

### Validation before any claim

```bash
python experiments/make_label_sample.py --n 300
python experiments/score_labels.py --a a.tsv --b b.tsv
```

Two annotators label independently against `docs/14-labeling-codebook.md`; the tool reports Cohen's κ, per-class precision/recall, and the **A0 bias** — the signed gap between classifier and humans. That bias applies directly to the headline and is reported beside it, never silently corrected.

---

## Layout

```
src/mcpaudit/     the deployable defense  (auditor, policy, CLI)
src/measure/      D1 instrument           (extract, harvest, discover, classify, report, agreement)
src/mcpmut/       benchmark               (mutations, adversary ladder, domains)
experiments/      runnable demos and harvest scripts
docs/00-14        research program, theory, threat model, lineage, codebook
paper/            references.bib -- 45 entries, all marked [U] unverified
```

Start with `docs/00-RESEARCH-PLAN.md`, then `docs/11-runtime-validation-design.md` (the defense) and `docs/12-intellectual-lineage.md` (what this subfield inherits from TOCTOU, metamorphic testing, BFT, and eight others).

---

## Status

Measurement instrument built and running. Two theorems stated, one proved and demonstrated. Deployable auditor works end-to-end against the full adversary ladder.

**Not yet done:** κ validation, extractor recall on real code, remaining tool domains, LLM-in-the-loop cost curve, T3 probe-aware adversary. Targeting a Tier-1 security venue; no workshop hedge.

MIT licensed. Group 13, UIU.

# 45 — Workstream A: pin-time effect templates (development result)

Plan: `docs/44-strengthening-plan.md`, frozen protocol
`artifact/template-generalization-plan.json`. Code:
`src/mcpgate/template_inference.py`, runners
`experiments/run_template_generalization.py` and `experiments/run_template_sql.py`.

## What changed in the method

Every contract before this was derived from honest runs of *the exact call
being admitted*. At deployment that call is new, so its honest run does not
exist. Now EffectSeal runs the pinned (approved) server version on perturbed
arguments once, at pin time, and infers one template per tool: which objects
change, how their paths are built from arguments, and how their content is
built from arguments plus bounded volatile spans. Each new call instantiates
the template into an ordinary tree contract at admission time.

- Anti-unification over argument-abstracted token sequences, star-aligned
  against the first training run.
- Argument transforms: identity, root-relative path, basename, stem, case, two
  slug forms (all found in real outputs).
- Clock values become shape-typed holes, bound at admission to the UTC date
  window of the admission clock; a date counts as a clock value only if it lies
  within a day of the training run's own clock.
- Enum fields, and fields whose perturbation makes the honest server refuse,
  are held fixed and discovered automatically; a call that differs in them is
  refused.
- Databases are serialized to canonical text (`sqlite_state_text`) and handled
  by the same machinery.

**Contract slack** is the number of bits an adversary can still choose while
conforming: 0 = L3, finite = L2, unbounded = L1. It turns the ladder into a
measured quantity.

## Results

These five filesystem and two SQLite servers are the **development set** (the
library was designed while inspecting their outputs). Held-out scoring waits for
the second frozen batch (workstream G).

### Run 1 (kept: `artifact/results/template_generalization_run1.json`)

- 54/54 landed attacks refused on held-out arguments; content-blind ablation 33/54.
- 12/48 honest false blocks, **all on ori-memory**: its `ops/daily.md` carries
  the constant epoch sentinel `date: 1970-01-01`, which inference had treated
  as a clock value and bound to the admission date.
- compose-mcp failed in the harness on an optional schema enum (`complexity`).

Both fixes are recorded in the plan's `development_changes` with regression tests.

### Run 2 (`artifact/results/template_generalization.json`, `..._sql.json`)

| Server | Honest held-out | False blocks | Slack (bits) | Landed | EffectSeal-T | Content-blind |
|---|---:|---:|---:|---:|---:|---:|
| filesystem-server | 12 | 0 | 0 (L3) | 15 | 15 | 9 |
| mcp-server-filesystem | 12 | 0 | 0 (L3) | 15 | 15 | 9 |
| ori-memory | 12 | 0 | 63.6 (L2) | 9 | 9 | 6 |
| compose-mcp | 12 | 0 | 62.2 (L2) | 6 | 6 | 3 |
| repomemory | 12 | 0 | 7.0 (L2) | 15 | 15 | 9 |
| mcp-sqlite3 | 12 | 0 | 0 (L3) | 9 | 9 | — |
| sqlite-mcp | 12 | 0 | 0 (L3) | 6 | 6 | — |
| **Total** | **84** | **0** | | **75** | **75** | 36/60 |

Four of the twelve honest calls per server used 3x longer text (scale shift).
Every pre-registered success criterion is met on the development set.

Where the slack lives: in ori-memory and compose-mcp, about 52 of the 62--64
bits (82--84%) are one sub-second ISO timestamp in an append-only log, even
with its date bound to the admission window; bound dates add about 1.6 bits
each, and each optional empty directory 1 bit (create or not). repomemory's
7 bits are exactly seven optional directories. The two plain file servers and both SQLite servers are exact.

### Oracle caveats (evaluator, not defense)

- Attacks that did not land: compose-mcp and sqlite-mcp *surfaced* the no-op
  as a protocol error (no false success, so nothing to prevent), which is correct.
- The six `sql_value` attacks changed state but did not meet the frozen
  evidence rule "honest value absent", because the shim writes
  `ATTACKER_<value>` and the honest value survives as a substring. EffectSeal-T
  refused all six. Post-hoc, with evidence "the exact honest row is absent",
  the SQL arm is 21/21 landed and refused. We report the frozen number and flag
  the correction as post-hoc.

## What this buys the paper

1. The deployment question ("where does the contract come from?") has an
   answer that fits the rug-pull threat model: derivation happens once against
   the approved version.
2. Slack gives the L1/L2/L3 ladder a number per tool, including where it is
   weak (timestamps).
3. The content-blind ablation (36/60) isolates the value of binding content,
   on held-out arguments rather than a fixed call.

## Next

- Adaptive attacks against slack (workstream D): hide a payload in timestamp
  holes; measure achieved bits against predicted slack.
- Held-out scoring on the second frozen batch (workstream G).

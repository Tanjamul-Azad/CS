# 38 — M4, second attack family: allowance exhaustion / replay

Written 2026-09-16. `25-research-program.md` §5's Permit rule has four
clauses — `Valid`, `Matches`, `Unused`, `Mediated`. `Unused(C)` (invocation
allowance remains) had never been tested against the M2-proper mediator
(`31`, `32`, `34`, `37`) before this. `25` §6 M4 also names "exhaust the
allowance" by name as an attack to attempt.

## The gap, found by inspection before running anything

`probe_m2.py`'s mediator has exactly one signal: does the staged effect
match the approved contract. A **replay** of an already-used, legitimate
authorization produces an effect that matches the contract by
definition — it's a copy of the first, legitimate use. A pure effect-diff
mediator therefore structurally cannot tell "the first, authorized use"
apart from "a replay of a use that already happened." `Unused(C)` is a
separate check this design never included.

**It didn't need to be built from scratch.** `src/mcpgate/allowance.py`'s
`AllowanceLedger` already exists, is already unit-tested
(`tests/test_allowance.py`), and is already wired into the *preliminary*
gateway (`src/mcpgate/gateway.py`) — a small state machine
(`AVAILABLE → RESERVED → COMMITTED/FAILED`) specifically designed around
the hard cases (concurrent calls racing for the last slot, a crash mid-
execution leaving an UNKNOWN outcome, a replayed `request_id` never
re-executing). It was simply never wired into the newer M2-proper
mediator, a different code path built later in this project.

## The attack

`experiments/boundary/probe_m4_replay.py`: the identical approved write
(same path, same content) submitted twice against one shared
staging/committed pair, under two conditions — no ledger in the path, and
`AllowanceLedger` wired in via `reserve()` before the write is even
staged.

## Result

```
[VULNERABLE (no ledger)]
  call 1: committed=True
  call 2 (replay): committed=True
  BOTH COMMITTED (double-spend shape): True

[FIXED (AllowanceLedger wired in)]
  call 1: committed=True
  call 2 (replay): committed=False   blocked_by=allowance
                    (execution allowance exhausted: 1/1 used for contract 682186adce6e)
  BOTH COMMITTED (double-spend shape): False
```

Without the ledger, both calls commit — the exact double-spend shape the
Permit rule's `Unused(C)` clause exists to prevent. With
`AllowanceLedger.reserve(contract_id, request_id, max_invocations=1)`
called before staging, the second call is refused outright — it never
reaches the staging step, let alone the diff.

## What this establishes

- **A real, previously-unstated gap in the M2-proper mediator**: every
  prior M2 result (`31`, `32`, `34`, `37`) measured contract-matching and
  request-shape correctness; none exercised allowance enforcement,
  because the mediator never included it. This document is the first to
  state that plainly rather than leave it implicit.
- **The fix required no new design.** `AllowanceLedger`'s own stated
  invariants (`allowance.py`'s own docstring: "a replayed request must
  not execute twice, whatever it is told") already anticipated exactly
  this attack, at the ORIGINAL gateway. The gap was integration, not
  design.
- **This is a real, working reuse of already-verified project
  infrastructure** — the ledger's own correctness (concurrent reservation,
  crash semantics) is not re-verified here; that was already covered by
  `tests/test_allowance.py`. What's new here is confirming it closes a
  concrete attack against the newer mediator it had not previously been
  connected to.

## What this does not establish

- **Concurrent replay** (two calls racing for the same slot
  simultaneously, not sequential as tested here) — `AllowanceLedger`'s own
  design explicitly handles this (`reserve()` is one atomic
  check-and-take under a lock), but this probe ran the two calls
  sequentially, not truly concurrently. Not yet tested against the
  mediator specifically.
- **Crash semantics** (a process that dies mid-execution, leaving a slot
  `RESERVED` / `UNKNOWN`) — `AllowanceLedger` models this explicitly and
  it is unit-tested in isolation, but not exercised here against the
  M2-proper mediator's own staging/commit flow.
- **Durability.** `allowance.py`'s own docstring states this plainly:
  "this is in-process state. It does not survive a restart." Unchanged by
  this integration.

## Reproduce

```bash
python experiments/run_m4_replay.py
```

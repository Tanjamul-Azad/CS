# 34 — M2 corner cases: honest workflows beyond "write one file, once"

Written 2026-09-16. Every scenario in `31`/`32` writes exactly one file,
exactly once. `25-research-program.md` §5 names two failure modes to
attack directly rather than assume away: "an honest file save may be
several writes plus a rename," and "one server process serves many
calls. Attributing an observed effect to THE call that authorized it is a
real problem." This closes both — one with a clean pass, one with a real,
demonstrated failure mode.

## Part 1 — Shaped honest effects: four corner cases, all pass

`experiments/boundary/probe_m2_corner_cases.py` (driver:
`experiments/run_m2_corner_cases.py`) reuses the exact post-fix mediator
logic from `probe_m2.py` against four honest behaviours no other scenario
exercises:

| Scenario | What it does | Result |
|---|---|---|
| `temp_write_rename` | Write to `report.txt.tmp`, then rename into place — the single most common real save pattern, two filesystem operations for one logical save | **PASS** — commits, content matches exactly |
| `empty_content` | Approved content is `""` — an edge case for any check written as `if content:` rather than `if content is not None` | **PASS** — commits correctly, not mistaken for "nothing happened" |
| `large_content` | A ~2.3MB payload, not the few-byte strings every other probe uses | **PASS** — commits correctly at real size |
| `write_then_overwrite` | Two honest writes to the SAME path in one invocation; only the final state should be checked | **PASS** — final content is what's checked and committed, not an intermediate draft |

All four commit with `completion=COMPLETED` and byte-exact committed
content. The mediator's diff (`staged_after.get(path) == content and
set(staged_after) <= {path}`) is agnostic to HOW the final state was
reached — temp+rename, one write, or several — which is exactly why it
handles all four without any scenario-specific code. This closes the
multi-write-plus-rename gap `31`/`32` both named as untested.

## Part 2 — Effect-to-call binding: a real failure mode, found by testing it rather than assuming it away

Every M2 probe in this project gives each invocation its own staging
directory — which sidesteps the effect-to-call binding problem by
construction, not by solving it. `experiments/boundary/
probe_m2_shared_staging.py` deliberately removes that isolation to find
out what happens without it: **one** server process, **one shared**
staging directory, **two sequential** invocations with different
approved contracts — call A approved to write `a.txt = "first"`, call B
approved to write `b.txt = "second"`, no reset of staging between them
(exactly what a real, long-lived server handling many calls would look
like without per-call isolation).

**Prediction, stated before running it**: a mediator whose contract check
is "does staging contain EXACTLY the approved path" will see call A's
leftover file as an unexpected extra path when checking call B's diff,
and wrongly discard call B's own, entirely honest effect.

**Result — the prediction held, exactly**:

```json
{
 "call_a": {"staged_keys": ["a.txt"], "matches_contract": true, "decision": "commit"},
 "call_b": {"staged_keys": ["a.txt", "b.txt"], "matches_contract": false, "decision": "discard"},
 "committed_final_state": {"a.txt": "first"},
 "b_wrongly_discarded_due_to_a": true
}
```

Call B did nothing wrong. Its own write of `b.txt = "second"` landed
exactly as approved. It was discarded anyway, solely because call A's
already-committed artifact was still visible in the shared staging
directory when B's diff ran (`set(staged_after) <= {approved_path}` sees
`{a.txt, b.txt} ⊈ {b.txt}` and fails). This is an **honest-utility
failure, not a security hole** — nothing unauthorized reached the
committed store — but it is a real, demonstrated cost: a mediator that
does not isolate per invocation will reject correct work as a side effect
of a completely unrelated prior call.

**Why this matters beyond one bug.** This is exactly the empirical
argument for why every other M2 probe in this project isolates staging
per invocation (`/staging/{scenario}`, freshly reset each trial) — not
asserted as good practice, demonstrated as necessary by showing what
breaks without it. It is also the concrete, measured instance of the
abstract failure mode `25` §5 names by name ("attributing an observed
effect to THE call that authorized it is a real problem") — now a real
data point, not only a predicted risk.

**What this does not establish**: a fix. The obvious mitigation —
per-invocation staging directories, which every other probe here already
uses — is not itself proven sufficient for a real, concurrent, multi-call
server (two calls arriving genuinely in parallel, not sequentially as
tested here, would need synchronization this probe does not test). Listed
as open in `35-mitigation-strategies.md`.

## Reproduce

```bash
python experiments/run_m2_corner_cases.py
python experiments/boundary/probe_m2_shared_staging.py   # run via docker, see run_m2_boundary.py for the invocation pattern
```

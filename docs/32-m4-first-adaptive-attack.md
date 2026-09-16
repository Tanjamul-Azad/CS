# 32 — M4, first adaptive attack: a real TOCTOU race, found, fixed, re-verified

Written 2026-09-16. `25-research-program.md` §6 M4: "an adversary that
knows the contract and the boundary... report what succeeds." This is
the first concrete instance — not against a generic sandbox, but against
this project's own M2-proper mediator (`31-m2-proper.md`), written by an
adversary that has read that mediator's actual code.

## The gap, found by reading our own code rather than assuming it away

`probe_m2.py`'s `run_m2` makes one commit decision from two independent
filesystem reads:

```python
staged_after = observe(staging)              # READ 1 -- the diff decision
if matches_contract:                          # decided from READ 1
    shutil.copy2(staging / path, COMMITTED / path)   # READ 2 -- independent
```

Nothing locks the file between READ 1 and READ 2. An adversary that knows
the mediator sleeps ~0.8s before deciding (this project's own published
design, not a guess — `31` §"Design", step 3) can write approved content
first, then race the file's content against that exact window, hoping
`shutil.copy2`'s own read lands on attacker content after the diff's read
already approved something else.

## The attack

`experiments/boundary/adaptive_server.py`: writes the approved content,
then spawns a detached background process that toggles the file between
approved and attacker content via atomic rename (`os.replace`) for 1.3
seconds — comfortably longer than the mediator's known 0.8s window, so
the race is attempted continuously rather than timed to one guess.
Deliberately kept separate from `malicious_server.py` (which predates the
M2-proper mediator and so cannot be "contract-aware" by construction),
so this new adversary cannot silently change the already-published
preliminary-probe result.

`experiments/boundary/probe_m4.py` runs the real mediator logic (copied
from `probe_m2.py`, not imported, so a fix to one is never silently
inherited by the other without being separately verified) 20 times per
condition — a race is a probability, not a yes/no fact, so one trial
either way would misrepresent it.

## Result: the attack works, 1 in 4 times

```
VULNERABLE (shutil.copy2, independent re-read):  5/20 trials won, 25%
FIXED      (commit bytes already read for the diff): 0/20 trials won, 0%
```

Five of twenty trials landed attacker-controlled content (`"TOCTOU-
ATTACKER-PAYLOAD"`) in the committed store, despite the diff having read
and approved `"quarterly numbers"` moments earlier — a real, reproducible
violation of the mediator's own stated guarantee, on this project's own
code, found by an adversary designed with knowledge of that code's actual
timing.

## The fix, and why it is re-verified rather than assumed to work

```python
# before (vulnerable)
shutil.copy2(staging / approved_path, COMMITTED / approved_path)

# after (fixed)
(COMMITTED / approved_path).write_text(staged_after[approved_path], encoding="utf-8")
```

Commit the bytes **already read** for the diff decision — never re-open
staging from disk at commit time. There is then only one read per
invocation, so there is no second moment for a race to target. Re-run
against the identical attack, same 1.3s timing budget, same 20 trials:
**0/20**. This is the same discipline this project has applied to every
prior instrument bug (the `isError` field-name bug, the `attack_landed`
ground-truth bug, the M2 scoring bug in `31`) — a fix is not reported
until the same test that found the bug is re-run against it and shows
zero.

`experiments/run_m2_boundary.py` was re-run after the fix and produces
byte-identical decision outcomes to the ones already published in `31` —
the fix changes *how* the mediator writes committed bytes, not *which*
scenarios it commits or discards, so `31`'s reported numbers stand
unchanged.

## What this does and does not establish

- **Does**: give M4 a first, concrete, positive result — not "no attack
  found" but a real one, on real code, with a measured win rate, a fix,
  and a re-verified win rate of zero against the identical attack.
- **Does not**: establish the mediator is now race-free in general. This
  closes the ONE race this specific adversary targeted (the diff-vs-copy
  double-read). Other TOCTOU windows may exist elsewhere in the same
  design (e.g. between the initial `observe()` at trial start and the
  post-write grace sleep) and were not searched for here.
- **Does not**: test the "encode the effect in an unmediated channel,"
  "exhaust the allowance," or "degrade utility until disabled" attack
  families `25` §6 M4 also names. This is one adaptive strategy out of
  several the milestone specifies, not the milestone closed.

## Reproduce

```bash
python experiments/run_m4_adaptive.py
```

Runs both the vulnerable and fixed mediator logic, 20 trials each,
against the identical attack, and reports both win rates side by side.

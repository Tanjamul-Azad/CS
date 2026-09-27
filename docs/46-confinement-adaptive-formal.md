# 46 — Workstreams C, D, E and the development history of A

Plans: `artifact/confinement-plan.json`, `artifact/adaptive-templates-plan.json`,
`artifact/template-generalization-plan.json` (see its `development_changes`).
Every run is kept under its run number in `artifact/results/`.

## A — development history after doc 45

Doc 45 reported run 2 (0/84 false blocks). The adaptive workstream then
exposed two things run 2 could not, because its held-out arguments were drawn
from the same random-letter distribution as training:

| Change | Found by | Failure | Fix |
|---|---|---|---|
| 3 | adaptive run 1 | slug variants coincide on letter-only values; the template picked the wrong one and refused the honest exemplar (underscores) | version space of transforms + punctuation in perturbations + strict slug |
| 4 | adaptive run 2 | ori-memory's log line depends on a classifier over the title ("low" vs "high" confidence); random training only reached "low" | train on the exemplar + natural-word perturbations; 4 held-out calls use natural text |

Run 3 (after change 3) reproduced run 2 exactly. **Run 4** (current):

| Server | Honest | False blocks | Slack (bits) | Landed | Refused |
|---|---:|---:|---:|---:|---:|
| filesystem-server | 12 | 0 | 0 | 15 | 15 |
| mcp-server-filesystem | 12 | 0 | 0 | 15 | 15 |
| ori-memory | 12 | **1** (natural text) | **841** | 9 | 9 |
| compose-mcp | 12 | 0 | 62.2 | 6 | 6 |
| repomemory | 12 | 0 | 7.0 | 15 | 15 |
| mcp-sqlite3 | 12 | 0 | 0 | 9 | 9 |
| sqlite-mcp | 12 | 0 | 0 | 6 | 6 |
| **Total** | **84** | **1 (1.2%)** | | **75** | **75** |

The honest reading: **servers whose output depends on semantic properties of
the input (here, a confidence classifier) are where template inference is
weakest** — they get large slack (ori 841 bits) and can still produce a false
block on input the training did not cover. Random perturbation alone hides
this; the earlier 0-false-block result on ori-memory was optimistic.

## C — confinement (`artifact/results/confinement.json`)

Silent escape (honest write in staging + copies to `/world`, `/tmp`, `/etc`,
`/app`), five filesystem servers, 3 repetitions.

| | Unconfined | EffectSeal boundary |
|---|---:|---:|
| Escape reached a path outside staging | 15/15 | **0/15** |
| Admission accepted the staged result of an escape run | 15/15 | 15/15 |
| Honest completion | 15/15 | 15/15 |

Admission alone does not prevent an outside effect (it accepted all 15
unconfined escapes, whose staged state was honest); the read-only-root,
no-network, staging-only boundary did, at no honest-completion cost on these
servers. `/etc` was never writable (non-root user). A first attempt was
stopped and discarded: the probe did not forward the escape targets to the
server, so even the control showed no escape.

## D — adaptive attacks on templates (run 3 is the valid one)

Run 1 lacked an honest control; runs 1–2 had ori-memory's honest exemplar
refused (changes 3 and 4 above), so their ori rows cannot be attributed to the
attacks. In run 3 all three servers admit their honest control.

| Server | Covert (payload in timestamp digits) | Over-slack (letters) | Log injection | Predicted slack |
|---|---|---|---|---:|
| ori-memory | admitted by both; 49.8 bits achieved | template refuses 3/3; fixed-call admits 3/3 | template refuses 3/3; fixed-call admits 3/3 | 841 |
| compose-mcp | admitted by both; 49.8 bits achieved | template refuses 3/3; fixed-call admits 3/3 | template refuses 3/3; fixed-call admits 3/3 | 62.2 |
| filesystem-server | no timestamps: nothing to rewrite | nothing landed | no log files | 0 |

- Slack is an honest upper bound: the covert channel carried 49.8 bits per
  timestamp, inside the predicted slack, and the template admitted it, as stated
  in advance. This is the residual risk of L2 contracts, now quantified.
- Anything outside the hole's class or outside the template is refused, while
  the fixed-call contract of the matched evaluation admitted it wherever the file
  was UNKNOWN (unconstrained).

**Pin-time poisoning** (server malicious from the start, noisy during training):

| Server | Honest slack | Poisoned slack | 128-bit budget refuses poisoned? | Structural policy (post-hoc): honest / poisoned |
|---|---:|---:|---|---|
| ori-memory | 841 | unbounded | yes | **rejects honest** / rejects |
| compose-mcp | 62.2 | 435 | yes | accepts / rejects |
| filesystem-server | 0 | 97 | **no** | accepts / rejects |

Neither pin-time policy is clean. The pre-registered budget misses poisoning of
an exact server (0 -> 97 bits stays under 128). The post-hoc structural policy
(every hole must be a clock value) catches all three poisoned templates but also
rejects ori-memory's honest template. A relative rule (flag any template whose
slack exceeds a re-pin of the same version) or pinning from two independent
sessions are the natural next designs; neither is tested yet. Both policies are
evaluated unbiasedly only on the held-out batch (workstream G).

## E — formal model (`formal/`)

`EffectSeal.tla` models the ledger (reserve/commit/fail/crash), the untrusted
writer (may write any value while alive, and may survive quiescing), the single
read, and promotion. It is checked with **TLC** (tla2tools.jar v1.7.4, official
GitHub release, SHA-256 936a2620...0e88; logs in `formal/tlc/`) and with
`check_model.py`, an independent explicit-state mirror of the same actions and
invariants. **The two agree exactly**, including the distinct-state counts of
the two passing configurations (1,387 and 1,027). Bounds: 3 requests,
allowance 2, at most 2 executions per request (`StateConstraint`).

| Configuration | States | Result |
|---|---:|---|
| Full | 1,387 | all invariants hold, with escaped writers |
| No same-read (commit re-reads staging) | 1,657 | `TrustedOnlyAccepted` fails: Reserve, Write, Stop, Read, Write, Commit |
| Non-atomic reservation | 12,167 | `AllowanceBound` fails: CheckRoom, CheckRoom, TakeSlot, TakeSlot |
| No replay guard | 15,694 | `ExecAtMostOnce` fails: ..., Refuse, Replay |
| No writer quiescing | 1,027 | all invariants hold |

The last row sharpens a claim in the draft: admission *safety* rests on the
same-read commit alone, even if writers escape; stopping writers is needed for
a complete, non-torn result, not for safety.

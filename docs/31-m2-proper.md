# 31 — M2 proper: the untrusted server performs its own effect

Written 2026-09-16. Closes the specific gap `25-research-program.md` §6
called out by name: `run_boundary_probe.py`'s result was a **preliminary
control experiment**, not M2, because the gateway performed the approved
effect on the server's behalf through `FilesystemExecutor` — the server
never had write access at all, so "the authorization-to-boundary
translation problem — the actual research question" was untested. This
document reports what happens once the server genuinely performs the
effect itself, confined by a real, generic OS boundary.

## Design, implemented literally from `25` §6

`experiments/boundary/probe_m2.py`, driven by `experiments/
run_m2_boundary.py`, run as root inside the project container so it can
own the committed store while the untrusted server drops to a separate
`sandbox` user (`preexec_fn` + `setuid`/`setgid`, unchanged from the
preliminary probe).

1. Each invocation gets an isolated **staging** workspace,
   `/staging/{scenario}`, owned by `sandbox`, mode `0700`. The server can
   read/write/create anything inside it — no mediation in this path.
2. The untrusted server (`malicious_server.py`, byte-for-byte unchanged
   from the preliminary probe — same fourteen scenarios, same bypass
   techniques) writes, symlinks, forks children, whatever the scenario
   calls for, inside that workspace.
3. When the call returns, plus the same 0.8s grace window the preliminary
   probe used for near-synchronous background writes, a trusted mediator
   (this process, running as root) reads the workspace.
4. The diff is checked against the contract: does the workspace hold
   **exactly** the approved path with the approved bytes, and nothing
   else?
5. Exact match: the mediator itself — not the server — copies the
   approved file into a **separate**, root-owned `/committed` store the
   server has **zero** permission on (mode `0755`; `sandbox` falls under
   "other": read+execute, no write). Mismatch: nothing is copied: the
   whole transaction is discarded.

Because only the mediator's own copy ever writes into `/committed`, and
it only ever copies the single verified path+content, the committed store
cannot hold anything unauthorized unless the mediator's own logic is
wrong — a structural property, not just an empirical one.

**Post-commit tampering is tested against the committed store
specifically**, not staging: `rename_after_write` / `hardlink` /
`delete_after_write` are sent as a second message with `root` pointed at
`/committed` (matching `malicious_server.py`'s existing `handle_post`),
*after* the mediator has already decided and copied. This is the one
place the preliminary probe's finding genuinely reproduces here, but for
a methodologically cleaner reason — see below.

**Undefended control, unchanged in spirit**: one shared, world-writable
area, no staging, no mediator, the server's own proposal is carried out
directly and immediately. Prevention coverage is defined only over
attacks this control actually demonstrates landing, exactly as the
preliminary probe defines it.

## A real bug this took two attempts to score correctly

The first run scored every scenario the contract correctly discarded
(`wrong_path`, `content_substitution`, `same_dir_extra_file`, …) as
confinement `UNKNOWN` instead of `CONFINED` — because the scoring
function only checked "before state equals after state," which is also
true of `silent_noop` (nothing ever attempted). Those are not the same
event: one is the boundary actively catching a real, non-empty attempt
sitting in staging; the other is a server that simply declined to act,
which blocking cannot take credit for. Fixed by keying the distinction
off whether `staging` held anything at all, not off the committed store's
state alone. Caught by reading the first run's actual output rather than
trusting the scoring function once it ran without crashing — the same
discipline this project has applied to every prior instrument bug.

## Result

```
scenario                undefended  m2_defended    completion  blocked by
----------------------------------------------------------------------------------------------------
honest                    CONFINED     CONFINED     COMPLETED  not applicable
wrong_path                VIOLATED     CONFINED NOT_COMPLETED  contract check (staging diff)
content_substitution      VIOLATED     CONFINED NOT_COMPLETED  contract check (staging diff)
hidden_extra_field        CONFINED     CONFINED     COMPLETED  not applicable
same_dir_extra_file       VIOLATED     CONFINED NOT_COMPLETED  contract check (staging diff)
symlink_escape            VIOLATED     CONFINED NOT_COMPLETED  contract check (staging diff)
rename_after_write        VIOLATED     CONFINED     COMPLETED  OS permission (on the committed store)
hardlink                  VIOLATED     CONFINED     COMPLETED  OS permission (on the committed store)
delete_after_write         UNKNOWN     CONFINED     COMPLETED  OS permission (on the committed store)
preopened_fd              VIOLATED     CONFINED NOT_COMPLETED  contract check (staging diff)
child_process              VIOLATED     CONFINED NOT_COMPLETED  contract check (staging diff)
background_write          VIOLATED     CONFINED NOT_COMPLETED  contract check (staging diff)
error_after_effect        VIOLATED     CONFINED NOT_COMPLETED  contract check (staging diff)
silent_noop                 UNKNOWN      UNKNOWN NOT_COMPLETED  not applicable
```

Prevention coverage: **10/10 (100%)** of attacks the undefended control
demonstrated landing. `hidden_extra_field` and `delete_after_write`
(undefended) still contribute nothing to that denominator, for the same
reason as before — they never landed even without a defense.

## The finding that matters: mechanism attribution flips

The preliminary probe found 8 of 10 landed attacks blocked by **OS
permission** and 2 by the **contract check**. Here, with the server
genuinely holding write authority over its own workspace, that ratio
**inverts**: **8 of 10 are blocked by the contract check** (the staging
diff refuses to commit anything that isn't exactly the approved path and
bytes), and only **2 of 10** — `rename_after_write` and `hardlink` — are
blocked by OS permission, and only because that permission protects the
**already-committed** store, not the server's own writable staging area.

This is not a contradiction of the earlier result; it is the actual
research question the preliminary probe couldn't ask. Once you give the
untrusted process the real execution authority M2 requires, an OS
permission boundary drawn around its own workspace stops doing most of
the confining — the workspace is, correctly, writable by the process
that needs to do real work in it. What confines the outcome instead is
the **contract's own diff-and-discard**, checked after the fact against
exactly what ended up on disk. OS permission's remaining job shrinks to
protecting the *final*, already-decided artifact from tampering — which
is still real, and still necessary (`rename_after_write`/`hardlink`
against the committed store fail with a genuine `PermissionError`, not a
simulated one), but it is a smaller job than the preliminary probe's
numbers suggested, because that probe never let the server hold
authority in the first place.

## The honest limit this design has, found by pre-registering it before running

`hidden_extra_field` **commits** here: `confinement=CONFINED`,
`completion=COMPLETED`, `decision=commit`. This was predicted in the
probe's own docstring before the run, not discovered after and rationalized:
a mediator that diffs FILE STATE, per `25` §6 step 5's own definition, has
no visibility into the raw MCP request's argument shape — only the effect
it produced. The preliminary probe's gateway design checked the
**proposal** against the contract before ever executing (`Matches(a, C)`,
`25` §5), which is exactly how it rejected this same scenario. A pure
effect-diff mediator cannot do that: an extra field that never manifests
as a file-level change is invisible to it. This is `25` §3.1's
"a boundary sees effects, not requests" limitation, now confirmed on real
filesystem state rather than only argued in the abstract — and it is a
genuine, load-bearing gap in the staging-and-diff design specifically,
not a bug to patch quietly. A production version of this mechanism would
need to check the proposal's argument shape too, before performing
anything, combining both layers rather than relying on effect-diffing
alone.

## Where this leaves M2

**The architectural gap is closed**: the untrusted server performs the
effect; a generic boundary (staging ownership + a trusted diff-and-commit
mediator) does the confining; no per-tool executor is anywhere in the
path. All three of `25` §6's pre-registered thresholds are met on this
run:

| Threshold | Required | Measured |
|---|---|---|
| Prevention coverage | ≥ 90% | **100%** (10/10) |
| UNKNOWN rate | ≤ 20% | **7.1%** (1/14, `silent_noop`) |
| Honest utility | within 5pp of undefended | **0pp gap** — the single honest scenario completes identically in both conditions |

**What is not yet covered, stated plainly:**

- This is **one synthetic adversarial process** (`malicious_server.py`),
  the same stub the preliminary probe used — not yet combined with the
  real, unmodified third-party servers M3 (`docs/29`) already tests
  separately. Whether a real server's own honest multi-step behavior
  survives this exact staging design is unmeasured.
- The honest scenario is a **single write**, not the multi-write-plus-
  rename workflow `25` §6 names explicitly ("a real save is several
  writes plus a rename... must still complete"). Untested here.
- `hidden_extra_field`'s silent commit (above) means this design, alone,
  is not sufficient for the full Permit rule (`25` §5) — `Matches(a, C)`
  on the raw proposal still needs to be checked somewhere, most likely
  before staging even begins, not only after.

So: M2's central architectural question — does a generic boundary confine
a server that genuinely holds execution authority — now has a real,
measured, mostly-positive answer, with one precisely-named gap
(request-shape checks) rather than an entirely open milestone. Combining
this design with a real M3 server, and with multi-write honest workflows,
is the natural next step, not yet done.

## Reproduce

```bash
python experiments/run_m2_boundary.py
python experiments/make_results.py   # results/tables/boundary_probe_m2.md
```

# 36 — Our approach: a clean specification, for direct use in the paper

Written 2026-09-16. Everything below is scattered correctly-but-separately
across `25` (the plan), `27` (the candidate spec), `31`/`32` (what was
actually built and found), and `33` (the security argument). This
document pulls the MECHANISM itself — not the evaluation, not the
history of how it was reached — into one clean specification, in the
order a paper's Design/Approach section would want it.

---

## 1. The problem this approach targets

Established by measurement, not assumed (`21`, `24`): a client that only
inspects an MCP tool server's responses cannot reliably determine, after
the fact, what the server actually did (Theorem 1, `33` §1). Six response-
level detection mechanisms were tried against 1,242 real servers; none
reached a usable operating point. The design lesson this approach acts
on:

> Do not rest safety on checking the response of a component that both
> performs the effect and produces the only evidence of it. (`25` §2)

So the approach moves the enforcement point from the RESPONSE to the
EFFECT — mediating what a server actually does to shared state, using
only information the server's own tool declaration already provides.

## 2. The Permit rule

For a proposed effect `a` and an approved contract `C`:

```
Permit(a, C) = Valid(C) ∧ Matches(a, C) ∧ Unused(C) ∧ Mediated(a)
```

- **Valid** — `C` is authentic and unexpired.
- **Matches** — `a`'s operation, target, and payload fall inside `C`'s
  bound fields. Implemented as the request-shape check in §4 step 2.
- **Unused** — invocation allowance remains on `C`. Implemented via
  `AllowanceLedger.reserve()` (`src/mcpgate/allowance.py`) — a reservation
  taken before staging even begins; a second reservation against an
  exhausted contract raises before the effect is ever staged. Found
  missing from the mediator by testing a replay attack, not assumed
  present because the component existed elsewhere in the project (`38`).
- **Mediated** — `a`'s effect took the enforced path; nothing reached the
  world around it unmediated.

This is a **policy definition**, not a theorem — the research content is
in whether an implementation actually preserves it, and where it breaks
(`25` §5). `Mediated` is the clause every implementation is most likely
to get wrong; §4 below is this approach's answer to it.

## 3. Deriving a contract from a tool's own declaration: the specification ladder

A contract's bound fields are derived from what the tool's own JSON
Schema declares — no out-of-band knowledge of the application built on
top. Three levels, tested independently, because more specification does
not uniformly buy more protection (that is an empirical question, `27`):

| Rung | Checks | What it catches | What it cannot |
|---|---|---|---|
| **L1 — destination** | Only the approved path/identity changed | Diversion to a different target | A payload swapped at the approved destination |
| **L2 — structure** | + the result is non-empty / well-formed | Nothing beyond L1 on free-text tools (measured, `27`) | Still nothing about content correctness |
| **L3 — content** | + exact-match (or hash-match) on the final bytes | Content substitution | Nothing beyond content — see §6 for what NO rung can reach |

Verdicts are **per-property**, never collapsed into one execution-level
pass/fail (`27`) — a tool can be `destination=PASS, content=FAIL`
simultaneously, and that distinction is what the ladder is measuring.

## 4. The mediation mechanism: allowance, staging, request-shape, effect-diff, commit-or-discard

Three independent checks, run in sequence, each catching what the others
structurally cannot (found necessary by testing, not designed in from
the start — `33` §4, `38`):

```
1. RESERVE THE ALLOWANCE (Unused(C))  Before anything else: reserve one
             execution slot against this contract's identity
             (`AllowanceLedger.reserve`, `src/mcpgate/allowance.py`). A
             second reservation attempt against an exhausted contract
             raises here — refused before staging even begins, let
             alone the diff. Catches: replay of an already-used,
             legitimate authorization, which an effect-diff alone
             cannot see because a replay's effect matches the contract
             by definition (`38`).

2. ISOLATE   Each invocation gets its own staging workspace, owned by
             the untrusted server's OS identity, writable ONLY by that
             identity. No executor performs the effect on the server's
             behalf — the untrusted process acts normally, with no
             mediation in this path.

3. REQUEST-SHAPE CHECK (Matches(a, C) on the raw proposal)
             Before the effect is even inspected: does the proposal's
             argument set fall entirely within C's bound fields? Any
             field outside C refuses the whole transaction here,
             regardless of what the resulting effect looks like.
             Catches: violations that never touch the filesystem
             (e.g. a hidden argument the tool's own schema didn't
             expose to the ladder).

4. FREEZE + READ ONCE  When the call returns (plus a bounded grace
             window for near-synchronous background work), a trusted
             mediator — a different OS identity than the server —
             reads the staging workspace EXACTLY ONCE. This single
             read is both the evidence for the next step and, if
             committed, the exact bytes that get committed. No second,
             independent read of staging occurs after this point
             (the M2 Commit Invariant, `33` §3).

5. EFFECT DIFF  The single read is checked against the contract at the
             ladder rung in force: exactly the approved path, exactly
             the approved bytes (by equality or hash), no extra paths.
             Catches: effect-level violations the request-shape check
             cannot see (a correct-looking request that nonetheless
             produces the wrong file, wrong bytes, or extra artifacts).

6. COMMIT OR DISCARD  Exact match: the mediator itself — never the
             server — writes the bytes from step 4 into a SEPARATE,
             committed store the server has no write permission on
             at all, and marks the reserved slot COMMITTED. Any
             mismatch at steps 3 or 5: nothing is written; the
             transaction is discarded, full stop.
```

Steps 4–6 are what close the concrete race found and fixed in this
project (`32`): because the committed bytes are taken from the SAME read
used for the decision, not a fresh read, there is no window between
"decided" and "committed" for a race to target.

## 5. What confines vs. what authorizes, and why both layers are necessary

Measured, not asserted (`31` §8.2): with the untrusted process genuinely
holding write authority over its own staging area (required by step 2
above), an OS permission boundary drawn around that area does very little
of the actual confining — the process legitimately needs to write there.
What confines the outcome is step 5's diff-and-discard. OS permission's
remaining, still-necessary job narrows to protecting the
ALREADY-COMMITTED artifact from post-hoc tampering (step 6's separate
store) — verified directly: `rename_after_write` and `hardlink` attempts
against the committed store fail with a real `PermissionError`, the same
attempts against the server's OWN staging area do not fail at all, since
it legitimately owns that area.

**Design consequence stated plainly**: a defense that relies only on OS
permissions around a SHARED writable area is not doing the confining work
this mechanism's numbers might suggest, once the untrusted process
actually needs write authority somewhere. The contract's own diff is
carrying most of the weight, and a design that skips it in favor of "just
sandbox the process" would not reproduce this mechanism's coverage.

**Confirmed directly against the alternative a careful engineer would
actually deploy** (`41`, M5 pilot): a task-specific static least-privilege
sandbox — directory permissions locked to root, the one approved file
pre-created and writable only by the untrusted identity, no software
check at all — was compared head-to-head against this mechanism on a
real server. It caught **neither** a path-diversion nor a content-
substitution attack: the former targets an absolute path entirely outside
the permission-locked directory, which directory permissions cannot
reach; the latter writes the correct bytes to the wrong content at the
CORRECT, permitted path, which no permission system checks in the first
place. Static permissions alone measured no better than no defense at
all on this evidence. Only the software-level diff caught both.

## 6. What this mechanism cannot do, by its own definition — stated once, not scattered

- **It cannot see request arguments with no file-level effect, without
  step 3.** With step 3, it catches them — but step 3 only knows the
  contract's OWN bound-field list, so a tool whose schema hides intent in
  a field the contract-deriver never recognized is still invisible.
- **It cannot enforce a single-use allowance without step 1.** Found by
  testing, not assumed present: a mediator built around step 4 (effect
  diff) alone commits a replay of an already-used authorization, because
  a replay's effect matches the contract by definition (`38`). With
  step 1, a second reservation against an exhausted contract is refused
  before staging even begins.
- **It cannot derive a content check for a tool whose schema offers no
  content field to point at** (the UNDERSPECIFIED class — `27`, `29` §4,
  §6). Confirmed on two independent real SQL-shaped servers: content
  substitution commits, undetected, at every rung, because there is no
  schema-derivable boundary between destination, structure, and content
  in a single opaque string.
- **It cannot prevent an effect that already reached the world before the
  mediator's read** (§4 step 4). "Discard" is bookkeeping over what gets
  counted as committed; a real external write a genuinely unconfined
  process already performed is not undone by this mechanism. Confirmed
  directly by combining the mediator with a real server (`37`): the same
  `path_diversion` attack from `29` §1 still writes to `/tmp/exfil.dat`
  for real when run through this mechanism — the write happens, and is
  correctly kept out of the committed store, but is not undone. Full
  prevention of that specific escape would additionally need the
  server's own writable scope restricted at the OS level before it runs
  (a mount namespace or chroot confining it to `staging`), which this
  mechanism does not add — it relies on the after-the-fact diff, exactly
  as §5 found is the dominant mechanism once a process holds real write
  authority.
- **It requires per-invocation isolation to preserve honest utility, not
  just security** (`34` Part 2) — sharing one staging area across calls
  causes an entirely honest second call to be wrongly discarded because
  of a first call's leftover artifact. Demonstrated, not assumed.
- **It says nothing about confidentiality, and cannot see any channel it
  does not watch.** The untrusted process reads what it is already
  permitted to read; this mechanism's claim is entirely about integrity
  of what reaches the committed store. Demonstrated directly, not only
  argued (`39`): a secret sent over a plain local socket in the SAME
  invocation as an approved, honest file write is completely invisible
  to the mediator, which commits the honest write as cleanly as if
  nothing else had happened — because nothing about that channel was
  ever in its observation surface. No fix for this exists WITHIN a
  filesystem-only mechanism; covering it needs a different layer
  entirely (network namespace isolation, an egress allowlist).
- **Its fixed timing window cannot simultaneously tolerate every honest
  slow write and catch every malicious hidden one — a genuine tradeoff,
  not a bug.** Demonstrated (`40`): an entirely honest write that lands
  after the grace window is discarded exactly like a `background_write`
  attack timed to land there deliberately, because the mediator's single
  read at a fixed delay cannot distinguish "slow but honest" from
  "malicious and patient." Widening the window trades one failure mode
  for the other; it does not remove either. A real fix would replace the
  timeout with an explicit completion signal or process-tree freezing,
  neither implemented here.

## 7. Relationship to prior work, stated once (full account: `26`)

Staging + diff + commit/discard is not new in the abstract — Alcatraz
(2003, process layer) and TxOS (2009, kernel syscall layer, requires a
modified kernel) both hold pieces of it. What is not held by any adjacent
system checked (`26`): staging-and-commit mediation of an UNMODIFIED
process's real, EXTERNAL effect, checked from OUTSIDE against a contract
DERIVED FROM THE TOOL'S OWN DECLARATION — the specific combination this
document specifies, now measured across seven real, independent
third-party servers (`29`), one adaptive adversary (`32`), and the full
mediation mechanism combined with one of those real servers directly
(`37`), not only proposed.

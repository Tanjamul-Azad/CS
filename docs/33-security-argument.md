# 33 — Security argument: what is proved, what is measured, and where each ends

Written 2026-09-16. This project makes two different kinds of security
claim, and the standing rule (`25` §8) is that they must never be
presented as the same kind: "No theorem labels without statements and
proofs." This document separates them explicitly — one proved
impossibility result, one code-level invariant with a proof sketch
grounded in the actual implementation, and the empirical measurements
that back each one up — and states exactly where every claim's authority
runs out.

---

## 1. What is proved: Theorem 1 (Transcript Indistinguishability)

**Statement** (`05-verifiability-taxonomy.md`, `README.md`). Let a client
`C` interact with a server `S` only by issuing calls `S` has declared and
observing `S`'s responses. Let `S*` be a variant of `S` that, on some
call, performs a different effect than declared while returning the
identical response `S` would have returned. Then no decision procedure
available to `C` — a passive client, one that only inspects responses —
can distinguish `S` from `S*` with detection rate exceeding its
false-positive rate, for any such `S*` that returns the honest response
exactly.

**Proof sketch.** By construction: `C`'s observation space is exhausted
by the responses it receives, and `S*`'s responses are, by hypothesis,
identical to `S`'s on the executed call. Any decision `C` makes from
identical inputs is identical, so `C`'s output distribution over `(S,
S*)` is the same regardless of which one it is actually talking to. This
is the shape of TOCTOU (check at T1, use at T2, untrusted party in
between) and of the classical confused-deputy problem
(`12-intellectual-lineage.md`); it is not a novel proof technique, and is
not claimed as one.

**What this rules out, precisely.** Any defense architecture whose only
input is the server's own protocol responses — response validation,
schema checking on replies, LLM-as-judge over tool output. It does not
rule out defenses that observe something OTHER than the server's
response: real filesystem/network state (what this project's mechanism
does), or a second, independent channel the server does not control.

**Empirical confirmation.** `experiments/demo_theorem1.py`: response
validation's detection rate collapses from 100% (level-1 adversary, naive
lies) to 0% (level-2, an adversary that also launders the read-back) —
demonstrated, not merely stated. The large-scale measurement (`24`,
`results/tables/operating_points.md`) confirms the same collapse at
scale: every detector version tried, 0% true detection at any usable
false-positive rate, across 217 real servers.

---

## 2. What is measured, not proved: the escape, and its cost

Theorem 1's own proof identifies the escape: `C` is not purely passive,
it is *authorized to call*. Interrogation (extra reads, metamorphic
relations) moves the client outside the theorem's premise. **This does
not restore a proof** — R1/R2/R7 relations are heuristics, not a
completeness argument, and the large-scale measurement shows exactly how
far short of "solved" they land (0% detection, `results/tables/
operating_points.md`). What IS a real, if informal, argument is the
**Cost Observation** (`README.md`, deliberately not labelled a theorem):
a client checking `k` independent metamorphic relations forces a
diverting server to lie consistently across all `k` simultaneously, and
that consistency has a cost in code and shadow state. Demonstrated, not
proved: 3 LOC / no shadow state → 9 LOC / a fake ledger → 17 LOC / a fake
ledger and balance, at which point this project's own relation set stops
catching it. This is a cost *ladder*, not a security guarantee — an
adversary willing to pay 17+ LOC is uncaught, by measurement, today.

---

## 3. The M2 mediator: a code-level invariant, proved by construction, verified empirically

This is the one place this project makes a security claim about its OWN
mechanism, not about what is impossible in general. Stated as a named
invariant, not a theorem, per the standing rule.

### 3.1 Statement

**M2 Commit Invariant.** For any invocation processed by the M2-proper
mediator (`experiments/boundary/probe_m2.py`, post-fix — see `32`), if
the mediator commits, the bytes present at the committed path are
byte-identical to a single, specific read of the staging workspace taken
before the commit decision was made — call this read `R`. No second,
independent read of the staging filesystem occurs between `R` and the
write to the committed store.

### 3.2 Proof sketch, grounded in the actual code

```python
staged_after = observe(staging)              # R -- the only read of staging
...
if matches_contract:                          # decision, computed from R
    (COMMITTED / approved_path).write_text(
        staged_after[approved_path], ...)      # writes the STRING captured by R
```

The write to `COMMITTED` takes its argument from `staged_after`, a Python
object already held in memory from `R`. No file-open, `read()`, or
`shutil.copy2` call touches `staging` again after `R`. Therefore no
sequence of filesystem operations performed by the untrusted process
after `R` completes can change what gets written to `COMMITTED` in this
invocation — there is no second read for such operations to race
against.

**This is a proof by code inspection, not a mathematical proof over an
abstract model.** It is only as strong as the claim "this is what the
code does," which is why it is paired with an adversarial test that
targets exactly this invariant, not merely inspected and trusted.

### 3.3 Empirical verification, both directions

**Before the fix** (`32`): the mediator read staging TWICE — once via
`observe()` for the decision, once independently via `shutil.copy2` for
the write. The invariant above did NOT hold. An adversary built with
knowledge of the ~0.8s decision window won this race in 5 of 20 trials
(25%) — attacker content reached the committed store despite the diff
having verified different, approved content moments earlier.

**After the fix**: the invariant holds by inspection (§3.2), and the
IDENTICAL attack, same 20 trials, same timing budget, wins **0 of 20**
(`32`). A proof by construction is not treated as sufficient on its own
in this project — see the standing rule "instrument bugs are the default
hypothesis" — so the same empirical test that found the violation is the
evidence the fix actually closes it, not the code reading correctly to a
human.

### 3.4 What this invariant does NOT cover — stated precisely, not implied

- **It says nothing about `R` itself being race-free.** `observe()` reads
  the directory tree; if the untrusted process can win a race *before* or
  *during* `R` (rather than between `R` and the write), this invariant
  does not address it. Not searched for in this project.
- **It says nothing about requests that carry no file-level effect.**
  `hidden_extra_field` is a separate gap, closed by a separate,
  independent check (§4) — the commit invariant is about the bytes that
  DO land on disk, not about the shape of the request that produced them.
- **It assumes the OS permission boundary around `COMMITTED` is correctly
  configured** (owned by a different user than the server, no write bit
  for that user) — verified empirically in `31`/`32` (`rename_after_write`
  and `hardlink` against `COMMITTED` both fail with a real
  `PermissionError`), not assumed.
- **It says nothing about confidentiality.** The untrusted process reads
  the *approved* directory tree freely; nothing here claims the server
  cannot exfiltrate data it can already see. The claim is entirely about
  integrity of what reaches the committed store.
- **It is scoped to ONE mediator implementation, run against ONE
  synthetic adversarial process plus one contract-aware adversary.** Not
  yet combined with a real M3 server (`31` §"What remains open").

---

## 4. The request-shape gap, and its closure

**Gap, found by measurement, not assumed** (`31`, `32`): a mediator that
only diffs FILE STATE cannot see an MCP request argument that never
manifests as a file-level change. `hidden_extra_field` committed under
the original M2-proper design — confirmed, not argued from first
principles, by running the scenario and observing `decision=commit`.

**Fix, closed the same session it was found**: a second, independent
check, run before staging is even inspected —

```python
proposal_args = (proposal_dict or {}).get("arguments", {})
unapproved_fields = sorted(set(proposal_args) - set(INTENT))
if unapproved_fields:
    matches_contract = False   # refused before the staging diff runs at all
```

This is exactly `Matches(a, C)` from the Permit rule (`25` §5), applied
to the raw proposal — the check the preliminary (gateway-performs)
mediator already had, and that the effect-diff-only design lacked. **Two
different jobs, both now present**: the request-shape check catches
violations that never touch the filesystem; the staging diff catches
effects that do. Re-run against all 14 scenarios after the fix: 14/14
correctly confined or legitimately `UNKNOWN` (`silent_noop` only) — see
`results/tables/boundary_probe_m2.md`.

---

## 5. Summary table — every claim, its kind, and its authority

| Claim | Kind | Authority | Where it ends |
|---|---|---|---|
| Theorem 1 | Proved impossibility | Any passive client, any such `S*` | Does not cover a client that also interrogates state outside the response channel |
| Cost Observation | Measured, not proved | This project's own R1/R2/R7 relation set, on the servers measured | An adversary paying ≥17 LOC / maintaining balance+ledger shadow state is uncaught today |
| M2 Commit Invariant | Proved by code inspection + empirically re-verified | This exact mediator implementation, this exact race | Does not cover races before/during the single read, confidentiality, or un-combined-with-M3 deployment |
| Request-shape check | Implemented mitigation, empirically verified | Catches any proposal argument outside the contract's bound fields | Does not by itself catch effect-level violations — needs the staging diff too |

No claim in this table is extrapolated beyond what was actually run. Where
a claim's scope is narrower than it might sound stated alone, the
narrowing is written into the claim itself, not left for a reader to
discover later.

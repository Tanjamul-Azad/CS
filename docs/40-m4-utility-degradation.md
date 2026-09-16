# 40 — M4, fourth attack family: utility degradation

Written 2026-09-16. `25-research-program.md` §6 M4's own list ends with
"degrade utility until the layer is disabled" — not an attack that
breaks confinement directly, but one that makes the defense costly
enough that an operator turns it off. Tried here for the first time.

## The concrete question

`probe_m2.py`'s mediator reads staging after a fixed ~0.8s grace window,
specifically to catch a malicious `background_write` dispatched after the
call returns (`31`). That same fixed window has no way to distinguish
"a MALICIOUS write, deliberately hidden to arrive after the read" from
"a genuinely HONEST write that is simply slower than 0.8s for an
ordinary reason" — load, a large file, a slow disk. Does a merely slow,
entirely honest write get discarded exactly as a malicious one would be?

This tests this project's own mechanism against a timing edge case. No
denial-of-service is performed against anything external — the "slow"
server is an honest process that sleeps before writing, run entirely
inside this project's own sandbox.

## Design

`experiments/boundary/probe_m4_utility_degradation.py`: three trials,
identical honest write, three different delays before the write happens
— 0.2s (well within the window), 0.6s (close to it), 2.0s (past it) —
against the unchanged mediator timing from `probe_m2.py`.

## Result

```
well within the window (delay=0.2s, window=0.8s)
  decision=commit  honest write eventually succeeded=True
  wrongly discarded purely for being slow: False

close to the window (delay=0.6s, window=0.8s)
  decision=commit  honest write eventually succeeded=True
  wrongly discarded purely for being slow: False

honest but slower than the window (delay=2.0s, window=0.8s)
  decision=discard  honest write eventually succeeded=True
  wrongly discarded purely for being slow: True
```

At 2.0s, the write is entirely honest, contains nothing hidden, and
DOES land correctly — just after the mediator already read an empty
`staging` and discarded. The mediator's decision has no way to
distinguish this from a genuinely malicious `background_write`; both
produce the identical observation at read time (nothing there yet).

## What this establishes

- **A real, structural tradeoff, not a bug to patch away.** The fixed
  grace window is what makes `background_write` catchable at all (`31`).
  Any window wide enough to also tolerate a legitimately slow honest
  write is, by the same logic, wide enough to tolerate a background
  write timed to land just inside it — the two are the same problem
  viewed from opposite sides. There is no window value that solves both.
- **This is the concrete shape of "degrade utility until the layer is
  disabled."** A real deployment where honest writes are sometimes
  slower than the window — plausible under real load, not a contrived
  edge case — would see real, legitimate work rejected. The operator's
  rational response to enough of that is to raise the timeout
  indefinitely (which reopens the `background_write` gap this window
  exists to close) or disable the check outright. Neither is a technical
  break of the mechanism; both are a real erosion of its usefulness.

## What would and would not fix it, stated honestly

- **Raising the fixed window** trades one failure mode for the other —
  demonstrated by the same data: at 0.6s it hasn't failed yet, at 2.0s it
  has. There is no single number that is simultaneously "long enough for
  every honest server" and "short enough to still catch a patient
  malicious one."
- **A genuinely different mechanism could help but is not implemented
  here**: an explicit "I am still writing" signal from the server (the
  MCP protocol has no such primitive today), or freezing the process
  tree instead of merely waiting (`25` §6 M2's original design language,
  not implemented in this project's probes) would replace the fixed
  timeout with an actual completion signal. Neither is attempted in this
  probe — this document reports the tradeoff, it does not resolve it.

## Where this leaves M4

All four attack families `25` §6 names have now been tried, each with a
genuinely different, honestly reported outcome:

| Attack family | Result |
|---|---|
| Race the check (TOCTOU) | Found, **fixed and re-verified** (25%→0%) — `32` |
| Exhaust the allowance | Found, **fixed and re-verified** by reusing existing code — `38` |
| Encode the effect in an unmediated channel | **Demonstrated as a scope boundary** — no fix applies within this mechanism — `39` |
| Degrade utility until the layer is disabled | **Demonstrated as a structural tradeoff** — no single fix resolves it; the honest tension is named, not patched over — this document |

Two real defects, closed. Two genuine limits of what this class of
mechanism can promise, named precisely rather than argued away or left
implicit.

## Reproduce

```bash
python experiments/run_m4_utility_degradation.py
```

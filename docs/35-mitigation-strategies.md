# 35 — Mitigation strategies: every gap found, its fix, and its status

Written 2026-09-16. This project has found real bugs and gaps in its own
instruments and its own mechanism throughout — the standing rule
"instrument bugs are the default hypothesis" has held every time it was
tested. This document consolidates every one of them into one place:
what was found, what the mitigation is, and whether that mitigation is
**implemented and re-verified**, or only **recommended**. The distinction
matters and is never blurred — a recommended-but-unimplemented mitigation
is not credited as if it were checked.

---

## A. Measurement-instrument gaps (M0)

| Gap found | Mitigation | Status |
|---|---|---|
| `isError`/`is_error` field-name mismatch: the SDK's wire alias was read instead of the field it actually returns, so `write_errored` was silently `False` on every call this project ever made until found | Read both spellings, prefer whichever is non-`None` | **Implemented, re-verified** — `src/mcpmut/live.py`, applied retroactively to every subsequent measurement |
| `attack_landed` meant only "the proxy changed an argument," not "an unauthorized effect occurred" — sat in the denominator of every published rate | Five independent outcome fields (`mutation_attempted`, `protocol_error`, `authorized_effect_observed`, `unauthorized_effect_observed`, `outcome_unknown`), decided by a trusted observer reading real state, never derived from another field | **Implemented, re-verified** — `experiments/run_effect_oracle.py`, `results/tables/effect_oracle.md` |
| Suppressed detections: 5 real attacks the detector caught internally, reported only as `WARNING`, scored zero | Calibrate the reader before trusting its silence as evidence (R7 calibration) | **Implemented, re-verified** — `results/tables/operating_points.md` shows the calibrated run; detection rate still 0% at usable FPR, i.e. the fix changed what was COUNTED correctly, not the underlying detection capability, which remains the paper's central negative finding |
| Round 1 labelling: 91% of disagreements were one A0-vs-A2 confusion, traced to siblings shown by name only, no description | Show each sibling's own (truncated) description in the sheet; codify "a plausible-sounding sibling NAME is not evidence" as an explicit rule | **Implemented**, Round 2 sheets regenerated (`docs/14`) — **not yet re-verified**, blocked on human labelling (κ still open, `docs/28`) |
| Label-sample orphaning: a drawn sample could no longer be matched against a regenerating live corpus | Archive the exact `ExtractedTool` records at sample-draw time (`*.corpus_archive.jsonl`), score against the archive when present | **Implemented, re-verified** — `tests/test_label_archive.py` |

## B. M1 — literature-derived design constraints, not bugs

Not gaps found by testing, but constraints the novelty gate (`26`)
imposed by showing what NOT to claim:

| Constraint | Why | Where enforced |
|---|---|---|
| Do not claim novelty for confining an unmodified server at a declaration-derived boundary in general | AgentBound already does this | `25` §1 goal statement corrected |
| Do not claim novelty for staging+diff+commit/discard in the abstract | Alcatraz (2003), TxOS (2009) | Candidate scoped to the narrow gap those three don't cover (`26` §6) |
| Do not claim "no sandbox can enforce authorization" | Landlock can, given a policy | `26` §2, corrected as a self-overclaim |

## C. M2 mediator gaps (found by adversarial testing against real code)

| Gap found | Mitigation | Status |
|---|---|---|
| **TOCTOU race**: the mediator read staging twice (once to decide, once via `shutil.copy2` to commit) with no lock between the reads. An adversary that knows the ~0.8s decision window won 5/20 trials (25%), landing attacker content in the committed store | Commit the bytes ALREADY read for the diff decision; never re-read staging from disk at commit time (`(COMMITTED/path).write_text(staged_after[path], ...)`) | **Implemented, re-verified** — identical attack, same 20 trials, 0/20 after the fix (`32`) |
| **Request-shape blindness**: a pure effect-diff mediator cannot see an MCP request argument (`hidden_extra_field`) that never manifests as a file-level change — it committed | A second, independent check on the raw proposal's argument keys, run BEFORE the staging diff: any key outside the contract's bound fields refuses the whole transaction | **Implemented, re-verified** — re-run of all 14 scenarios, 14/14 correctly confined or legitimately `UNKNOWN` (`33` §4, `results/tables/boundary_probe_m2.md`) |
| **Effect-to-call binding**: sharing one staging directory across two sequential honest calls causes the second call's entirely honest effect to be wrongly discarded because of the first call's leftover artifact | Isolate staging per invocation (a fresh directory per call, reset before use) — already the design every other M2 probe in this project uses | **Design mitigation confirmed necessary by demonstrating the failure without it** (`34` Part 2). **Not fully verified for genuine concurrency** — tested sequentially, not with two calls genuinely overlapping in time, which would additionally need synchronization this project has not tested |
| **UNDERSPECIFIED-class blindness**: a `sql`-shaped tool's schema gives the mechanism no field to derive a content check from at all — content substitution is uncaught at ANY rung, replicated on two independent real servers (`29` §4, §6) | **Recommended, not implemented**: an application-level adapter that understands the caller's own table schema (which columns exist, which identify a row) would need to sit between the generic contract layer and this class of tool. Whether that adapter can be derived automatically or must be hand-written per application is exactly the open question the program's own goal statement (`25` §1) asks | **Not implemented.** Stated as an open question, not silently left unaddressed |
| **M2 mediator not yet combined with a real (non-stub) server** | Wrap the real server's launch command in `su sandbox -s /bin/sh -c '...'` — `LiveSession` has no built-in privilege-drop (verified against the MCP SDK's own launch-parameter type), so the OS-level identity switch happens inside the command string it's given, verified live before being relied on | **Implemented, verified** (`37`): run against `domdomegg/filesystem-mcp`, the identical `path_diversion` attack from `29` §1 still writes to `/tmp/exfil.dat` for real (detection, not prevention, of that specific escape — the real write is not undone) but is correctly kept out of the committed store |
| **Allowance exhaustion / replay**: the mediator has one signal (does the effect match the contract), and a replay of an already-used authorization matches by definition — the mediator committed the same approved write twice | Wire `AllowanceLedger.reserve(contract_id, request_id, max_invocations)` in BEFORE staging — this component already existed, already unit-tested (`tests/test_allowance.py`), already used by the preliminary gateway; it had simply never been connected to the newer M2-proper mediator | **Implemented, re-verified** (`38`): identical replay, `committed=True` twice without the ledger, `committed=False` on the second call (refused before staging) with it wired in |
| **Unmediated-channel exfiltration**: a secret sent over a plain local socket, in the SAME invocation as an approved honest file write, is invisible to a filesystem-only mediator — demonstrated live (`39`), not only argued | **No fix applies within this mechanism.** A filesystem contract-and-staging design can only ever cover the filesystem; covering network channels needs a DIFFERENT mechanism layer (network namespace isolation, an egress allowlist, TLS interception) | **Demonstrated scope boundary, not a bug — not applicable to fix within this mechanism.** Stated as a hard limit of what a filesystem-only mediator can ever claim, not a gap that was merely missed |
| **Utility degradation**: an entirely honest write slower than the mediator's fixed grace window is discarded exactly like a malicious hidden background write — the design has no way to tell them apart (`40`) | **No single fix resolves it — a genuine tradeoff, stated honestly.** Raising the window tolerates more honest slowness but also more patient malice; there is no value that is simultaneously "long enough for every honest server" and "short enough to catch a patient adversary." A different mechanism (an explicit completion signal from the server, or freezing the process tree instead of waiting) could replace the timeout, but is not implemented here | **Demonstrated structural tradeoff, not a bug — not applicable to fix within a fixed-window design.** The tension is named precisely rather than patched over with an arbitrary timeout change |

## D. What "implemented and re-verified" means in this project, stated once

A fix is not reported as done because the code was edited and looked
correct on inspection. Every row above marked "implemented, re-verified"
went through the same cycle: the original bug was demonstrated with a
real, running test; the fix was written; the SAME test was re-run against
the fixed code, not a new, easier test; and the result (0/20, 14/14, etc.)
is what is reported — not the code diff alone. This is the discipline
carried from the very first instrument bug found in this project
(`isError`) through the most recent one (`32`'s TOCTOU race), applied
consistently rather than loosened as the project's own confidence grew.

## E. Summary — what remains genuinely open

Two gaps in the table above are explicitly **not implemented**, and are
carried forward rather than hidden:

1. An adapter strategy for UNDERSPECIFIED-class tools (SQL and similar) —
   open question, not yet attempted.
2. Verified behavior under genuine concurrency (two calls truly
   overlapping in time, not sequential) — only the sequential case was
   tested (`34` Part 2).

A third item — combining the M2 mediator with a real (non-stub) server —
was open as of this document's first version and is now closed (`37`),
kept in this list's history rather than silently removed.

These three, plus the still-open κ gate and the remaining M4 attack
families (`32`), are the concrete scope of work this project has left,
stated in the same place as everything that has already been closed.

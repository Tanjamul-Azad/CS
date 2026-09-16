# 41 — M5, held-out evaluation pilot: the M2 mechanism vs. two baselines

Written 2026-09-16. `25-research-program.md` §6 M5: compare this layer
against baselines including "the demanding one" — a task-specific static
least-privilege sandbox — and report unauthorized-effect rate, honest
completion, false blocks, and latency overhead. First attempt at this
comparison in the project.

## Scope, stated before any result

**Server**: `io.github.domdomegg/filesystem-mcp`. Previously used once
for M2-mechanism work — the single-condition capstone combination (`37`).
This is its first use in a **multi-baseline** comparison, which is what
M5 actually asks for. Stated precisely: this is not a server the project
had never seen (`29` §1, `37` both used it) — it is the first time it has
been run through more than one defensive condition side by side.

**Baselines run live**: no defense, a static least-privilege sandbox, and
this project's own M2 mechanism (`31`, `32`, `37`).

**Baselines from `25` §6 explicitly NOT run, and why**:
- *The project's own auditor* — already measured at 0% true detection
  across 217 real servers (`results/tables/operating_points.md`); not
  re-run against this one server, since that number is already
  established and re-running it here would add nothing.
- *Plain container sandbox* — collapses into "no defense" here: every
  condition in this probe already runs inside the same Docker container
  regardless of which defensive layer is added on top. There is no
  separate "outside the container" comparison to make.
- *MCP confirmation prompts* — cannot be tested without a real human
  actually reviewing each call. Simulating one would be exactly the kind
  of fabricated result this project has refused to produce throughout;
  explicitly not attempted.

**Attack scope**: only argument-level attacks (path diversion via the
project's own `TamperingProxy`, content substitution via direct argument
tampering) — not the OS-bypass techniques `malicious_server.py` uses
(symlink escape, hardlink, etc.), because those require a deliberately
adversarial SERVER IMPLEMENTATION, which only the stub servers provide.
A real, unmodified server does only what its own tool declaration says.

## The static least-privilege baseline, built from plain Unix permissions

No software layer at all — deliberately, since the point of this
baseline is to isolate what PURE OS permissions can achieve, the
"demanding" comparison `25` §6 calls for:

- The staging directory: owned by **root**, mode `0555`. The server
  cannot create, delete, or rename ANY entry in it.
- The one approved target file: **pre-created**, owned by `sandbox`,
  mode `0600`. The server CAN open and write into this existing file —
  file permissions, not directory permissions, govern writing to a file
  a process already has access to.
- Verified live, not assumed: `create` on this server writes/overwrites
  rather than requiring the target not to already exist — confirmed by
  the honest trial succeeding against the pre-created file.

## Result

```
scenario               condition                  attack_landed  unauthorized_effect  decision
------------------------------------------------------------------------------------------------
honest                 no_defense                 -              false                 -
honest                 static_least_privilege     -              false                 -
honest                 m2_mechanism               -              false                commit

path_diversion         no_defense                 true           true                  -
path_diversion         static_least_privilege     true           TRUE                  -
path_diversion         m2_mechanism               true           true (real write)   discard

content_substitution   no_defense                 true           true                  -
content_substitution   static_least_privilege     true           TRUE                  -
content_substitution   m2_mechanism               true           false               discard
```

**Honest completion**: all three conditions complete correctly, byte-exact.

**Path diversion**: lands as a real external write to `/tmp/exfil.dat`
under **every** condition, including static least-privilege. Directory
permissions on the staging area do nothing to stop a write to a
completely different absolute path — confirming, on real code, exactly
what plain Unix permissions can and cannot express. Under M2, the write
still happens for real (detection, not prevention, of that specific
escape — same as `37`), but is correctly kept out of what gets counted as
committed.

**Content substitution**: lands under no-defense AND under static
least-privilege — the attacker's payload is written to the *correct*,
permitted path, so a pure permission check has nothing to object to; only
a check on WHAT was written can catch this. Only M2 catches it.

**The sharp finding**: static least-privilege, implemented the common,
cheap way (Unix permissions on one directory), provides **zero**
additional protection over no defense at all, against either attack
tested. It is not a weaker version of M2 — on this evidence, it is not
a defense against these attacks in any measurable sense. What actually
confines the outcome is M2's software-level diff-and-discard, not the
permission structure underneath it.

**Latency**: the honest trial's no-defense condition took 10.0s — almost
certainly `npx`'s cold-start package resolution on the first launch in a
fresh container, not a property of the "no defense" condition itself.
Every subsequent trial across all three conditions, including M2, lands
in the same 0.7–0.9s band. **On this evidence, M2's own overhead (staging
setup, the diff, the commit copy) is not measurably distinguishable from
server-launch cost itself** — a genuine, if narrow, positive result for
the "latency and call overhead" metric `25` §6 asks for, though one
server and nine trials is a thin basis for a general latency claim.

**False blocks**: none observed in any condition — the honest scenario
committed correctly everywhere.

## What this pilot does and does not establish

- **Does**: give M5 a first real datapoint against the baseline `25` §6
  itself calls "the demanding one," and shows it losing to the mechanism
  this project built, on real code, not a synthetic comparison.
- **Does not**: establish this across servers or workflows. One server,
  three scenarios — the same scale caveat every real-server result in
  this project carries.
- **Does not** run the two baselines this document explicitly excludes
  above. Reported as not run, not silently omitted.
- **Does not** establish a general latency claim — nine trials against
  one real server's launch-dominated timing is a thin basis, stated as
  a narrow, first observation rather than a settled number.

## Reproduce

```bash
python experiments/boundary/probe_m5_held_out.py   # via docker, see other run_*.py drivers for the invocation pattern
```

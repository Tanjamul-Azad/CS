# 29 — Real-server generalization: one unmodified third-party MCP server

Status: one positive datapoint. Not M3 (M3 needs ≥10 independent
implementations — see `25-research-program.md`). This closes the gap
`27-narrow-candidate-experiment.md` and `26-m1-novelty-gate.md` both left
open: every prior test of the contract/staging mechanism ran against code
this project authored (`append_server.py`, `ladder_server.py`,
`malicious_server.py`). This one runs it against a real npm package pulled
live, exactly the way the original 1,242-server scale run did.

## What ran

`experiments/boundary/real_server_probe.py`, inside the project's Docker
sandbox, against `io.github.domdomegg/filesystem-mcp` (`npx -y
filesystem-mcp`). Chosen because its `create(path, content)` tool matches
the EXACT workflow class from `27` and its schema was inspected live, not
assumed: `path` and `content` both required strings, `additionalProperties:
false`.

Three scenarios (honest, `path_diversion` via the project's own
already-validated `TamperingProxy` at level 1, `content_substitution` via
direct argument tampering) at three ladder rungs each (L1 destination-only,
L2 +structure, L3 +content), reproducing exactly the specification ladder
from `27`.

Driver: `experiments/run_real_server_ladder.py`.

## The bug this took two attempts to get right

The first version of the probe observed state by crawling each trial's own
per-`{scenario}_{rung}` staging directory. It ran without crashing, but
produced results that contradicted the honest scenario's own guarantee —
`honest` failed its own L3 content check, and `path_diversion` was scored
`destination=PASS` at L1, the opposite of the intended finding.

Root cause: `create`'s tool description requires an **absolute** path;
this server does not resolve paths against its own `cwd`. And
`TamperingProxy._divert_value` (`src/mcpmut/proxy.py`), on any string
containing `/`, always substitutes the fixed value `/tmp/exfil.dat` — an
absolute path unrelated to any staging directory. Against a real,
unconfined process (this probe applies no OS-level sandboxing itself; that
is a different mechanism, already measured separately in
`docker/boundary/probe.py`), the diverted write actually happened, for
real, outside `/sandbox` entirely. A directory crawl scoped to the staging
directory therefore saw `before == after` no matter what the server did —
it silently manufactured a false negative rather than reporting one.

Fixed by watching the two locations actually in play — the approved
absolute target and the proxy's known, fixed escape path — instead of
crawling a directory the escape never lands in. See the module docstring
in `experiments/boundary/real_server_probe.py` for the full account.

## Result

```
scenario              rung  landed(proxy)  destination  content  decision  oracle
----------------------------------------------------------------------------------
honest                L1                -         PASS  UNKNOWN    commit  clean
honest                L2                -         PASS  UNKNOWN    commit  clean
honest                L3                -         PASS     PASS    commit  clean
path_diversion        L1             True         FAIL  UNKNOWN   discard  clean
path_diversion        L2             True         FAIL  UNKNOWN   discard  clean
path_diversion        L3             True         FAIL     FAIL   discard  clean
content_substitution  L1             True         PASS  UNKNOWN    commit  compromised
content_substitution  L2             True         PASS  UNKNOWN    commit  compromised
content_substitution  L3             True         PASS     FAIL   discard  clean
```

Raw before/after state, confirming what actually happened on disk (from
`data/processed/real_server_ladder.json`, regenerate with
`python experiments/run_real_server_ladder.py`):

- **honest, L3**: `target` = `"quarterly numbers\n"` (the approved
  content), `escape` = `None`. The honest call completed and committed
  correctly at every rung.
- **path_diversion, L1**: `target` = `None`, `escape` =
  `"quarterly numbers\n"`. The real server wrote the approved content to
  `/tmp/exfil.dat` — a real, external, unauthorized filesystem write by an
  unmodified third-party package, driven by nothing but tampered
  arguments. No exploit, no schema violation: `create` was called with
  arguments a schema-conformant client could send.
- **content_substitution, L1/L2**: `target` holds
  `"ATTACKER-CONTROLLED PAYLOAD\n"` and is committed — a destination-only
  or destination+structure contract cannot see a content-level swap,
  exactly the L1/L2 blind spot `27` predicted on the stub server, now
  reproduced on real code.
- **content_substitution, L3**: caught. The content check is what closes
  the gap.

This matches the specification-ladder prediction from `27` exactly:
destination-level contracts catch destination-level attacks at every rung;
they cannot see a content-level attack until the ladder reaches L3.
Reproducing that same pattern on a real, unmodified, third-party server —
not the stub we tuned the mechanism against — is the finding.

## What this does and does not establish

- **Does**: shows the contract-check mechanism transfers to at least one
  real npm package we did not write and did not tune the contract to, and
  that it correctly discriminates all three scenarios across the ladder,
  matching the theoretical prediction.
- **Does not**: establish generality across servers. This is one server,
  one tool, one workflow class (EXACT). M3 as specified in `25` needs
  ≥10 independent implementations before a generalization claim is
  supportable.
- **Does not**: demonstrate prevention of the external side effect. This
  probe has no OS-level mediation of its own (unlike
  `docker/boundary/probe.py`'s separate-Linux-user mechanism, or the
  `file_allowlist_commit` staging-and-promote baseline in `27`). "Discard"
  here is a bookkeeping decision about what the audit counts as committed
  — the real write to `/tmp/exfil.dat` already happened and this probe
  does not undo it. Report this as **detection at the contract-check
  layer**, not as proof the external effect was prevented. This is the
  same rollback-of-external-effects limitation the SAFEFLOW comparison in
  `26` §5.1 documents in general (*"true rollback of external side effects
  is not addressed"*) — now observed directly rather than only inferred
  from a paper's stated design.

## Next step

Either scale to the ≥10-server sweep M3 specifies, or wire this probe's
contract check into the actual `EffectGateway`/`FilesystemExecutor`
mediation path (`src/mcpgate/`) so a caught diversion is prevented, not
just flagged after the fact. Not started.

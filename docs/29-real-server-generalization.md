# 29 — Real-server generalization: unmodified third-party MCP servers

Status: **two verified datapoints, two written-but-unverified.** Not M3
(M3 needs ≥10 independent implementations — see `25-research-program.md`).
This closes the gap `27-narrow-candidate-experiment.md` and
`26-m1-novelty-gate.md` both left open: every prior test of the
contract/staging mechanism ran against code this project authored
(`append_server.py`, `ladder_server.py`, `malicious_server.py`). These run
it against real npm packages pulled live, exactly the way the original
1,242-server scale run did.

| Server | Workflow class | Status |
|---|---|---|
| `domdomegg/filesystem-mcp` | EXACT | **Verified**, §1 below |
| `@modelcontextprotocol/server-filesystem` (official) | EXACT | **Verified**, §2 below |
| `@modelcontextprotocol/server-memory` | CONSTRAINED (keyed/structured) | Written, **not yet run to completion** — see §3 |
| `mcp-sqlite-server` | UNDERSPECIFIED (free-text SQL) | Written, **not yet run** — see §3 |

## §1. domdomegg/filesystem-mcp

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

## §2. @modelcontextprotocol/server-filesystem (official reference implementation)

Same EXACT workflow class, same `path`/`content` tool shape (`write_file`),
but a genuinely different, independent implementation — this is the
reference server Anthropic ships, not domdomegg's. Run: `experiments/
boundary/probe_server_filesystem.py`. Schema verified live: `write_file
(path: string, content: string)`, both required, no
`additionalProperties: false` this time.

**The one behavioral difference that matters.** This server takes an
allowed directory as a CLI argument at launch and enforces it itself:
any path resolving outside that directory is refused before any effect
happens. Driving `write_file` through the project's unmodified
`TamperingProxy` — the identical attack that succeeded against
domdomegg/filesystem-mcp in §1 — gets refused outright here:

```
scenario              rung  refused  landed  destination  content  decision  oracle
--------------------------------------------------------------------------------------
honest                L1    False    -       PASS         UNKNOWN  commit    clean
honest                L2    False    -       PASS         UNKNOWN  commit    clean
honest                L3    False    -       PASS         PASS     commit    clean
path_diversion        L1    True     True    PASS         UNKNOWN  commit    clean
path_diversion        L2    True     True    PASS         UNKNOWN  discard   clean
path_diversion        L3    True     True    PASS         FAIL     discard   clean
content_substitution  L1    False    True    PASS         UNKNOWN  commit    compromised
content_substitution  L2    False    True    PASS         UNKNOWN  commit    compromised
content_substitution  L3    False    True    PASS         FAIL     discard   clean
```

`refused=True` means the SDK's own `is_error`/`isError` flag (read under
both spellings — the calibration bug from `24`) fired: the server's own
path-allowlist check rejected the diverted write before any external
effect occurred. Nothing landed at the escape path, so our contract's
`destination` check reads PASS — correctly, since nothing unauthorized
actually happened, but for a reason external to our mechanism.

**This is the actual finding, and it is a real difference between two
"same workflow class" implementations, exactly the kind of variation M3
exists to measure.** Against domdomegg/filesystem-mcp the identical
tampered call landed as a real external write (§1). Against the official
reference server it did not, because that server enforces its own
directory boundary. Two implementations of what looks, from the tool
declaration alone, like the same tool — different real-world outcome.

**A caveat worth stating precisely**, and a direct instance of the
project's own standing rule ("report prevented / detected / UNKNOWN
separately — a refusal and a compromise are opposite events that look
identical in world state," `README.md`): at L1, `decision=commit` for
`path_diversion` does not mean "the honest effect completed as approved."
It means "nothing appeared at either watched location," which is equally
consistent with an honest success or an upstream refusal. Only the
`server_refused_call` flag — which is not part of the contract check
itself, it is bookkeeping this probe adds — distinguishes them here. A
contract derived purely from watching file state, with no visibility into
the protocol-level error flag, could not tell these apart at L1 either.

Driver for both §1 and §2 together:
`experiments/run_real_server_ladder.py` currently runs only §1;
`experiments/run_multi_server_ladder.py` (added alongside §3, see below)
runs all four.

## §3. Written but not yet verified: server-memory, mcp-sqlite-server

Two more probes were designed and written in the same session as §2, for
two workflow classes no real server had tested yet:

- **`experiments/boundary/probe_server_memory.py`** —
  `@modelcontextprotocol/server-memory`'s `create_entities` tool: a KEYED,
  STRUCTURED store (name/entityType/observations), not a file path. Its
  docstring records a real, separate finding already confirmed by
  inspection (not assumed): `TamperingProxy._pick_target` only inspects
  TOP-LEVEL string arguments, and `create_entities`'s only top-level
  argument is an array of objects — so the existing automatic tampering
  instrument cannot even formulate an attack against this tool's shape.
  The probe applies the same diversion by hand, one level into the nested
  structure, using the same `_divert_value`/`_substitute` primitives
  TamperingProxy itself uses.
- **`experiments/boundary/probe_sqlite.py`** — `mcp-sqlite-server`'s
  `query` tool: the UNDERSPECIFIED class from `27`, a single opaque `sql`
  string with no schema-derivable split between destination, structure,
  and content. Its docstring argues why L2/L3 are reported `N/A` rather
  than `UNKNOWN` for this tool — no schema-derivable check exists for
  those properties at all, not merely "not checked at this rung by
  policy" — and why the two attacks tested are hand-authored SQL rather
  than schema-derived tampering, for the identical reason as the memory
  probe.

**Why these are not reported as results.** The `server-memory` probe's
first attempted run took over six minutes and had to be killed without
producing output — most likely resource contention from running several
`docker run` invocations concurrently on the host rather than a real
defect in the probe (a clean, isolated single-trial timing check
completed one full trial, three subprocess launches included, in 10.7
seconds), but this was never confirmed by a clean full run before the
session that wrote it ended. `probe_sqlite.py` was written and reviewed
but never executed at all. Reporting either as a result without having
watched it complete cleanly would violate this project's own standing
rule ("instrument bugs are the default hypothesis" — `README.md`) in the
same way the very first version of the §1 probe did. They are left as
code, not findings, until run and read the same way §1 and §2 were.

## Next step

- Finish §3: rebuild the Docker image, run `probe_server_memory.py` and
  `probe_sqlite.py` in isolation (not concurrently with other Docker
  activity), and either report their results the same way as §1/§2 or
  fix whatever the clean run reveals. `experiments/
  run_multi_server_ladder.py` runs all four servers in one pass once §3 is
  confirmed working.
- Scale toward the ≥10-server sweep M3 specifies — four servers across
  three workflow classes is a real step past one, still far short of ten.
- Or wire the contract check into the actual `EffectGateway`/
  `FilesystemExecutor` mediation path (`src/mcpgate/`) so a caught
  diversion is prevented, not just flagged after the fact. Not started.

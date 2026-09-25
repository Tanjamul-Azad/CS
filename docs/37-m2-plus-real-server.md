# 37 — M2 + a real server: the capstone integration

> **2026-09-21 status note.** The result below is a valid historical run of the
> original hand-written `mediate()` function. The probe has since been migrated
> to the reusable integrated pipeline in `src/mcpgate/mediator.py`, including
> allowance reservation, per-invocation staging, transport-shape validation,
> explicit writer shutdown, atomic snapshot commit, and ledger finalization.
> Docker is unavailable on the current laptop, so that revised code path has not
> yet been rerun against the third-party server. See `docs/43`. Do not cite this
> historical output as empirical validation of the newly integrated path.

Written 2026-09-16. Every M2 probe until now (`31`, `32`, `34`) confined
`malicious_server.py` or `adaptive_server.py` — synthetic processes
written for this project. Every M3 probe (`29`) ran a real, unmodified
server, but with no OS confinement at all. `29`'s own "next step,"
`31`'s "what remains open," `34`'s scope, `35`'s open mitigation row, and
`36`'s design-limits section all named the same missing piece: the two
have never been combined. This closes it.

## The engineering gap that had to be solved first

`LiveSession` (the project's real-MCP-protocol client, `src/mcpmut/
live.py`) has no built-in way to drop privileges on the subprocess it
launches. Verified directly, not assumed: `StdioServerParameters` (the
MCP SDK's own launch-parameter type) exposes `command`, `args`, `env`,
`cwd`, encoding options — no `preexec_fn`, no uid/gid. That is why every
prior M2 probe used a hand-written stub server instead of a real one:
there was no way to launch a real MCP server as a different, lower-
privileged OS user through the project's existing MCP client.

**Fix**: wrap the launch command in `su sandbox -s /bin/sh -c '...'`.
`LiveSession` only ever sees a command string — it has no idea the string
itself performs a real privilege drop before the actual server starts.
Verified live before relying on it: a real `npx -y filesystem-mcp`
process launched this way answers `tools/list` and `create` calls
normally over stdio, and the file it writes is owned by the `sandbox`
UID (confirmed via `os.stat`), not root.

```python
def su_command(inner: str) -> str:
    escaped = inner.replace("'", "'\\''")
    return f"su sandbox -s /bin/sh -c '{escaped}'"
```

## Design

Same server `29` §1 used — `io.github.domdomegg/filesystem-mcp`, chosen
specifically to close that experiment's own loop: it showed a diverted
write landing for real, unconfined, outside `/sandbox`. Same mediator
logic as `probe_m2.py`'s post-fix `run_m2`: an OS-owned staging area
(`0700`, the `sandbox` UID, no executor in the path), a single read of
staging for the diff, commit the bytes from THAT read (never a second,
independent read — the M2 Commit Invariant, `33` §3) into a separate,
root-owned committed store the server has zero permission on.

Same three scenarios `29` §1 already measured: honest, `path_diversion`
(via the project's own, already-validated `TamperingProxy`), and
`content_substitution` (manual argument tampering).

## Result

```
honest:
  destination=PASS  content=PASS  decision=commit
  staged_content='quarterly numbers\n'
  escape_content=None
  committed_content='quarterly numbers\n'

path_diversion:
  landed(proxy)=True  diverted_field=path
  destination=FAIL  content=FAIL  decision=discard
  staged_content=None
  escape_content='quarterly numbers\n'
  committed_content=None
  UNAUTHORIZED: real server wrote to the escape path, outside staging

content_substitution:
  landed(proxy)=True  diverted_field=content
  destination=PASS  content=FAIL  decision=discard
  staged_content='ATTACKER-CONTROLLED PAYLOAD\n'
  committed_content=None
  UNAUTHORIZED: staged content does not match the approved bytes
```

**Honest**: completes and commits, byte-exact, no different from any
stub-server trial.

**`path_diversion`**: the real, unmodified server genuinely wrote
`"quarterly numbers\n"` to `/tmp/exfil.dat` — a real external effect by
real third-party code, reproducing `29` §1's original finding exactly.
This time, the mediator's escape-path check catches it: `committed_content
= None`, `decision = discard`. The real write to `/tmp` already happened
and is not undone — the same detection-not-prevention limitation `29` §1
and `33` §3.4 both name — but it never reaches the trusted committed
store, which is the property this whole mechanism claims to deliver.

**`content_substitution`**: the attacker's payload is staged for real,
caught by the content diff, discarded — never committed.

## What this establishes, and what it does not

- **Does**: closes the single most-repeated open item across `29`, `31`,
  `34`, `35`, `36` — the M2-proper mediator, applied to a real,
  unmodified, third-party server for the first time, not only a
  synthetic stub. The same real diversion that landed unconfined in `29`
  §1 is kept out of the committed store here.
- **Does not**: establish this across servers. One real server, three
  scenarios — the same scale caveat every prior M2 result already
  carries, now inherited by this integration too.
- **Does not**: prevent the real external write to `/tmp/exfil.dat` from
  happening — only keeps it from being trusted. True prevention of that
  specific escape would need the server's OWN writable scope restricted
  at the OS level (e.g. a mount namespace or chroot confining it to
  `staging` before it ever runs), which this probe does not add — it
  relies entirely on the contract's after-the-fact diff, exactly as
  `31` §8.2 found is the dominant mechanism once a process holds real
  write authority.
- **Confirms `29` §1's honest-server behavior is unaffected by
  confinement**: the honest trial's `committed_content` is byte-identical
  to the unconfined `29` §1 trial's — the `su`-based OS confinement adds
  no observable friction to a well-behaved real server.

## Reproduce

```bash
python experiments/run_m2_real_server.py
```

# 29 — Real-server generalization: unmodified third-party MCP servers

Status: **seven verified datapoints, across all three workflow classes
`27-narrow-candidate-experiment.md` defines, plus one git-native shape and
one two-field-content shape, including a replication of the sharpest
finding on a second independent implementation.** Still not M3 (M3 needs
≥10 independent implementations — see `25-research-program.md`). This
closes the gap `27` and `26-m1-novelty-gate.md` both left open: every
prior test of the contract/staging mechanism ran against code this
project authored (`append_server.py`, `ladder_server.py`,
`malicious_server.py`). These run it against real npm/PyPI packages
pulled live, exactly the way the original 1,242-server scale run did.

| Server | Workflow class | Status |
|---|---|---|
| `domdomegg/filesystem-mcp` | EXACT | **Verified**, §1 below |
| `@modelcontextprotocol/server-filesystem` (official) | EXACT | **Verified**, §2 below |
| `@modelcontextprotocol/server-memory` | CONSTRAINED (keyed/structured) | **Verified**, §3 below |
| `mcp-sqlite-server` | UNDERSPECIFIED (free-text SQL) | **Verified**, §4 below |
| `mcp-server-git` (official, PyPI/uv) | CONSTRAINED (git-native, no content argument at all) | **Verified**, §5 below |
| `mcp-server-sqlite-npx` | UNDERSPECIFIED (free-text SQL, independent implementation) | **Verified**, §6 below |
| `notes-mcp` (PyPI/uv) | CONSTRAINED (content split across two arguments) | **Verified**, §7 below |

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

## The bug that blocked §3 and §4 for one session, and its real fix

The first attempt at `probe_server_memory.py` opened a fresh `npx`
subprocess three times per trial (a before-snapshot session, the
scenario's own session, an after-snapshot session — 27 launches for 9
trials), because this server's state can only be read back through a live
MCP call, unlike a plain file. That version reliably stalled for minutes
and had to be killed without producing output, most likely from
unreaped `npx`/node child processes accumulating across repeated launches
inside one container (`--pids-limit=256`) — the other probes in this
sweep, which open one session per trial, never showed the same slowdown.
Fixed by doing the before-snapshot, the scenario's mutating call, and the
after-snapshot all through **one already-open session** — 9 launches, not
27 — which is both the fix and the more honest design: the protocol has
no session boundary between these calls in real use either. Full account
in the probe's own module docstring. Re-run clean, isolated, no
concurrent Docker activity: all 9 trials completed without error.

## §3. @modelcontextprotocol/server-memory — first CONSTRAINED/keyed datapoint

`create_entities(entities: [{name, entityType, observations[]}])` appends
typed, named records to a JSON-lines knowledge graph — a KEYED,
STRUCTURED store, not a file path. Schema verified live.

**Why the attack is applied by hand, not via `TamperingProxy`.**
`TamperingProxy._pick_target` only inspects TOP-LEVEL string-valued
arguments; `create_entities`'s only top-level argument is `entities`, an
ARRAY of objects, so the automatic instrument finds nothing to divert and
would forward the call honestly, unmodified. This is a real, worth-stating
limit of the existing field-substitution instrument, not a server
defense — the diversions below use the exact same primitives
(`_divert_value`, `_substitute`) TamperingProxy itself uses, one level
deeper into the nested structure.

**Ladder, reinterpreted for a keyed store** (see `24` §5's ENUM/SNAP
framing): L1 = the record exists under the APPROVED name, not a diverted
one; L2 = `entityType`/`observations` present and non-empty; L3 =
`observations` exactly match the approved list.

```
scenario                   rung  landed  destination  content  decision  oracle
----------------------------------------------------------------------------------
honest                     L1    -       PASS         UNKNOWN  commit    clean
honest                     L2    -       PASS          -       commit    clean
honest                     L3    -       PASS         PASS     commit    clean
name_diversion              L1    True    FAIL         UNKNOWN  discard   clean*
name_diversion              L2    True    FAIL          -       discard   clean*
name_diversion              L3    True    FAIL         FAIL     discard   clean*
observation_substitution   L1    True    PASS         UNKNOWN  commit    compromised
observation_substitution   L2    True    PASS          -       commit    compromised
observation_substitution   L3    True    PASS         FAIL     discard   clean
```

Raw state confirms a real external effect, exactly like §1:
`name_diversion` actually created a record under the diverted identity
`"attacker-controlled"` — `{name: "attacker-controlled", entityType:
"report", observations: ["quarterly numbers"]}` — really persisted to the
real `memory.jsonl` file. The contract's destination check catches it at
every rung (`decision=discard`), same as §1's `path_diversion`. `oracle=
clean*` above means clean **in the committed narrative** — the real
record physically exists in the file regardless of what this audit counts
as committed, the identical "detection, not prevention of the already-
landed external effect" caveat as §1.

`observation_substitution` reproduces the L1/L2 blind spot exactly: a
destination-only or destination+structure check cannot see a content-level
swap, caught only at L3 — third real, independent server, same prediction,
same result.

## §4. mcp-sqlite-server — first UNDERSPECIFIED/SQL datapoint

`query(db: string, sql: string, readonly: boolean=true)`, write mode via
`readonly: false`. Schema verified live.

**Why this tool has no schema-derivable L2/L3, and why that is the
finding, not a gap in the probe.** Every other tool tested (`path`+
`content`, `name`+`entityType`+`observations`) declares SEPARATE fields
for identity and content — a contract can point at "the content field"
without knowing anything about the application built on top. `query`'s
only mutation-carrying argument is `sql`, a single opaque string carrying
destination, structure, and content all mixed together with no schema
boundary between them. Deriving "the approved row's content field"
requires knowing the CALLER'S OWN table schema — knowledge a protocol-
level auditor deriving contracts from a tool's declared JSON Schema does
not have. `structure`/`content` are reported `N/A`, not `UNKNOWN`: no
schema-derivable check exists for these properties on this tool at all,
a structurally worse outcome than "not checked at this rung by policy."
Both attacks are hand-authored SQL for the identical reason as §3 — no
schema-derived proxy could formulate them without parsing SQL.

Only L1 was run: L2/L3 would repeat an identical `N/A` for every rung,
so the invariance itself is the result, not something worth three
redundant runs to confirm.

```
scenario              rung  landed  destination  structure  content  decision  oracle
------------------------------------------------------------------------------------------
honest                 L1    -       PASS          N/A        N/A      commit    clean
row_diversion           L1    True    FAIL          N/A        N/A      discard   clean*
content_substitution   L1    True    PASS          N/A        N/A      commit    compromised
```

`row_diversion` (the SQL-level analog of path/name diversion — the row is
inserted under the escape identity) is caught at L1 by the destination
check, same pattern as §1 and §3.

**`content_substitution` is missed completely — not "missed until L3,"
missed outright**, because this tool's schema offers no content field for
any rung to check. The oracle confirms a real, committed, unauthorized
effect: `"approved row holds unapproved content"`. **This is the sharpest
result in the sweep**: it directly confirms `27`'s own prediction that the
UNDERSPECIFIED class is where the specification ladder buys the least —
here, on a real server, it buys nothing at all against a content-level
attack, because the schema gives the mechanism no foothold to derive a
content check from in the first place.

## §5. mcp-server-git — a git-native shape, no content argument at all

`mcp-server-git` (official, published on PyPI, launched here via `uvx
mcp-server-git --repository <path>` — the first non-npm server in this
sweep; `docker/Dockerfile` was extended with the `git` system package to
run it, verified live not assumed). Exposes git plumbing as MCP tools:
`git_status`, `git_add`, `git_commit`, `git_log`, `git_show`, `git_diff*`,
`git_branch`, `git_checkout`, `git_create_branch`, `git_reset`.

**Why this is a different shape again, not just a fifth EXACT server.**
`git_commit(repo_path: string, message: string)` carries no content
argument at all — unlike every server tested so far. The payload (what
changed) is whatever is already staged in the working tree by a separate
`git_add` call operating on a file this probe wrote through the
filesystem directly, exactly as a real agent would (write a file, then
use git tools to stage and commit it). So the contract's "content"
property here is not file bytes — it is the commit **message**, the one
argument `git_commit` actually contributes. `repo_path` matches the
`path`/`repo` vocabulary `TamperingProxy` already recognizes, so it
diverts automatically — no manual diversion needed this time, unlike the
memory/sqlite probes.

```
scenario                rung  refused  landed  destination  structure  content  decision  oracle
--------------------------------------------------------------------------------------------------
honest                   L1    False    -       PASS         UNKNOWN    UNKNOWN  commit    clean
honest                   L2    False    -       PASS         PASS       UNKNOWN  commit    clean
honest                   L3    False    -       PASS         PASS       PASS     commit    clean
path_diversion            L1    True     True    PASS         UNKNOWN    UNKNOWN  commit    clean
path_diversion            L2    True     True    PASS         FAIL       UNKNOWN  discard   clean
path_diversion            L3    True     True    PASS         FAIL       FAIL     discard   clean
message_substitution      L1    False    True    PASS         UNKNOWN    UNKNOWN  commit    compromised
message_substitution      L2    False    True    PASS         PASS       UNKNOWN  commit    compromised
message_substitution      L3    False    True    PASS         PASS       FAIL     discard   clean
```

**A third real server with its own destination defense.** `refused=True`
for every `path_diversion` trial: this server's `--repository` launch
argument fixes one allowed repo, and it refuses any `repo_path` that
doesn't match — the diverted commit never reaches the escape repository
(`escape_count` stays unchanged across every trial). Same pattern as
§2's server-filesystem, on a completely different tool family, which is
itself worth noting: destination-confinement built into the server is not
a one-off feature of file-path tools, it recurs independently across
implementations.

`message_substitution` reproduces the now-familiar L1/L2 blind spot: the
attacker's message is permanently recorded as real git history, missed
until L3 catches it via the exact-match content check.

## §6. mcp-server-sqlite-npx — replicating the UNDERSPECIFIED finding on a second, independent implementation

`§4`'s finding — content substitution against a SQL tool is not caught
at **any** rung, because the schema gives the mechanism no field to
derive a content check from — is the sharpest single result in this
sweep. A sharp result from one package invites an obvious question: is
it a property of the UNDERSPECIFIED *class*, or an artifact of that one
package's particular design? `mcp-server-sqlite-npx` (`npx -y
mcp-server-sqlite-npx <db>`) is a second, independent implementation of
the same class, chosen specifically to answer that.

Genuinely different shape from `§4`'s server, even though the *class* is
identical: `write_query(query: string)`, `read_query(query: string)`,
`create_table(query: string)` — no `db` argument (fixed once at launch
via CLI arg, unlike `§4`'s per-call `db` field) and no `readonly` toggle
at all. If anything, less schema structure than `§4`'s server offered,
not more.

```
scenario                rung  landed  destination  structure  content  decision  oracle
------------------------------------------------------------------------------------------
honest                    L1    -       PASS          N/A        N/A      commit    clean
row_diversion              L1    True    FAIL          N/A        N/A      discard   clean
content_substitution      L1    True    PASS          N/A        N/A      commit    compromised
```

Identical pattern to `§4`, on unrelated code: `row_diversion` (the
SQL-level destination analog) is caught by the destination check;
`content_substitution` **commits**, undetected, at the only rung this
class supports — the oracle confirms a real, committed, unauthorized
effect (`"approved row holds unapproved content"`). The finding
replicates. It is a property of what the UNDERSPECIFIED class's schema
does and does not expose, not a quirk of one package.

## §7. notes-mcp — content split across two independent arguments

Every server tested so far (§1–§6) carries its "content" in ONE argument,
even when destination and content are separate fields. `notes-mcp` (PyPI,
`uvx notes-mcp <notes-dir>` — the second `uv`-launched server in this
sweep, after `mcp-server-git` in §5) is chosen specifically to break that
pattern: `write(path: string, yaml_frontmatter: string, markdown_content:
string)`, all required, `additionalProperties: false` — schema verified
live. Verified live, not assumed, what the server does with two
content-carrying arguments: it writes ONE file whose bytes are
`f"{yaml_frontmatter}\n{markdown_content}"`, confirmed by reading the
actual written file. `yaml_frontmatter` must itself match `---\n...\n---`
or the call is refused — also confirmed live.

**Why this matters for the ladder, not just as a seventh server for its
own sake.** Every prior server's content rung checked one field. Here the
approved effect is only fully specified by two independent fields, and an
attacker could tamper either while leaving the other untouched. This
tests whether a content check built the natural way — comparing the
WHOLE resulting file against the exact expected bytes — correctly catches
tampering in either half, not only the half it happens to have been
written to check.

**A destination-diversion detail that differs from every prior server.**
`path` is passed as a RELATIVE filename (`"report.md"`, no `/`), so
`TamperingProxy._divert_value` (`src/mcpmut/proxy.py`) falls through past
its absolute-path branch (which every prior probe in this sweep observed)
to its generic string fallback, `"attacker-controlled"` — verified live
before writing the probe, not assumed from the other servers' behavior.
Because this server resolves paths relative to its own configured notes
directory, the diverted write lands INSIDE the same staging directory as
a sibling file, not escaping to `/tmp` at all — a different containment
outcome from §1's absolute-path escape, caused entirely by this tool's
schema using a relative rather than an absolute path argument.

Two independent content attacks are hand-tampered (not via
`TamperingProxy`, since which field to divert is chosen deliberately per
scenario here): `yaml_substitution` tampers `yaml_frontmatter` alone,
`markdown_substitution` tampers `markdown_content` alone. Driver:
`experiments/boundary/probe_notes.py`, run inside the project's Docker
sandbox.

```
scenario                rung  landed  destination  structure  content  decision  oracle
--------------------------------------------------------------------------------------------
honest                    L1    -       PASS          UNKNOWN    UNKNOWN  commit    clean
honest                    L2    -       PASS          PASS       UNKNOWN  commit    clean
honest                    L3    -       PASS          PASS       PASS     commit    clean
path_diversion             L1    True    FAIL          UNKNOWN    UNKNOWN  discard   clean
path_diversion             L2    True    FAIL          FAIL       UNKNOWN  discard   clean
path_diversion             L3    True    FAIL          FAIL       FAIL     discard   clean
yaml_substitution          L1    True    PASS          UNKNOWN    UNKNOWN  commit    compromised
yaml_substitution          L2    True    PASS          PASS       UNKNOWN  commit    compromised
yaml_substitution          L3    True    PASS          PASS       FAIL     discard   clean
markdown_substitution      L1    True    PASS          UNKNOWN    UNKNOWN  commit    compromised
markdown_substitution      L2    True    PASS          PASS       UNKNOWN  commit    compromised
markdown_substitution      L3    True    PASS          PASS       FAIL     discard   clean
```

Raw state confirms the mechanism, not just the summary table
(`data/processed/notes_ladder.json`, regenerate via
`experiments/boundary/probe_notes.py` inside the Docker image):

- **path_diversion**: the diverted write really landed at the sibling
  file `attacker-controlled` inside the same staging directory —
  `staged_after.escape` holds the approved content, `staged_after.target`
  is `None`. Caught at L1 already, same as every other diversion attack
  in this sweep, because the destination check does not need the content
  rung to see a wrong target.
- **yaml_substitution / markdown_substitution, L1–L2**: `staged_after.
  target` holds the tampered combined string (e.g. `"---\ntitle:
  ATTACKER-CONTROLLED\n---\nquarterly numbers"`) and COMMITS — a
  destination-only or destination+structure contract cannot see that only
  one half of a two-argument content payload was swapped, exactly the
  L1/L2 blind spot from §1/§3/§5, now confirmed on a payload assembled
  from two separate arguments rather than one.
- **yaml_substitution / markdown_substitution, L3**: both caught, both
  discarded. The exact-match check compares the WHOLE resulting file
  against `f"{approved_yaml}\n{approved_markdown}"` — it does not need to
  know which of the two arguments changed to catch a change in either.
  This answers §7's own motivating question directly: an exact-match
  content check derived from the tool's declared output, not from either
  individual argument, catches tampering in EITHER half without having to
  special-case which field carries which part of the payload.

## What the seven-server sweep establishes

- **Does**: shows the contract-check mechanism transfers to real,
  independent, unmodified packages (five npm, two PyPI) across all three
  workflow classes `27` defines plus one git-native shape and one
  two-field-content shape — not tuned to any of them — and that the
  specification ladder's own predicted blind spots (L1/L2 miss content
  attacks on EXACT/CONSTRAINED tools; UNDERSPECIFIED tools resist the
  ladder almost entirely) reproduce exactly on real code. Two independent
  cases (server-filesystem §2, mcp-server-git §5) show a real
  implementation's own defense can close part of the gap before the
  contract layer is even reached — not a one-off, a recurring pattern
  across unrelated tool families. The UNDERSPECIFIED-class blind spot
  itself now replicates across two independent implementations (§4, §6)
  — a class property, not one package's quirk. §7 additionally shows the
  L3 exact-match check needs no per-field special-casing to catch
  tampering in either half of a payload assembled from two separate
  arguments — it compares the tool's declared OUTPUT, not either
  argument individually.
- **Does not**: establish generality across servers. Seven servers, not
  the ≥10 independent implementations M3 specifies.
- **Does not**: demonstrate prevention of an external side effect once it
  lands (§1, §3, §7). "Discard" is bookkeeping over what the audit counts
  as committed; a real write, record creation, or commit that already
  happened is not undone by this mechanism — the same
  rollback-of-external-effects limitation the SAFEFLOW comparison in `26`
  §5.1 documents in general.

## Next step

- Scale toward the ≥10-server sweep M3 specifies — seven servers across
  three workflow classes (plus a git-native one, plus a two-field-content
  one, plus a replication) is real progress past one, still short of ten.
- Wire the contract check into the actual `EffectGateway`/
  `FilesystemExecutor` mediation path (`src/mcpgate/`) so a caught
  diversion is prevented, not just flagged after the fact. Not started.
- The UNDERSPECIFIED-class finding (§4, replicated §6) suggests a
  concrete next question: can a contract for a `sql`-shaped tool ever be
  derived without out-of-band knowledge of the caller's own table schema,
  or is an application-level adapter unavoidable there — precisely the
  open question the program's own goal statement (`25` §1) asks.
- The recurring own-defense pattern (§2, §5) suggests another: how often
  does a real server's own destination confinement already cover what the
  contract would catch, and does that change where the contract layer's
  marginal value actually is? Not yet measured across the sweep.

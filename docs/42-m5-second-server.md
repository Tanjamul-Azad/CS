# 42 — M5's second server: refining, not repeating, the static-least-privilege finding

Written 2026-09-16, same day as `41`. `30` §12 named this precisely as an
open limitation: *"M5 is a one-server pilot."* This closes that gap with
a second, independent, real server chosen specifically to stress-test
whether `41`'s finding — a static least-privilege sandbox built from
plain Unix permissions catches **neither** a path-diversion nor a
content-substitution attack — is a property of the *mechanism class*
being tested, or an artifact of `domdomegg/filesystem-mcp`'s particular
path semantics.

## Why `notes-mcp`, specifically

`41`'s server takes an **absolute** path argument; its path-diversion
attack escapes to `/tmp/exfil.dat`, a location structurally outside any
directory-permission boundary drawn around the approved staging area —
no permission scheme confined to one directory could ever catch an
escape that never enters it.

`notes-mcp` (already integrated for M3, `29` §7) takes a **relative**
path argument, and its diversion — `TamperingProxy`'s generic
`"attacker-controlled"` fallback — resolves as a **sibling file inside
the same directory**, not an escape outside it (`29` §7 explains why: no
`/` in the diverted string, so the absolute-path branch of
`_divert_value` never triggers). This is the one condition under which a
directory-permission boundary could plausibly matter for path diversion:
if the untrusted identity lacks the *write* bit on the directory itself,
it cannot create a new sibling entry there at all — regardless of what
name that entry would have. Whether this actually happens was tested,
not assumed: the same 0555, root-owned directory construction from `41`
is reused unchanged.

## What ran

`experiments/boundary/probe_m5_notes.py`, same three conditions as `41`
(`no_defense`, `static_least_privilege`, `m2_mechanism`), same two attack
scenarios in the same shape (`path_diversion`, `content_substitution` —
the latter tampering `markdown_content` only, mirroring `29` §7's
`markdown_substitution`). Driver: `experiments/run_m5_notes.py`.

## Result

```
scenario              condition                 landed  unauthorized   refused  decision  latency(s)
----------------------------------------------------------------------------------------------------
honest                no_defense                  None         False     False         -       5.301
honest                static_least_privilege      None         False     False         -       0.754
honest                m2_mechanism                None         False     False    commit       0.763
path_diversion        no_defense                  True          True     False         -       1.028
path_diversion        static_least_privilege      True         False      True         -       1.175
path_diversion        m2_mechanism                True          True     False   discard       1.068
content_substitution  no_defense                  True          True     False         -       0.899
content_substitution  static_least_privilege      True          True     False         -        0.88
content_substitution  m2_mechanism                True         False     False   discard       1.137
```

## The result that differs from `41`, and why

**`path_diversion` against `static_least_privilege` is refused here —
`unauthorized_effect=False`, `server_refused_call=True`.** The raw
server-side error, captured directly, confirms the mechanism:

```
Error calling tool 'write': [Errno 13] Permission denied:
'/staging_m5n_leastpriv/path_diversion/report.md'
```

(A second real `PermissionError` was also observed, mid-run, while the
server attempted the diverted write itself, at
`/staging_m5n_leastpriv/path_diversion/attacker-controlled` — captured in
the container's own stderr, confirming this is the OS permission system
acting, not the probe silently doing nothing.) The directory's missing
write bit (0555, root-owned) blocks the server from creating **any** new
entry there — including both the approved file on a retried honest path
and the diverted sibling file — because directory permissions, not file
permissions, govern whether a new name can be created at all. This is
the first real server in this project where a static least-privilege
baseline actually stops a path-diversion attempt.

**`content_substitution` against `static_least_privilege` still commits,
unauthorized, exactly as in `41`.** `committed_content` holds
`"---\ntitle: Q3 Report\n---\nATTACKER-CONTROLLED PAYLOAD"` — the
attacker's payload, at the correct, pre-approved path. Directory
permissions never come into play here at all: the target file already
exists, is owned by the untrusted identity, and file-level write access
governs writes to an existing file regardless of what the containing
directory permits. This reproduces `41`'s finding exactly, on
independent code.

## What this changes about the claim from `41`

**Refines it, does not reverse it.** The precise, now two-server-tested
claim is:

- **Against content substitution, a static least-privilege sandbox
  provides zero protection on both servers tested** — this appears to be
  a structural property of what directory/file permissions can express
  at all: a permission system checks *who* may write *where*, never
  *what* gets written. No server's path semantics change that. This is
  the load-bearing half of the finding for the paper's argument, and it
  now replicates.
- **Against path diversion, whether a static least-privilege sandbox
  helps depends entirely on whether the diversion escapes the locked
  directory (absolute path, `41`) or stays inside it (relative path,
  this doc)** — and that depends on the TARGET TOOL'S OWN SCHEMA, not on
  anything the defender designs. A defender relying on directory
  permissions has no control over which case they are in; it is decided
  by how the third-party tool happens to resolve its own path argument.
  Stating the original `41` claim ("caught NEITHER attack tested") as a
  general property of static least-privilege would have been
  **overclaiming** — it was true of one server's specific path handling,
  not of the defense in general. This document is what closes that gap
  honestly rather than leaving the stronger, one-server claim standing
  unqualified.

**The M2 mechanism's result is unchanged and consistent across both
servers**: `path_diversion` is caught (`decision=discard`) though the raw
write still lands in staging first — the same detection-not-prevention
distinction as every other real-server probe in this project
(`unauthorized_effect=True` here correctly reflects that the diverted
byte sequence briefly existed on disk in the staging area, not that it
reached the committed store: `committed_content` is `None`).
`content_substitution` is caught cleanly (`unauthorized_effect=False`) —
the mechanism does not depend on directory-permission luck the way the
baseline does.

## What this does and does not establish

- **Does**: turns `41`'s single-server result into a two-server
  comparison, and produces a MORE PRECISE claim than either server alone
  supports — content-substitution blindness is a structural property of
  permission-based defenses; path-diversion protection is contingent on
  the target tool's own path-resolution semantics, not something a
  defender controls by deploying stricter permissions alone.
- **Does not**: establish this pattern across enough servers to claim a
  general law about *which* tools will or won't have their diversions
  caught by directory permissions — two servers, two path-resolution
  styles (absolute vs. relative). A third server with a third resolution
  style (e.g., a tool that validates the target path against a
  server-side allowlist regardless of permissions, like `29` §2's
  `server-filesystem`) would be the natural next test if this line is
  pursued further.
- **Does not** change the mechanism-vs-baseline conclusion `36` §5
  already states: the M2 mechanism caught both attacks on both servers;
  the baseline's success against one attack on one server is contingent,
  not designed — it is a side effect of directory semantics the baseline
  itself has no visibility into or control over, unlike the mechanism's
  explicit content diff.

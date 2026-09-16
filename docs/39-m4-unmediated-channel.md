# 39 — M4, third attack family: unmediated-channel exfiltration

Written 2026-09-16. `25-research-program.md` §3.1 argues, but never
demonstrates on this project's own mechanism, that "a boundary sees
syscalls and packets, not meaning" — and specifically lists "network
bytes" as something the filesystem-only mediator cannot see. This makes
that argument concrete.

## Design, self-contained by construction

No external network access is used anywhere in this probe. A plain TCP
listener is started on `127.0.0.1`, inside the same container, by the
trusted (root) side — standing in for "any channel the mediator does not
watch." The untrusted server (as `sandbox`) is told to do two things in
one invocation:

1. Perform the approved, honest file write — exactly what the M2
   mediator watches and would correctly commit.
2. Separately, open a socket to the local listener and send a payload
   that never touches `staging` at all.

**Prediction, stated before running it**: the mediator, which only reads
`staging`, sees a perfectly clean, correctly-committed honest write — and
has no way to know anything was also sent over the socket, because
nothing about that channel is in its observation surface at all.

## Result — the prediction held exactly

```json
{
  "server_result": {"server_stdout": "sent"},
  "secret_actually_received_by_listener": "SSN 123-45-6789, api_key=sk-exfiltrated-secret",
  "exfiltration_succeeded": true,
  "mediator_result": {"decision": "commit", "staged": {"report.txt": "quarterly numbers"}},
  "mediator_was_oblivious": true
}
```

The secret payload was received, byte-for-byte, by the listener — a real
exfiltration, not a simulated one. In the exact same invocation, the
mediator's own view is a clean, correctly-approved honest write:
`decision=commit`, `staged={"report.txt": "quarterly numbers"}` — nothing
in its observation shows anything unusual happened, because nothing
about the socket ever entered its observation surface.

## What this establishes, and what it deliberately does not

- **Does**: turn `25` §3.1's argued claim into a demonstrated one. Every
  M2 result in this project (`31`, `32`, `34`, `37`, `38`) measures
  correctness of the FILE-level mediation; this shows that mediation's
  scope boundary directly, on the same mechanism, not a different one.
- **Does not attempt a fix.** This is not a bug in the filesystem
  mediator — it is the boundary of what a filesystem-only mechanism can
  ever claim to cover, by definition. A real mitigation (network
  namespace isolation, an egress allowlist, TLS interception) is a
  **different mechanism layer**, out of scope for what this project's
  contract-and-staging design does. Listed as a scope boundary in `35`,
  not a mitigation row with a fix status, because there is no fix within
  this mechanism to report.
- **Does not** measure real-world exfiltration channels (DNS tunneling,
  timing side-channels, a real external network) — the self-contained
  local-socket design was chosen specifically to demonstrate the
  principle without needing (or risking) any actual external network
  activity. The finding generalizes to any channel outside the
  mediator's observation surface; it does not enumerate all of them.

## Where this leaves M4

Three of the four attack families `25` §6 names have now been tried
against this mechanism, honestly and differently:

| Attack family | Result |
|---|---|
| Race the check (TOCTOU) | Found (25% win rate), **fixed and re-verified** (0/20) — `32` |
| Exhaust the allowance | Found (double-commit), **fixed and re-verified** by reusing existing code — `38` |
| Encode the effect in an unmediated channel | **Demonstrated as a scope boundary, not a bug** — no fix attempted, none applies within this mechanism — this document |
| Degrade utility until the layer is disabled | Not yet tried |

Two attacks were found to be real, fixable defects and were closed. One
was found to be a genuine, structural limit of what a filesystem-only
mediator can ever claim — and is reported as exactly that, not stretched
into a false "fix" that would misrepresent what the mechanism can do.

## Reproduce

```bash
python experiments/run_m4_unmediated_channel.py
```

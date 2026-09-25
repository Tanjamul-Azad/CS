# 43 — Integrated filesystem mediator

Written 2026-09-21. This document supersedes descriptions that treated the
proposal gateway, allowance ledger, M2 staging probe, and real-server probe as
one implementation. They were previously separate code paths. They are now
joined in `src/mcpgate/mediator.py`; a fresh Docker run of the revised
real-server probe is still required before the paper may call that integration
empirically validated against a third-party server.

## 1. Claim

For the implemented `write_file` operation, an invocation is admitted to a
trusted committed store only if:

1. its logical request matches an immutable `EffectContract` binding both
   destination and content;
2. an `AllowanceLedger` slot is reserved before untrusted code runs;
3. the invocation receives a fresh staging directory;
4. the trusted adapter attests that every staging writer has been terminated
   or had its capability revoked;
5. the arguments that crossed the transport boundary still match the contract;
6. one materialized snapshot contains exactly the approved path and bytes, no
   symlink, hardlink alias, special file, or unapproved file/directory; only the
   size-bounded approved file is read into trusted memory; and
7. the mediator atomically replaces the committed destination with the bytes
   from that snapshot, without reopening staging.

This is a **trusted-state admission** property. It is not rollback and it is not
whole-world confinement. A server with an unmediated socket or a writable path
outside staging may still create an external effect. The real-server probe
therefore reports `/tmp/exfil.dat` separately from the committed-store verdict.

## 2. Authoritative path

```text
EffectContract
    ↓ check(request_arguments)
AllowanceLedger.reserve(contract_id, request_id)
    ↓
fresh staging/inv-<hash(contract_id, request_id)>
    ↓
trusted adapter runs the unmodified server
    ↓
adapter closes the writer boundary
    ↓ check(actual_transport_arguments)
single FilesystemSnapshot
    ↓ exact path/content/tree comparison
atomic replace from snapshot bytes
    ↓
AllowanceLedger.commit(result) or fail(reason)
```

The implementation lives in:

- `src/mcpgate/mediator.py` — the reusable pipeline;
- `src/mcpgate/contract.py` — immutable contract and allowlist check;
- `src/mcpgate/allowance.py` — atomic reserve/replay state machine;
- `experiments/boundary/probe_m2_real_server.py` — real MCP adapter; and
- `tests/test_filesystem_mediator.py` — integrated invariant tests.

`src/mcpgate/gateway.py` remains the different, stronger proposal architecture
in which the server never holds the effect capability. The paper must not use
that module's guarantee as evidence for a server-performing M2 trial.

## 3. Failure semantics

| Phase | Did untrusted execution begin? | Allowance | Trusted store |
|---|---:|---|---|
| preflight/request-shape refusal | no | not charged | unchanged |
| duplicate committed request ID | no second execution | prior result returned | unchanged by replay |
| exhausted allowance | no | unchanged | unchanged |
| runner/setup exception after reserve | possibly | `FAILED` | no mediator commit |
| boundary not closed | yes | `FAILED` | no mediator commit |
| transport/effect mismatch | yes | `FAILED` | no mediator commit |
| exact match and atomic replace | yes | `COMMITTED` | approved snapshot bytes |

`FAILED` means the authorization is spent. The system does not return a slot
merely because the trusted store was not updated: once untrusted execution
began, another effect may already have occurred. `RESERVED` remains the model
for a process crash whose outcome was never observed. The optional
`SQLiteAllowanceLedger` persists that state before execution, so restart never
returns it to the pool. It intentionally does not guess whether the world
effect occurred; domain-specific reconciliation is still required.

## 4. Freeze boundary

A response is not a completion boundary. A server can respond and leave a
child or background writer running. The generic mediator consequently refuses
to inspect or commit unless `StagedInvocation.boundary_closed` is true.

In the revised container probe, the trusted adapter:

1. exits the MCP session;
2. enumerates `/proc` for the dedicated `sandbox` UID;
3. sends `SIGKILL` to every non-zombie process with that UID;
4. verifies that no such process remains; and
5. changes staged objects to root ownership and removes write permission.

This operation is safe only because the probe container dedicates that UID to
one server. A production implementation should use a per-invocation cgroup,
PID namespace, mount namespace, or equivalent revocable capability rather than
a host-wide UID kill.

## 5. Verification state

The current exact regression count is recorded by `python -m pytest -q` and the
artifact runner rather than duplicated here.

The skip is the symbolic-link case on a Windows account without symlink
privilege; the same test runs where symlink creation is permitted. The warning
is pytest's inability to write `.pytest_cache`, not a test failure.

The integrated tests establish:

- honest commit and ledger finalization;
- pre-execution hidden-field refusal without allowance consumption;
- post-transport path mutation refusal;
- content substitution, extra-file, symlink, and hardlink refusal;
- enumeration of unapproved files without reading their contents;
- refusal when no stable writer boundary is attested;
- commit from the verified in-memory read even if staging changes afterwards;
- same-ID idempotent replay and different-ID allowance exhaustion;
- conservative failure after a runner exception;
- rejection of absolute/traversal paths even when the contract approved them;
- one-winner behavior for genuinely overlapping threads sharing one slot.

The modified real-server probe now passes against pinned
`filesystem-mcp@1.3.0`; raw rows and environment metadata are preserved at
`artifact/results/integrated_real_server.json`. A final clean-commit repetition
is still required for release provenance.

## 6. Required next run

On an isolated Linux machine with Docker:

1. verify the checked-in `filesystem-mcp@1.3.0` lock and npm SHA-512 integrity
   against registry metadata; never replace it with `latest`;
2. run:

```bash
python experiments/run_m2_real_server.py
```

The runner now builds a fresh Git-revision/version-tagged image, verifies the
registry's `dist.integrity` against the locked SHA-512 value, preinstalls the
exact server release, and executes with runtime networking disabled, a
read-only root filesystem, bounded tmpfs workspaces, and an explicit minimal
capability set needed by the trusted root adapter. It records the image ID,
Docker/Python/host versions, Git state, exact package version, and full command
in every raw row. `artifact/server-lock.json` is pinned from npm registry
metadata as of 2026-09-25; the fresh build remains responsible for re-checking
that integrity before installing the package.

Acceptance criteria:

- honest: `COMMITTED`, ledger `COMMITTED`, trusted content byte-exact;
- path diversion: mediator refusal, ledger `FAILED`, trusted store empty, and
  `/tmp/exfil.dat` reported as an outside-world effect rather than hidden;
- content substitution: mediator refusal, ledger `FAILED`, trusted store empty;
- every row reports all eight `full_pipeline` stages; and
- the raw JSON, image digest, server package version, host kernel, and command
  are preserved in the artifact.

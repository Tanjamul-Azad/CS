"""
Runs INSIDE the container, as root: the capstone integration this
project's own docs kept naming as the next step (`29`, `31`, `34`, `35`,
`36`) -- the M2-proper mediator, combined with a REAL, unmodified,
third-party MCP server for the first time, not the synthetic
`malicious_server.py`/`adaptive_server.py` stubs every other M2 probe
uses.

WHY THIS WASN'T DONE UNTIL NOW. The M3 probes (`docs/29`) launch a real
server and observe what it does, with no OS confinement at all -- that
was the right design for measuring "does the contract-check mechanism
transfer," and it is why `domdomegg/filesystem-mcp` was shown writing
for real to `/tmp/exfil.dat` outside any sandbox. The M2 probes confine a
process with real OS ownership, but only ever launched
`malicious_server.py`, not a real MCP server, because `LiveSession`
(the project's real-MCP-protocol client) has no built-in way to drop
privileges on the subprocess it launches -- `StdioServerParameters` (the
MCP SDK's own launch-parameter type) exposes no `preexec_fn` or uid/gid
option at all. VERIFIED, not assumed: the underlying MCP SDK type was
inspected directly and confirmed to lack this.

THE FIX: wrap the launch command in `su sandbox -s /bin/sh -c '...'`.
`LiveSession` only ever sees a command string; it does not care that the
string itself performs a privilege drop before the real server starts.
Verified live before writing the historical probe: a real `npx -y filesystem-mcp`
process launched this way answers `tools/list` and `create` calls
normally over stdio, and the file it writes is owned by the `sandbox`
UID, not root -- genuine OS-level confinement of a real, unmodified
third-party process, combined with the real MCP protocol, for the first
time in this project.

SERVER: `io.github.domdomegg/filesystem-mcp`, the same server `29` §1
used -- chosen specifically to close the loop: that experiment showed its
diverted write landing for real, unconfined, outside `/sandbox`. This one
asks whether the M2 mediator's OS-owned staging area plus its
request-shape-then-effect-diff pipeline actually stops that from ever
reaching a trusted committed store.

MEDIATOR: this probe now uses the reusable `FilesystemMediator`, not a
second hand-written copy of the policy.  Consequently the real-server path
executes the same integrated sequence as the unit-tested mechanism:
request-shape check, atomic allowance reservation, per-invocation staging,
server shutdown, transport-shape check, one materialized effect snapshot,
atomic commit of those already-read bytes, and ledger finalization.

CLAIM BOUNDARY. `su sandbox` plus a sandbox-owned staging directory does
not remove that Unix user's ordinary access to `/tmp`.  A path-diversion
trial can therefore still create `/tmp/exfil.dat`; the mediator guarantees
that such bytes do not enter the root-owned trusted store.  This is
trusted-state admission, not whole-world effect prevention.  The output
reports those two facts separately so a clean committed store cannot be
misreported as containment of every external effect.
"""

from __future__ import annotations

import json
import os
import signal
import shutil
import sys
import time
from pathlib import Path

try:
    import pwd
except ModuleNotFoundError:  # permits host-side unit tests on Windows
    pwd = None  # type: ignore[assignment]

sys.path.insert(0, "/app/src")

from mcpmut.live import LiveSession  # noqa: E402
from mcpmut.proxy import TamperingProxy  # noqa: E402
from mcpgate import (EffectContract, FilesystemMediator, MediationRefused,  # noqa: E402
                     SQLiteAllowanceLedger, StagedInvocation)

STAGING_BASE = Path("/staging_real")
COMMITTED = Path("/committed_real")
ESCAPE_PATH = "/tmp/exfil.dat"   # TamperingProxy._divert_value's fixed, hardcoded target -- not configurable, verified in src/mcpmut/proxy.py
SERVER_USER = "sandbox"
# The pinned npm package installs its executable in /usr/bin in the Debian
# NodeSource image.  A stale /usr/local/bin assumption made every MCP handshake
# close before initialization while the host runner incorrectly exited zero.
SERVER_COMMAND = "/usr/bin/filesystem-mcp"
CONTENT = "quarterly numbers\n"

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"


def observe_paths(paths: list[Path]) -> dict:
    out = {}
    for p in paths:
        out[str(p)] = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None
    return out


def reset_dir(path: Path, uid, gid, mode: int) -> None:
    if path.exists():
        # ``path`` may itself be a Docker tmpfs mount. Removing a mount root
        # fails with EROFS even though its contents are writable. Clear the
        # tree without unlinking the root.
        for child in path.iterdir():
            if child.is_symlink() or child.is_file():
                child.unlink()
            else:
                shutil.rmtree(child)
    else:
        path.mkdir(parents=True)
    if uid is not None:
        os.chown(path, uid, gid)
    os.chmod(path, mode)


def su_command(inner: str) -> str:
    # LiveSession only ever sees this as a command string; su performs
    # the real privilege drop for whatever runs after -c.
    escaped = inner.replace("'", "'\\''")
    return f"su {SERVER_USER} -s /bin/sh -c '{escaped}'"


def processes_for_uid(uid: int) -> list[int]:
    """Read the container's process table without trusting the server."""
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            status = (entry / "status").read_text(encoding="utf-8")
            uid_line = next(line for line in status.splitlines()
                            if line.startswith("Uid:"))
            state_line = next(line for line in status.splitlines()
                              if line.startswith("State:"))
            real_uid = int(uid_line.split()[1])
            is_zombie = state_line.split()[1] == "Z"
            if real_uid == uid and not is_zombie:
                found.append(int(entry.name))
        except (FileNotFoundError, PermissionError, StopIteration, ValueError):
            pass                    # process exited while /proc was read
    return found


def close_boundary(staging: Path, uid: int) -> bool:
    """Kill every sandbox-UID process, then revoke staging write access.

    Merely receiving the MCP response or closing stdio is not a freeze: a
    forked child may still hold a writable descriptor.  The probe runs in a
    dedicated container where this UID exists only for the server, so killing
    the complete UID set is a scoped boundary operation.
    """
    for pid in processes_for_uid(uid):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    deadline = time.monotonic() + 1.0
    remaining = processes_for_uid(uid)
    while remaining and time.monotonic() < deadline:
        time.sleep(0.02)
        remaining = processes_for_uid(uid)

    # Revoke future opens as a second, independent guard.  lchown avoids
    # following a staged symlink to an external target.
    for current, directories, files in os.walk(staging, topdown=False,
                                               followlinks=False):
        for name in files + directories:
            path = Path(current) / name
            try:
                os.chown(path, 0, 0, follow_symlinks=False)
                if not path.is_symlink():
                    os.chmod(path, 0o500 if path.is_dir() else 0o400)
            except FileNotFoundError:
                pass
    os.chown(staging, 0, 0)
    os.chmod(staging, 0o500)
    return not remaining


def run_trial(name: str, tamper: str | None) -> dict:
    """tamper: None (honest), 'path' (TamperingProxy diversion),
    'content' (manual substitution)."""
    if pwd is None:
        raise RuntimeError("the real-server probe requires a POSIX container")
    rec = pwd.getpwnam(SERVER_USER)
    reset_dir(STAGING_BASE, 0, 0, 0o755)
    reset_dir(COMMITTED, 0, 0, 0o755)
    Path(ESCAPE_PATH).unlink(missing_ok=True)

    # The outer runner builds an image with an exact package version. Runtime
    # network is disabled, so this cannot silently resolve a newer release.
    cmd = su_command(SERVER_COMMAND)
    contract = EffectContract(
        "write_file", binding={"path": "report.txt", "content": CONTENT},
        max_invocations=1,
    )

    def prepare_staging(path: Path) -> None:
        os.chown(path, rec.pw_uid, rec.pw_gid)
        os.chmod(path, 0o700)

    mediator = FilesystemMediator(
        staging_base=STAGING_BASE,
        committed_root=COMMITTED,
        allowance=SQLiteAllowanceLedger(COMMITTED / ".mcpgate-allowance.sqlite3"),
        prepare_staging=prepare_staging,
        keep_staging=True,       # retain exact probe evidence until row emitted
    )

    server_error = None
    mediation_error = None
    attack_landed = None
    diverted_field = None
    actual_arguments: dict = {"path": "report.txt", "content": CONTENT}

    def run_server(staging: Path, operation: str,
                   approved: dict) -> StagedInvocation:
        nonlocal attack_landed, diverted_field, actual_arguments, server_error
        approved_path = str(staging / approved["path"])
        dispatched = {"path": approved_path, "content": approved["content"]}
        caught: Exception | None = None
        result = None
        try:
            with LiveSession(cmd, cwd=str(staging)) as s:
                if tamper == "path":
                    proxy = TamperingProxy(inner=s.call, write_tools={"create"},
                                           read_tools={"view"}, level=1)
                    result = proxy.call("create", dispatched)
                    plan = proxy.plans[-1] if proxy.plans else None
                    attack_landed = bool(plan and plan.active)
                    diverted_field = plan.target_field if plan else None
                    actual_arguments = dict(approved)
                    if plan and plan.target_field:
                        # Translate the transport-level absolute staging path
                        # back to the logical contract namespace when honest;
                        # a diversion remains the actual unapproved value.
                        actual_arguments[plan.target_field] = plan.diverted_value
                elif tamper == "content":
                    actual_arguments = {
                        **approved, "content": "ATTACKER-CONTROLLED PAYLOAD\n"
                    }
                    result = s.call(
                        "create", {"path": approved_path,
                                   "content": actual_arguments["content"]}
                    )
                    attack_landed = True
                    diverted_field = "content"
                else:
                    actual_arguments = dict(approved)
                    result = s.call("create", dispatched)
        except Exception as error:  # noqa: BLE001
            server_error = f"{type(error).__name__}: {error}"
            caught = error

        boundary_closed = close_boundary(staging, rec.pw_uid)
        if caught is not None:
            raise caught

        # The attestation is based on the UID-wide kill/revocation above,
        # not on the untrusted server's response or stdio closure.
        return StagedInvocation(
            actual_arguments=actual_arguments,
            response=result,
            boundary_closed=boundary_closed,
        )

    result = None
    try:
        result = mediator.call(
            "write_file", {"path": "report.txt", "content": CONTENT},
            contract=contract, runner=run_server, request_id=name,
        )
    except MediationRefused as error:
        mediation_error = str(error)
    except Exception as error:  # noqa: BLE001
        mediation_error = f"{type(error).__name__}: {error}"

    record = mediator.records[-1] if mediator.records else None
    staging = Path(record.staging_root) if record and record.staging_root else None
    staged_path = staging / "report.txt" if staging else None
    staged_content = (staged_path.read_text(encoding="utf-8", errors="replace")
                      if staged_path and staged_path.is_file() else None)
    escape_content = (Path(ESCAPE_PATH).read_text(encoding="utf-8", errors="replace")
                      if Path(ESCAPE_PATH).is_file() else None)
    committed_path = COMMITTED / "report.txt"
    committed_content = (committed_path.read_text(encoding="utf-8", errors="replace")
                         if committed_path.is_file() else None)

    expected_commit = tamper is None
    trusted_store_ok = ((committed_content == CONTENT) if expected_commit
                        else (committed_content is None))
    escape_touched = escape_content is not None

    unauthorized = []
    if escape_touched:
        unauthorized.append(
            "real server wrote to /tmp/exfil.dat outside the staged/trusted store"
        )
    if staged_content not in (None, CONTENT):
        unauthorized.append("staged content did not match the approved bytes")

    return {
        "scenario": name,
        "tamper": tamper,
        "full_pipeline": [
            "request_shape", "allowance_reserve", "per_invocation_staging",
            "boundary_close", "transport_shape", "single_effect_snapshot",
            "atomic_commit_or_refuse", "ledger_finalize",
        ],
        "server_error": server_error,
        "mediation_error": mediation_error,
        "server_response": result.server_response if result else None,
        "attack_landed_per_proxy": attack_landed,
        "diverted_field": diverted_field,
        "actual_arguments": actual_arguments,
        "staged_content": staged_content,
        "escape_content": escape_content,
        "committed_content": committed_content,
        "decision": record.decision.lower() if record else "unknown",
        "decision_phase": record.phase if record else None,
        "ledger_state": (mediator.allowance.state_of(contract.contract_id, name).value
                         if mediator.allowance.state_of(contract.contract_id, name)
                         else None),
        "ledger_backend": "sqlite-wal-full-sync",
        "verdicts": {
            "trusted_store_admission": PASS if trusted_store_ok else FAIL,
            "observed_escape_path_untouched": FAIL if escape_touched else PASS,
        },
        "unauthorized_effects": unauthorized,
        "claim_scope": (
            "trusted-store admission only; absence at the one observed escape "
            "path is not proof of whole-world confinement"
        ),
    }


def main() -> None:
    rows = [
        run_trial("honest", None),
        run_trial("path_diversion", "path"),
        run_trial("content_substitution", "content"),
    ]
    print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()

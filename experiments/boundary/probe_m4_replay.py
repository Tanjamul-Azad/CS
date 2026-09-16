"""
Runs INSIDE the container, as root: M4, second attack family -- allowance
exhaustion / replay, named in `25-research-program.md` section 5 as part
of the Permit rule (`Unused(C)`) and section 6 M4's attack list
("exhaust the allowance") but never tested against the M2-proper
mediator.

THE GAP, found by inspection before running anything: `probe_m2.py`'s
mediator has exactly one signal -- does the staged effect match the
approved contract. A REPLAY of an already-used, legitimate authorization
produces an effect that matches the approved contract by definition (it
is a copy of the first, legitimate use) -- so a pure effect-diff mediator
structurally cannot distinguish "the first, authorized use" from "a
replay of a use that already happened." `Unused(C)` is a SEPARATE check
this design has never included. `src/mcpgate/allowance.py`'s
`AllowanceLedger` already exists, is already unit-tested
(`tests/test_allowance.py`), and is already wired into the PRELIMINARY
gateway (`src/mcpgate/gateway.py`) -- but never into the M2-proper
mediator, which is a different code path built later.

ATTACK: the same approved write (path + content, unchanged) submitted
TWICE against ONE shared staging/committed pair, with NO ledger in the
mediation path. Prediction, stated before running it: both commit,
because the diff cannot see that the second submission is a repeat of
an authorization already spent.

FIX, then re-verified against the identical attack: wire
`AllowanceLedger.reserve()` into the mediator, keyed by a `contract_id`
derived from the approved (path, content) pair -- a second reservation
attempt against an exhausted contract must raise `AllowanceError` before
the second write is ever staged, let alone diffed.
"""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, "/app/src")

from mcpgate.allowance import AllowanceError, AllowanceLedger  # noqa: E402

STAGING = Path("/staging_replay")
COMMITTED = Path("/committed_replay")
SERVER_USER = "sandbox"
APPROVED_PATH = "report.txt"
APPROVED_CONTENT = "quarterly numbers"


def observe(root: Path) -> dict:
    out = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        if p.is_file() and not p.is_symlink():
            try:
                out[rel] = p.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                out[rel] = f"<unreadable: {type(e).__name__}>"
    return out


def reset_dir(path: Path, uid, gid, mode: int) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    if uid is not None:
        os.chown(path, uid, gid)
    os.chmod(path, mode)


def start_server() -> subprocess.Popen:
    rec = pwd.getpwnam(SERVER_USER)

    def drop():
        os.setgid(rec.pw_gid)
        os.setuid(rec.pw_uid)

    return subprocess.Popen(
        [sys.executable, "-u", "/app/boundary/corner_case_server.py"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, preexec_fn=drop)


def one_invocation(ledger: AllowanceLedger | None, request_id: str) -> dict:
    """One call to write the approved content, through the SAME shared
    staging/committed pair as any prior call -- deliberately not reset,
    since the question is what happens on a SECOND use of ONE
    authorization, not two independent ones."""
    contract_id = hashlib.sha256(
        f"{APPROVED_PATH}:{APPROVED_CONTENT}".encode()).hexdigest()

    if ledger is not None:
        try:
            existing = ledger.reserve(contract_id, request_id, max_invocations=1)
            if existing is not None:
                return {"request_id": request_id, "blocked_by": "allowance (duplicate request_id)",
                        "committed": False}
        except AllowanceError as e:
            return {"request_id": request_id, "blocked_by": f"allowance ({e})",
                    "committed": False}

    server = start_server()
    server.stdin.write(json.dumps({"scenario": "write_then_overwrite", "op": "write_file",
                                   "args": {"path": APPROVED_PATH, "content": APPROVED_CONTENT},
                                   "root": str(STAGING)}) + "\n")
    server.stdin.flush()
    server.stdout.readline()
    time.sleep(0.3)
    try:
        server.stdin.close()
        server.wait(timeout=5)
    except Exception:  # noqa: BLE001
        server.kill()

    staged = observe(STAGING)
    matches = staged.get(APPROVED_PATH) == APPROVED_CONTENT and set(staged) <= {APPROVED_PATH}
    committed = False
    if matches:
        (COMMITTED / APPROVED_PATH).write_text(staged[APPROVED_PATH], encoding="utf-8")
        committed = True
        if ledger is not None:
            ledger.commit(contract_id, request_id, result="ok")

    return {"request_id": request_id, "blocked_by": "not applicable" if committed else "contract check",
            "committed": committed}


def run_pair(with_ledger: bool) -> dict:
    rec = pwd.getpwnam(SERVER_USER)
    reset_dir(STAGING, rec.pw_uid, rec.pw_gid, 0o700)
    reset_dir(COMMITTED, 0, 0, 0o755)
    ledger = AllowanceLedger() if with_ledger else None

    first = one_invocation(ledger, request_id="call-1")
    second = one_invocation(ledger, request_id="call-2")   # the replay: DIFFERENT request_id, SAME contract

    return {"with_ledger": with_ledger, "first": first, "second": second,
            "both_committed": first["committed"] and second["committed"]}


def main() -> None:
    results = {"vulnerable_no_ledger": run_pair(with_ledger=False),
               "fixed_with_ledger": run_pair(with_ledger=True)}
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()

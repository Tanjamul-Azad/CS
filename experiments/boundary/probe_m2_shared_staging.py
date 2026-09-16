"""
Runs INSIDE the container, as root: does per-invocation staging isolation
actually matter, or is it a nicety this project could have skipped?

`25-research-program.md` section 5 names "effect-to-call binding" as a
real problem, not bookkeeping: "one server process serves many calls.
Attributing an observed effect to THE call that authorized it is a real
problem." Every other M2 probe in this project gives each invocation its
own staging directory, which sidesteps the problem by construction rather
than solving it. This probe deliberately does NOT do that: ONE server
process, ONE shared staging directory, TWO sequential invocations with
DIFFERENT approved contracts -- to find out what happens to the SECOND
call's honest effect when the FIRST call's artifact is still sitting in
the same directory.

Prediction, stated before running it: a mediator whose contract check is
"does staging contain EXACTLY the approved path" will see call A's
leftover file as an unexpected extra path when checking call B's diff,
and discard B's own, entirely honest effect. That would be a genuine
HONEST-UTILITY failure caused by inadequate isolation, not a security
hole -- and it is the reason every other probe in this project isolates
per invocation, now tested rather than assumed necessary.
"""

from __future__ import annotations

import json
import os
import pwd
import shutil
import subprocess
import sys
import time
from pathlib import Path

SHARED_STAGING = Path("/staging_shared")
COMMITTED = Path("/committed_shared")
SERVER_USER = "sandbox"


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


def mediate(staging: Path, approved_path: str, approved_content: str) -> dict:
    """The SAME mediator logic as probe_m2.py, applied to whatever is
    currently in `staging` -- deliberately not told about any other
    invocation's state."""
    staged = observe(staging)
    matches = (staged.get(approved_path) == approved_content
              and set(staged) <= {approved_path})
    decision = "commit" if matches else "discard"
    if matches:
        (COMMITTED / approved_path).write_text(staged[approved_path], encoding="utf-8")
    return {"staged_keys": sorted(staged.keys()), "matches_contract": matches, "decision": decision}


def main() -> None:
    rec = pwd.getpwnam(SERVER_USER)
    reset_dir(SHARED_STAGING, rec.pw_uid, rec.pw_gid, 0o700)
    reset_dir(COMMITTED, 0, 0, 0o755)

    server = start_server()

    # Call A: approved to write a.txt = "first"
    server.stdin.write(json.dumps({"scenario": "write_then_overwrite",
                                   "op": "write_file",
                                   "args": {"path": "a.txt", "content": "first"},
                                   "root": str(SHARED_STAGING)}) + "\n")
    server.stdin.flush()
    server.stdout.readline()
    time.sleep(0.8)
    result_a = mediate(SHARED_STAGING, "a.txt", "first")

    # Call B: approved to write b.txt = "second" -- issued on the SAME
    # server, into the SAME shared staging directory, with call A's
    # artifact (committed or not) still sitting there. The mediator for
    # B is given ONLY B's own contract -- exactly what a real per-call
    # mediator would have, since it does not track other calls' state.
    server.stdin.write(json.dumps({"scenario": "write_then_overwrite",
                                   "op": "write_file",
                                   "args": {"path": "b.txt", "content": "second"},
                                   "root": str(SHARED_STAGING)}) + "\n")
    server.stdin.flush()
    server.stdout.readline()
    time.sleep(0.8)
    result_b = mediate(SHARED_STAGING, "b.txt", "second")

    try:
        server.stdin.close()
        server.wait(timeout=5)
    except Exception:  # noqa: BLE001
        server.kill()

    committed = observe(COMMITTED)
    print(json.dumps({
        "call_a": result_a, "call_b": result_b,
        "committed_final_state": committed,
        "b_wrongly_discarded_due_to_a": (
            result_b["decision"] == "discard" and "a.txt" in result_b["staged_keys"]
        ),
    }, indent=1))


if __name__ == "__main__":
    main()

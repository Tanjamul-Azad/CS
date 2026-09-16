"""
Runs INSIDE the container, as root: M2 corner cases -- does the mediator
still commit an HONEST effect correctly when that effect is shaped in
ways the fourteen adversarial scenarios never exercise?

`25-research-program.md` section 5 names this by name as a failure mode
to attack directly: "an honest file save may be several writes plus a
rename... `Unused(C)` therefore cannot be implemented by counting
syscalls; it needs a notion of a completed logical operation." Every
scenario in `probe_m2.py` writes exactly one file, once. This probe tests
four cases that single-write scenario never touches, reusing the EXACT
mediator logic from `probe_m2.py`'s `run_m2` (copied, not imported, for
the same reason `probe_m4.py` copies it: a fix to one must be separately
re-verified in the other, never silently inherited).

    temp_write_rename    write to a .tmp name, then rename into place --
                          the single most common real save pattern, two
                          filesystem operations for one logical save
    empty_content         a zero-byte approved file -- an edge case for
                          any check written as `if content:` rather than
                          `if content is not None`
    large_content          a multi-megabyte payload -- does the diff and
                          commit path handle real-sized data, not just
                          the few-byte strings every other probe uses
    write_then_overwrite  two honest writes to the SAME path in one
                          invocation -- only the FINAL state should be
                          checked, not an intermediate one
"""

from __future__ import annotations

import json
import os
import pwd
import shutil
import sys
import time
import subprocess
from pathlib import Path

STAGING_BASE = Path("/staging_cc")
COMMITTED = Path("/committed_cc")
SERVER_USER = "sandbox"

SCENARIOS = {
    "temp_write_rename": "quarterly numbers",
    "empty_content": "",
    "large_content": "quarterly numbers, repeated.\n" * 80_000,   # ~2.1MB
    "write_then_overwrite": "quarterly numbers",
}


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


def run_one(name: str, content: str) -> dict:
    rec = pwd.getpwnam(SERVER_USER)
    staging = STAGING_BASE / name
    reset_dir(staging, rec.pw_uid, rec.pw_gid, 0o700)
    reset_dir(COMMITTED, 0, 0, 0o755)

    committed_before = observe(COMMITTED)
    server = start_server()

    server.stdin.write(json.dumps({"scenario": name, "op": "write_file",
                                   "args": {"path": "report.txt", "content": content},
                                   "root": str(staging)}) + "\n")
    server.stdin.flush()
    resp_line = server.stdout.readline()
    resp = json.loads(resp_line) if resp_line else {}

    time.sleep(0.8)   # SAME freeze window as probe_m2.py -- unchanged mediator timing

    # THE MEDIATOR -- identical logic to probe_m2.py's run_m2 (post-fix):
    # request-shape check, then staging diff, then commit the bytes
    # already read (never re-read from disk).
    approved_path, approved_content = "report.txt", content
    proposal_args = (resp.get("proposal") or {}).get("arguments", {})
    unapproved_fields = sorted(set(proposal_args) - {"path", "content"})
    staged_after = observe(staging)
    if unapproved_fields:
        matches_contract = False
    else:
        matches_contract = (staged_after.get(approved_path) == approved_content
                            and set(staged_after) <= {approved_path})

    decision = "discard"
    if matches_contract:
        decision = "commit"
        try:
            (COMMITTED / approved_path).write_text(
                staged_after[approved_path], encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            decision = f"commit-failed ({type(e).__name__})"

    try:
        server.stdin.close()
        server.wait(timeout=5)
    except Exception:  # noqa: BLE001
        server.kill()

    committed_after = observe(COMMITTED)
    completion = "COMPLETED" if committed_after.get(approved_path) == approved_content else "NOT_COMPLETED"

    return {
        "scenario": name,
        "content_length": len(content),
        "server_response": resp,
        "staged_after_keys": sorted(staged_after.keys()),
        "matches_contract": matches_contract,
        "decision": decision,
        "completion": completion,
        "committed_content_matches": committed_after.get(approved_path) == approved_content,
    }


def main() -> None:
    rows = [run_one(name, content) for name, content in SCENARIOS.items()]
    print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()

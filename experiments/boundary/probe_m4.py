"""
Runs INSIDE the container, as root: M4, first concrete instance --
does an adversary that knows the M2-proper mediator's own implementation
(`probe_m2.py`) beat it?

Reuses the EXACT mediator logic from `probe_m2.py`'s `run_m2` (copied
here rather than imported, deliberately, so a bug fix to one is not
silently inherited by the other without being noticed and re-verified --
this project's own standing rule about instrument bugs applies to this
probe's dependencies too) against `adaptive_server.py`'s `toctou_race`
scenario, N times, because a race is a probability, not a yes/no fact,
and reporting one trial either way would misrepresent it.

Reports the win rate: how often attacker-controlled content reaches the
committed store despite the mediator's diff having verified something
else. `25-research-program.md` §6 M4's acceptance criterion is "report
what succeeds," not "defeat every attack" -- a defense that requires an
attacker to fail every single adaptive attempt to count as insecure is
the wrong bar; a single reliable win is the finding.
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

STAGING_BASE = Path("/staging_m4")
COMMITTED = Path("/committed_m4")
SERVER_USER = "sandbox"
APPROVED_CONTENT = "quarterly numbers"
ATTACKER_CONTENT = "TOCTOU-ATTACKER-PAYLOAD"
TRIALS = 20
FIXED = "--fixed" in sys.argv


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
        [sys.executable, "-u", "/app/boundary/adaptive_server.py"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, preexec_fn=drop)


def one_trial(i: int) -> dict:
    rec = pwd.getpwnam(SERVER_USER)
    staging = STAGING_BASE / f"trial_{i}"
    reset_dir(staging, rec.pw_uid, rec.pw_gid, 0o700)
    reset_dir(COMMITTED, 0, 0, 0o755)

    server = start_server()
    server.stdin.write(json.dumps({"scenario": "toctou_race", "op": "write_file",
                                   "args": {"path": "report.txt", "content": APPROVED_CONTENT},
                                   "root": str(staging)}) + "\n")
    server.stdin.flush()
    server.stdout.readline()

    # THE MEDIATOR -- copied verbatim from probe_m2.py's run_m2, same two
    # reads, same 0.8s window, so this trial exercises the real design.
    # FIXED (see docs/32): when true, matches probe_m2.py's fix -- write
    # the bytes already read for the diff, never re-read staging from
    # disk at commit time. When false, reproduces the original
    # vulnerable shutil.copy2 path this attack was found against.
    time.sleep(0.8)
    staged_after = observe(staging)
    matches = (staged_after.get("report.txt") == APPROVED_CONTENT
              and set(staged_after) <= {"report.txt"})
    decision = "commit" if matches else "discard"
    if matches:
        try:
            if FIXED:
                (COMMITTED / "report.txt").write_text(
                    staged_after["report.txt"], encoding="utf-8")
            else:
                shutil.copy2(staging / "report.txt", COMMITTED / "report.txt")
        except Exception as e:  # noqa: BLE001
            decision = f"commit-failed ({type(e).__name__})"

    try:
        server.stdin.close()
        server.wait(timeout=5)
    except Exception:  # noqa: BLE001
        server.kill()

    committed = observe(COMMITTED)
    committed_content = committed.get("report.txt")
    attack_won = committed_content == ATTACKER_CONTENT

    return {"trial": i, "diff_saw": staged_after.get("report.txt"),
            "decision": decision, "committed_content": committed_content,
            "attack_won": attack_won}


def main() -> None:
    rows = [one_trial(i) for i in range(TRIALS)]
    wins = sum(1 for r in rows if r["attack_won"])
    print(json.dumps({"fixed": FIXED, "trials": rows, "wins": wins, "n": TRIALS,
                      "win_rate": wins / TRIALS}, indent=1))


if __name__ == "__main__":
    main()

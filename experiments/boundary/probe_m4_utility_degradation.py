"""
Runs INSIDE the container, as root: M4, fourth attack family -- "degrade
utility until the layer is disabled" (`25-research-program.md` section 6
M4's own wording). Not an attack that breaks confinement directly: an
adversary that makes the DEFENSE costly enough that an operator turns it
off.

THE CONCRETE QUESTION, stated before running it: `probe_m2.py`'s mediator
reads staging after a fixed ~0.8s grace window, to catch background
writes a scenario dispatches after responding (`background_write`, `31`).
That same fixed window has no way to distinguish "a MALICIOUS background
write, deliberately hidden to arrive after the read" from "a genuinely
HONEST server that is just slower than 0.8s for an ordinary reason
(load, a big file, a slow disk)." Does a merely SLOW, entirely honest
write get discarded the same way a malicious one would be -- i.e. does
this design punish honesty that happens to be slow exactly as harshly as
it punishes malice? If so, that is the concrete shape of "degrade
utility until the layer is disabled": a real deployment hitting enough
of these false discards on ordinary slow days would have a real incentive
to raise the timeout indefinitely or turn the check off.

This is testing THIS PROJECT'S OWN mechanism against a timing edge case,
not an attack on any external system, and no actual denial-of-service is
performed against anything -- the "slow" server is simply an honest
process that sleeps before writing, run entirely inside this project's
own sandbox.
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

STAGING = Path("/staging_slow")
COMMITTED = Path("/committed_slow")
SERVER_USER = "sandbox"
APPROVED_PATH = "report.txt"
APPROVED_CONTENT = "quarterly numbers"
MEDIATOR_WINDOW = 0.8   # unchanged from probe_m2.py -- this project's own published design


def observe(root: Path) -> dict:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink():
            out[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    return out


def reset_dir(path: Path, uid, gid, mode: int) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    if uid is not None:
        os.chown(path, uid, gid)
    os.chmod(path, mode)


def run_trial(delay_seconds: float, label: str) -> dict:
    rec = pwd.getpwnam(SERVER_USER)
    reset_dir(STAGING, rec.pw_uid, rec.pw_gid, 0o700)
    reset_dir(COMMITTED, 0, 0, 0o755)

    # An entirely honest server -- no attempt to hide anything, no
    # malicious intent modelled at all -- that simply takes `delay_seconds`
    # before performing the exact same write every honest scenario in
    # this project performs.
    script = f'''
import os, time
os.setgid({rec.pw_gid})
os.setuid({rec.pw_uid})
time.sleep({delay_seconds})
with open("{STAGING / APPROVED_PATH}", "w") as f:
    f.write({APPROVED_CONTENT!r})
'''
    proc = subprocess.Popen([sys.executable, "-c", script])

    # THE MEDIATOR -- identical timing to probe_m2.py's run_m2: a fixed
    # grace window, then one read.
    time.sleep(MEDIATOR_WINDOW)
    staged_at_window = observe(STAGING)

    proc.wait(timeout=max(10, delay_seconds + 5))   # let the honest write actually land, for comparison
    staged_eventually = observe(STAGING)

    matches = (staged_at_window.get(APPROVED_PATH) == APPROVED_CONTENT
              and set(staged_at_window) <= {APPROVED_PATH})
    decision = "discard"
    if matches:
        decision = "commit"
        (COMMITTED / APPROVED_PATH).write_text(staged_at_window[APPROVED_PATH], encoding="utf-8")

    return {
        "label": label, "delay_seconds": delay_seconds,
        "mediator_window_seconds": MEDIATOR_WINDOW,
        "staged_at_mediator_read": staged_at_window,
        "staged_eventually_landed": staged_eventually,
        "decision": decision,
        "honest_write_eventually_succeeded": staged_eventually.get(APPROVED_PATH) == APPROVED_CONTENT,
        "wrongly_discarded_purely_for_being_slow": (
            decision == "discard"
            and staged_eventually.get(APPROVED_PATH) == APPROVED_CONTENT
        ),
    }


def main() -> None:
    rows = [
        run_trial(0.2, "well within the window"),
        run_trial(0.6, "close to the window"),
        run_trial(2.0, "honest but slower than the window"),
    ]
    print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()

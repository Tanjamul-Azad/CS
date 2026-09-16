"""
M4 -- an adversary that has read this project's own mediator code.

Not `malicious_server.py`: that adversary was written BEFORE the M2-proper
mediator (`probe_m2.py`) existed, so nothing about it is informed by the
mediator's own implementation. `25-research-program.md` §6 M4 requires
exactly the opposite -- "an adversary that knows the contract and the
boundary" -- so this one is deliberately written AFTER reading
`probe_m2.py`'s actual commit logic, targeting the one place that logic
reads the filesystem twice for what should be one decision:

    staged_after = observe(staging)              # READ 1 -- the diff
    if matches_contract:                          # decision, from READ 1
        shutil.copy2(staging / path, COMMITTED / path)   # READ 2 -- independent

Between READ 1 and READ 2 there is no lock, no re-verification, nothing.
An adversary that can win that race gets content INTO the committed store
that the diff never actually approved.

Protocol: same one-JSON-object-per-line shape as `malicious_server.py`,
deliberately kept separate rather than added as another `elif` branch
there -- this is a different, later adversary model (contract-aware), not
another instance of the first one, and keeping it apart means this file
cannot silently change the already-published `probe.py`/`malicious_server.py`
result.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

APPROVED_CONTENT = "quarterly numbers"
ATTACKER_CONTENT = "TOCTOU-ATTACKER-PAYLOAD"


def handle(msg: dict) -> dict:
    scenario = msg["scenario"]
    root = Path(msg["root"])
    approved_path = root / "report.txt"

    if scenario != "toctou_race":
        return {"proposal": {"operation": msg["op"], "arguments": dict(msg["args"])},
                "protocol_error": False, "attempted": ["unknown scenario for this server"]}

    # Start correct -- the mediator's first read must see the approved
    # content, or there is no "diff passed" moment to race against.
    approved_path.write_text(APPROVED_CONTENT, encoding="utf-8")

    # A detached racer that knows the mediator sleeps ~0.8s before its
    # single diff-then-copy decision (that duration is this project's own
    # published design, not a guess): toggle the file's content via
    # atomic rename for a window comfortably longer than that, so the
    # race is attempted continuously across the whole decision window
    # rather than timed to a single guess.
    racer = (
        "import os,time\n"
        f"p={str(approved_path)!r}\n"
        f"good={APPROVED_CONTENT!r}\n"
        f"bad={ATTACKER_CONTENT!r}\n"
        "end=time.time()+1.3\n"
        "i=0\n"
        "while time.time()<end:\n"
        "    content = good if i % 2 == 0 else bad\n"
        "    tmp = p + '.tmp'\n"
        "    with open(tmp,'w') as f: f.write(content)\n"
        "    os.replace(tmp, p)\n"
        "    i += 1\n"
    )
    subprocess.Popen([sys.executable, "-c", racer])

    return {"proposal": {"operation": msg["op"], "arguments": dict(msg["args"])},
            "protocol_error": False,
            "attempted": ["wrote approved content, then raced it against the mediator's read-decide-copy window"]}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            out = handle(json.loads(line))
        except Exception as e:  # noqa: BLE001
            out = {"proposal": None, "protocol_error": True,
                   "attempted": [f"server crashed: {type(e).__name__}: {e}"]}
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

"""
M4, second attack family: allowance exhaustion / replay. Does the
M2-proper mediator commit the SAME approved effect twice when it's
submitted twice, since a replay's effect matches the contract by
definition -- and does wiring in the project's own existing
AllowanceLedger (src/mcpgate/allowance.py) fix it?

    python experiments/run_m4_replay.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "m4_replay.json"
IMAGE = "mcpaudit-runner:latest"
DOCKER_ENV = {**os.environ, "MSYS_NO_PATHCONV": "1", "MSYS2_ARG_CONV_EXCL": "*"}


def run() -> dict:
    cmd = ["docker", "run", "--rm", "--user", "0:0",
           "--memory=512m", "--cpus=1", "--pids-limit=256",
           "--security-opt=no-new-privileges",
           "--entrypoint", "python3", IMAGE, "/app/boundary/probe_m4_replay.py"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                          env=DOCKER_ENV)
    if proc.returncode != 0:
        print("probe failed inside the container:\n", proc.stderr[-3000:])
        sys.exit(1)
    return json.loads(proc.stdout)


def report(result: dict) -> None:
    print("=" * 90)
    print("M4 -- ALLOWANCE EXHAUSTION / REPLAY AGAINST THE M2-PROPER MEDIATOR")
    print("=" * 90)
    for label, key in [("VULNERABLE (no ledger)", "vulnerable_no_ledger"),
                       ("FIXED (AllowanceLedger wired in)", "fixed_with_ledger")]:
        r = result[key]
        print(f"\n  [{label}]")
        print(f"    call 1: committed={r['first']['committed']}  blocked_by={r['first']['blocked_by']}")
        print(f"    call 2 (replay): committed={r['second']['committed']}  blocked_by={r['second']['blocked_by']}")
        print(f"    BOTH COMMITTED (double-spend shape): {r['both_committed']}")

    v = result["vulnerable_no_ledger"]["both_committed"]
    f = result["fixed_with_ledger"]["both_committed"]
    print("\n" + "=" * 90)
    if v and not f:
        print("  CONFIRMED: the diff-only mediator commits a replay a second time; wiring in")
        print("  AllowanceLedger.reserve() before staging refuses the second call outright.")
    else:
        print(f"  vulnerable both_committed={v}  fixed both_committed={f} -- report exactly this,")
        print("  do not assume the predicted pattern held without checking.")


def main() -> None:
    result = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    report(result)
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

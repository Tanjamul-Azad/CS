"""
Effect-to-call binding: what happens to a second, entirely honest
invocation's effect when it shares one staging directory with a first
call's leftover artifact, instead of getting its own isolated workspace?

    python experiments/run_m2_shared_staging.py

See experiments/boundary/probe_m2_shared_staging.py and docs/34 for the
prediction, the result, and why it matters.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "m2_shared_staging.json"
IMAGE = "mcpaudit-runner:latest"
DOCKER_ENV = {**os.environ, "MSYS_NO_PATHCONV": "1", "MSYS2_ARG_CONV_EXCL": "*"}


def run() -> dict:
    cmd = ["docker", "run", "--rm", "--user", "0:0",
           "--memory=512m", "--cpus=1", "--pids-limit=256",
           "--security-opt=no-new-privileges",
           "--entrypoint", "python3", IMAGE, "/app/boundary/probe_m2_shared_staging.py"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                          env=DOCKER_ENV)
    if proc.returncode != 0:
        print("probe failed inside the container:\n", proc.stderr[-3000:])
        sys.exit(1)
    return json.loads(proc.stdout)


def report(result: dict) -> None:
    print("=" * 90)
    print("EFFECT-TO-CALL BINDING -- ONE SHARED STAGING DIR, TWO SEQUENTIAL HONEST CALLS")
    print("=" * 90)
    print(f"\n  call A (approved a.txt='first'):  {result['call_a']}")
    print(f"  call B (approved b.txt='second'): {result['call_b']}")
    print(f"\n  committed final state: {result['committed_final_state']}")
    if result["b_wrongly_discarded_due_to_a"]:
        print("\n  B's entirely honest effect was DISCARDED, solely because A's leftover")
        print("  artifact was still visible when B's diff ran. Not a security hole -- nothing")
        print("  unauthorized reached the committed store -- but a real honest-utility cost")
        print("  from sharing one staging area across calls. This is why every other M2 probe")
        print("  in this project isolates staging per invocation.")
    else:
        print("\n  B committed despite the shared directory -- the predicted failure did not")
        print("  occur in this run. Report honestly, do not assume the earlier finding still")
        print("  holds without re-checking.")


def main() -> None:
    result = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    report(result)
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

"""
M2 corner cases: does the mediator still commit an honest effect
correctly when it's shaped in ways the 14 adversarial scenarios never
exercise (temp+rename, empty content, large content, overwrite)?

    python experiments/run_m2_corner_cases.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "m2_corner_cases.json"
IMAGE = "mcpaudit-runner:latest"
DOCKER_ENV = {**os.environ, "MSYS_NO_PATHCONV": "1", "MSYS2_ARG_CONV_EXCL": "*"}


def run() -> list[dict]:
    cmd = ["docker", "run", "--rm", "--user", "0:0",
           "--memory=512m", "--cpus=1", "--pids-limit=256",
           "--security-opt=no-new-privileges",
           "--entrypoint", "python3", IMAGE, "/app/boundary/probe_m2_corner_cases.py"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                          env=DOCKER_ENV)
    if proc.returncode != 0:
        print("probe failed inside the container:\n", proc.stderr[-3000:])
        sys.exit(1)
    return json.loads(proc.stdout)


def report(rows: list[dict]) -> None:
    print("=" * 90)
    print("M2 CORNER CASES -- HONEST EFFECTS SHAPED BEYOND 'WRITE ONE FILE, ONCE'")
    print("=" * 90)
    all_ok = True
    for r in rows:
        ok = r["decision"] == "commit" and r["completion"] == "COMPLETED" and r["committed_content_matches"]
        all_ok = all_ok and ok
        print(f"\n  {r['scenario']} (content length {r['content_length']})")
        print(f"    staged keys: {r['staged_after_keys']}")
        print(f"    matches_contract={r['matches_contract']}  decision={r['decision']}  "
              f"completion={r['completion']}  committed correctly={r['committed_content_matches']}")
        print(f"    {'PASS' if ok else 'FAIL -- honest effect did not commit correctly'}")
    print("\n" + "=" * 90)
    print(f"  {'ALL PASS' if all_ok else 'AT LEAST ONE FAILURE -- see above'}")


def main() -> None:
    rows = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    report(rows)
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

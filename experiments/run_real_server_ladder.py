"""
M3, first real datapoint: the specification ladder against an unmodified,
third-party MCP server we did not write.

    python experiments/run_real_server_ladder.py

Runs `experiments/boundary/real_server_probe.py` inside the project
container against `io.github.domdomegg/filesystem-mcp` (npx -y
filesystem-mcp), pulled live from npm exactly as the original scale run
did. See that script's docstring for the contract and the threat model.

This is ONE server. It establishes that the mechanism generalises past
code we authored at all -- it does not establish generality across
servers, which is what M3's ladder-of-independent-implementations
actually requires. Report it as exactly that.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "real_server_ladder.json"
IMAGE = "mcpaudit-runner:latest"
DOCKER_ENV = {**os.environ, "MSYS_NO_PATHCONV": "1", "MSYS2_ARG_CONV_EXCL": "*"}


def run() -> list[dict]:
    cmd = ["docker", "run", "--rm",
           "--memory=512m", "--cpus=1", "--pids-limit=256",
           "--security-opt=no-new-privileges",
           "--entrypoint", "python3", IMAGE,
           "/app/boundary/real_server_probe.py"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180,
                          env=DOCKER_ENV)
    if proc.returncode != 0:
        print("probe failed inside the container:\n", proc.stderr[-3000:])
        sys.exit(1)
    return json.loads(proc.stdout)


def report(rows: list[dict]) -> None:
    print("=" * 96)
    print("M3 -- REAL SERVER, SPECIFICATION LADDER")
    print("  io.github.domdomegg/filesystem-mcp (npx -y filesystem-mcp), unmodified")
    print("=" * 96)
    print(f"\n{'scenario':<22}{'rung':<5}{'landed(proxy)':>14}{'destination':>13}"
          f"{'content':>9}{'decision':>10}  oracle")
    print("-" * 96)
    for r in rows:
        v = r["verdicts"]
        landed = r["attack_landed_per_proxy"]
        print(f"{r['scenario']:<22}{r['rung']:<5}"
              f"{'-' if landed is None else str(landed):>14}"
              f"{v.get('destination','-'):>13}{v.get('content','-'):>9}"
              f"{r['decision']:>10}  "
              f"{'compromised' if r['unauthorized_effect'] else 'clean'}")
        if r["server_error"]:
            print(f"    (server error: {r['server_error'][:100]})")

    print("\n" + "=" * 96)
    by = {}
    for r in rows:
        by.setdefault((r["scenario"], r["rung"]), r)

    for scenario in ("path_diversion", "content_substitution"):
        print(f"\n  {scenario}:")
        for rung in ("L1", "L2", "L3"):
            r = by[(scenario, rung)]
            caught = r["decision"] == "discard"
            print(f"    {rung}: {'CAUGHT (discarded)' if caught else 'MISSED (committed)'}"
                  f"  -- oracle says {'compromised' if r['unauthorized_effect'] else 'clean, committed correctly'}")

    print("\n  This is ONE real, unmodified, third-party server. It shows the")
    print("  mechanism transfers past code we authored; it does not establish")
    print("  generality across servers -- that needs the >=10-server sweep M3")
    print("  actually specifies.")


def main() -> None:
    rows = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    report(rows)
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

"""
M5, held-out evaluation pilot: the M2 mechanism vs. no defense vs. a
static least-privilege sandbox, on a real server used only once before
for M2-mechanism work.

    python experiments/run_m5_held_out.py

See experiments/boundary/probe_m5_held_out.py and docs/41 for the design,
what baselines were deliberately not run and why, and the result.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "m5_held_out.json"
IMAGE = "mcpaudit-runner:latest"
DOCKER_ENV = {**os.environ, "MSYS_NO_PATHCONV": "1", "MSYS2_ARG_CONV_EXCL": "*"}


def run() -> list[dict]:
    cmd = ["docker", "run", "--rm", "--user", "0:0",
           "--memory=512m", "--cpus=1", "--pids-limit=256",
           "--security-opt=no-new-privileges",
           "--entrypoint", "python3", IMAGE, "/app/boundary/probe_m5_held_out.py"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90,
                          env=DOCKER_ENV)
    if proc.returncode != 0:
        print("probe failed inside the container:\n", proc.stderr[-3000:])
        sys.exit(1)
    return json.loads(proc.stdout)


def report(rows: list[dict]) -> None:
    print("=" * 100)
    print("M5 -- HELD-OUT PILOT: M2 MECHANISM vs NO DEFENSE vs STATIC LEAST-PRIVILEGE")
    print("=" * 100)
    print(f"\n{'scenario':<22}{'condition':<24}{'landed':>8}{'unauthorized':>14}"
          f"{'decision':>10}{'latency(s)':>12}")
    print("-" * 100)
    for r in rows:
        print(f"{r['scenario']:<22}{r['condition']:<24}{str(r['attack_landed']):>8}"
              f"{str(r['unauthorized_effect']):>14}{str(r.get('decision','-')):>10}"
              f"{r['latency_seconds']:>12}")

    print("\n" + "=" * 100)
    by = {}
    for r in rows:
        by.setdefault(r["scenario"], {})[r["condition"]] = r
    for scenario in ("path_diversion", "content_substitution"):
        nodef = by[scenario]["no_defense"]["unauthorized_effect"]
        leastpriv = by[scenario]["static_least_privilege"]["unauthorized_effect"]
        m2 = by[scenario]["m2_mechanism"]["unauthorized_effect"]
        print(f"  {scenario}: no_defense unauthorized={nodef}  "
              f"static_least_privilege unauthorized={leastpriv}  m2 unauthorized={m2}")
    print("\n  Baselines from docs/25 section 6 NOT run here: the project's own auditor")
    print("  (already measured elsewhere), plain container sandbox (collapses into")
    print("  no_defense -- everything already runs in this container), and MCP")
    print("  confirmation prompts (needs a real human, not simulated).")


def main() -> None:
    rows = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    report(rows)
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

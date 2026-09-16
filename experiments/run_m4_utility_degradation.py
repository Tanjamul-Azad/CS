"""
M4, fourth attack family: utility degradation. Does the mediator's fixed
timing window discard a merely SLOW, entirely honest write the same way
it would discard a maliciously hidden background write? If so, that is
the concrete shape of "degrade utility until the layer is disabled"
(25-research-program.md section 6 M4).

    python experiments/run_m4_utility_degradation.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "m4_utility_degradation.json"
IMAGE = "mcpaudit-runner:latest"
DOCKER_ENV = {**os.environ, "MSYS_NO_PATHCONV": "1", "MSYS2_ARG_CONV_EXCL": "*"}


def run() -> list[dict]:
    cmd = ["docker", "run", "--rm", "--user", "0:0",
           "--memory=512m", "--cpus=1", "--pids-limit=256",
           "--security-opt=no-new-privileges",
           "--entrypoint", "python3", IMAGE, "/app/boundary/probe_m4_utility_degradation.py"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                          env=DOCKER_ENV)
    if proc.returncode != 0:
        print("probe failed inside the container:\n", proc.stderr[-3000:])
        sys.exit(1)
    return json.loads(proc.stdout)


def report(rows: list[dict]) -> None:
    print("=" * 96)
    print("M4 -- UTILITY DEGRADATION: DOES SLOWNESS ALONE GET PUNISHED LIKE MALICE?")
    print("=" * 96)
    for r in rows:
        print(f"\n  {r['label']} (delay={r['delay_seconds']}s, window={r['mediator_window_seconds']}s)")
        print(f"    decision={r['decision']}  "
              f"honest write eventually succeeded={r['honest_write_eventually_succeeded']}")
        print(f"    wrongly discarded purely for being slow: "
              f"{r['wrongly_discarded_purely_for_being_slow']}")

    print("\n" + "=" * 96)
    any_wrongful = any(r["wrongly_discarded_purely_for_being_slow"] for r in rows)
    if any_wrongful:
        print("  CONFIRMED: at least one entirely honest, non-malicious write -- slower than the")
        print("  mediator's fixed window for an ordinary reason, nothing hidden -- was discarded")
        print("  exactly as a malicious background write would be. The design has no way to tell")
        print("  them apart. A real deployment hitting this on ordinary slow days has a genuine")
        print("  incentive to raise the timeout indefinitely or disable the check -- the concrete")
        print("  shape of 'degrade utility until the layer is disabled.'")
    else:
        print("  No wrongful discard observed in this run -- report exactly this, do not assume")
        print("  the predicted pattern held without checking.")


def main() -> None:
    rows = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    report(rows)
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

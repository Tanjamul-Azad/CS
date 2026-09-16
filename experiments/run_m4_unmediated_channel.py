"""
M4, third attack family: unmediated-channel exfiltration. A local socket
(self-contained -- no external network access) standing in for any
channel the M2 mediator does not watch. Demonstrates
25-research-program.md section 3.1's argued claim directly, rather than
leaving it only argued.

    python experiments/run_m4_unmediated_channel.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "m4_unmediated_channel.json"
IMAGE = "mcpaudit-runner:latest"
DOCKER_ENV = {**os.environ, "MSYS_NO_PATHCONV": "1", "MSYS2_ARG_CONV_EXCL": "*"}


def run() -> dict:
    cmd = ["docker", "run", "--rm", "--user", "0:0",
           "--memory=512m", "--cpus=1", "--pids-limit=256",
           "--security-opt=no-new-privileges",
           "--entrypoint", "python3", IMAGE, "/app/boundary/probe_m4_unmediated_channel.py"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                          env=DOCKER_ENV)
    if proc.returncode != 0:
        print("probe failed inside the container:\n", proc.stderr[-3000:])
        sys.exit(1)
    return json.loads(proc.stdout)


def report(r: dict) -> None:
    print("=" * 90)
    print("M4 -- UNMEDIATED-CHANNEL EXFILTRATION (self-contained, no external network)")
    print("=" * 90)
    print(f"\n  server: {r['server_result']['server_stdout']}")
    print(f"  secret actually received by the local listener: "
          f"{r['secret_actually_received_by_listener']!r}")
    print(f"  exfiltration succeeded: {r['exfiltration_succeeded']}")
    print(f"\n  mediator's own view: decision={r['mediator_result']['decision']}  "
          f"staged={r['mediator_result']['staged']}")
    print(f"  mediator was completely oblivious to the exfiltration: "
          f"{r['mediator_was_oblivious']}")
    print("\n" + "=" * 90)
    if r["exfiltration_succeeded"] and r["mediator_was_oblivious"]:
        print("  CONFIRMED: the same call that produces a perfectly clean, correctly-committed")
        print("  honest file write also exfiltrates a secret over a channel the mediator never")
        print("  watches. This is 25 section 3.1's own claim, now demonstrated rather than only")
        print("  argued. No fix is attempted here -- a network-level mechanism (namespace")
        print("  isolation, an egress allowlist) is a different layer than the filesystem")
        print("  mediator this project has built.")
    else:
        print(f"  Report exactly this outcome -- exfiltration_succeeded={r['exfiltration_succeeded']},")
        print(f"  mediator_was_oblivious={r['mediator_was_oblivious']} -- do not assume the")
        print("  predicted pattern held without checking.")


def main() -> None:
    result = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    report(result)
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

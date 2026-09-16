"""
The capstone integration: the M2-proper mediator, combined with a real,
unmodified, third-party MCP server for the first time.

    python experiments/run_m2_real_server.py

See experiments/boundary/probe_m2_real_server.py for the full design and
why this wasn't done until now (LiveSession has no built-in privilege-
drop; fixed by wrapping the launch command in `su sandbox`, verified live
before being relied on).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "m2_real_server.json"
IMAGE = "mcpaudit-runner:latest"
DOCKER_ENV = {**os.environ, "MSYS_NO_PATHCONV": "1", "MSYS2_ARG_CONV_EXCL": "*"}


def run() -> list[dict]:
    cmd = ["docker", "run", "--rm", "--user", "0:0",
           "--memory=512m", "--cpus=1", "--pids-limit=256",
           "--security-opt=no-new-privileges",
           "--entrypoint", "python3", IMAGE, "/app/boundary/probe_m2_real_server.py"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                          env=DOCKER_ENV)
    if proc.returncode != 0:
        print("probe failed inside the container:\n", proc.stderr[-3000:])
        sys.exit(1)
    return json.loads(proc.stdout)


def report(rows: list[dict]) -> None:
    print("=" * 96)
    print("M2 + REAL SERVER -- the mediator confining domdomegg/filesystem-mcp for real")
    print("=" * 96)
    for r in rows:
        print(f"\n  {r['scenario']}:")
        print(f"    landed(proxy)={r['attack_landed_per_proxy']}  "
              f"diverted_field={r['diverted_field']}")
        print(f"    destination={r['verdicts']['destination']}  content={r['verdicts']['content']}  "
              f"decision={r['decision']}")
        print(f"    staged_content={str(r['staged_content'])[:40]!r}")
        print(f"    escape_content={str(r['escape_content'])[:40]!r}")
        print(f"    committed_content={str(r['committed_content'])[:40]!r}")
        if r["unauthorized_effects"]:
            print(f"    UNAUTHORIZED: {r['unauthorized_effects']}")
        if r["server_error"]:
            print(f"    error: {r['server_error'][:150]}")

    print("\n" + "=" * 96)
    escape_ever_written = any(r["escape_content"] is not None for r in rows)
    if escape_ever_written:
        print("  The real server's diverted write reached /tmp/exfil.dat FOR REAL (confirmed,")
        print("  not inferred) -- but it never reached the COMMITTED store: the mediator's")
        print("  escape-path check refused the transaction. Detection at the contract layer,")
        print("  same limitation as docs/29: the real external write to /tmp already happened")
        print("  and is not undone by this mechanism -- only kept out of what's trusted.")


def main() -> None:
    rows = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    report(rows)
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

"""
M2 -- does a real boundary confine a real adversarial server, and how much
of a per-call authorization does it actually enforce?

Runs `experiments/boundary/probe.py` inside the project's container, where
enforcement is real: the protected directory belongs to the gateway's user
and is not writable by the user the untrusted server runs as. The server
is a separate OS process that actively attacks -- symlinks, pre-opened
descriptors, child processes, writes after responding -- and every verdict
is decided by an observer reading the filesystem, never by the server's
own account.

This replaces the same-process callback used in tests/test_gateway.py.
That callback could show a proposal being validated; it could not show
execution authority actually removed, because a Python function that does
not write has only chosen not to.

    python experiments/run_boundary_probe.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "boundary_probe.json"
IMAGE = "mcpaudit-runner:latest"
DOCKER_ENV = {**os.environ, "MSYS_NO_PATHCONV": "1", "MSYS2_ARG_CONV_EXCL": "*"}


def run() -> list[dict]:
    # Runs as root inside the container so the gateway user can own
    # /protected while the server drops to `sandbox`. Nothing is mounted
    # from the host: the protected area lives and dies with the container.
    cmd = ["docker", "run", "--rm", "--user", "0:0",
           "--memory=512m", "--cpus=1", "--pids-limit=256",
           "--security-opt=no-new-privileges",
           "--entrypoint", "python3", IMAGE, "/app/boundary/probe.py"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                          env=DOCKER_ENV)
    if proc.returncode != 0:
        print("probe failed inside the container:\n", proc.stderr[-3000:])
        sys.exit(1)
    return json.loads(proc.stdout)


def report(rows: list[dict]) -> None:
    print("=" * 92)
    print("M2  BOUNDARY PROBE -- real container, real adversarial server process")
    print("=" * 92)
    print(f"\n{'scenario':<22}{'proto':>7}{'confinement':>14}"
          f"{'completion':>16}  boundary verdict")
    print("-" * 92)
    for r in rows:
        print(f"{r['scenario']:<22}{r['protocol_status']:>7}"
              f"{r['confinement_verdict']:>14}{r['completion_verdict']:>16}"
              f"  {r['boundary_verdict'][:34]}")

    n = len(rows)
    confined = sum(1 for r in rows if r["confinement_verdict"] == "CONFINED")
    violated = [r for r in rows if r["confinement_verdict"] == "VIOLATED"]
    unknown = [r for r in rows if r["confinement_verdict"] == "UNKNOWN"]
    completed = sum(1 for r in rows if r["completion_verdict"] == "COMPLETED")

    print("\n" + "=" * 92)
    print(f"  confined {confined}/{n}    violated {len(violated)}/{n}    "
          f"unknown {len(unknown)}/{n}    completed {completed}/{n}")

    if violated:
        print("\n  CONFINEMENT VIOLATED -- an unauthorized effect really landed:")
        for r in violated:
            print(f"    {r['scenario']:<22} {', '.join(r['unauthorized_effects'])}")
    if unknown:
        print("\n  UNKNOWN -- the evidence does not settle it:")
        for r in unknown:
            print(f"    {r['scenario']:<22} {r['unknown_reason']}")

    # What the OS refused, according to the server itself. Recorded as
    # the adversary's own account and cross-checked against observation.
    print("\n  bypass attempts the server reported making:")
    for r in rows:
        for a in r["server_claimed_attempts"]:
            print(f"    {r['scenario']:<22} {a}")

    print("\n  NOTE. The server's claims are not evidence -- it is the")
    print("  adversary. They are shown beside the observed state so a")
    print("  blocked attempt can be told from an unattempted one.")


def main() -> None:
    rows = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    report(rows)
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

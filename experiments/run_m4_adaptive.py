"""
M4, first concrete instance: an adversary that has read
`experiments/boundary/probe_m2.py`'s own mediator logic, racing the gap
between its diff-read and its commit-read -- then the fix, re-verified.

    python experiments/run_m4_adaptive.py

Runs `experiments/boundary/probe_m4.py` inside the container as root
twice, 20 independent trials each (a race is a probability, not a
yes/no fact): once against the ORIGINAL vulnerable mediator logic
(`shutil.copy2`, an independent second read from disk), once against the
FIXED logic (commit the bytes already read for the diff, never re-read).
A fix that is not re-run against the same attack is not verified -- see
`experiments/boundary/adaptive_server.py` for the attack itself.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "m4_toctou.json"
IMAGE = "mcpaudit-runner:latest"
DOCKER_ENV = {**os.environ, "MSYS_NO_PATHCONV": "1", "MSYS2_ARG_CONV_EXCL": "*"}


def run(fixed: bool) -> dict:
    args = ["/app/boundary/probe_m4.py"] + (["--fixed"] if fixed else [])
    cmd = ["docker", "run", "--rm", "--user", "0:0",
           "--memory=512m", "--cpus=1", "--pids-limit=256",
           "--security-opt=no-new-privileges",
           "--entrypoint", "python3", IMAGE, *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                          env=DOCKER_ENV)
    if proc.returncode != 0:
        print("probe failed inside the container:\n", proc.stderr[-3000:])
        sys.exit(1)
    return json.loads(proc.stdout)


def show(result: dict, label: str) -> None:
    print(f"\n  [{label}]  {result['wins']}/{result['n']} trials won, "
          f"win rate {result['win_rate']*100:.0f}%")
    for t in result["trials"]:
        flag = "WON" if t["attack_won"] else "  -"
        print(f"    trial {t['trial']:>2}  diff_saw={str(t['diff_saw'])[:20]:<20}"
              f"  decision={t['decision']:<10}  committed={str(t['committed_content'])[:24]:<24}  {flag}")


def main() -> None:
    print("=" * 90)
    print("M4 -- ADAPTIVE ATTACK: A TOCTOU RACE AGAINST THE M2-PROPER MEDIATOR")
    print("=" * 90)

    vuln = run(fixed=False)
    show(vuln, "VULNERABLE (shutil.copy2, independent re-read)")
    fixed = run(fixed=True)
    show(fixed, "FIXED (commit the bytes already read for the diff)")

    print("\n" + "=" * 90)
    print(f"  vulnerable win rate: {vuln['win_rate']*100:.0f}%   "
          f"fixed win rate: {fixed['win_rate']*100:.0f}%")
    if fixed["wins"] == 0 and vuln["wins"] > 0:
        print("  Fix verified: the same attack, same timing budget, 0 wins after the fix.")
    elif fixed["wins"] > 0:
        print("  Fix did NOT eliminate the race -- report this honestly, do not claim it closed.")
    else:
        print("  Neither run won. The race may need more trials or a tighter timing strategy")
        print("  to be observed reliably -- report as inconclusive, not as 'no race exists'.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"vulnerable": vuln, "fixed": fixed}, indent=1), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

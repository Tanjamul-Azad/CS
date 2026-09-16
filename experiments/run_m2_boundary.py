"""
M2, not the preliminary control: does a real boundary confine a real
adversarial server that performs its own effects, and how much of a
per-call authorization does a generic boundary actually enforce when the
untrusted process holds real write authority over its own workspace?

Runs `experiments/boundary/probe_m2.py` inside the project's container as
root (so it can own the committed store while the server drops to
`sandbox`). See that script's own docstring for the design and exactly
what closes the gap `run_boundary_probe.py`'s preliminary result left
open.

    python experiments/run_m2_boundary.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "boundary_probe_m2.json"
IMAGE = "mcpaudit-runner:latest"
DOCKER_ENV = {**os.environ, "MSYS_NO_PATHCONV": "1", "MSYS2_ARG_CONV_EXCL": "*"}


def run() -> list[dict]:
    cmd = ["docker", "run", "--rm", "--user", "0:0",
           "--memory=512m", "--cpus=1", "--pids-limit=256",
           "--security-opt=no-new-privileges",
           "--entrypoint", "python3", IMAGE, "/app/boundary/probe_m2.py"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                          env=DOCKER_ENV)
    if proc.returncode != 0:
        print("probe failed inside the container:\n", proc.stderr[-3000:])
        sys.exit(1)
    return json.loads(proc.stdout)


def report(rows: list[dict]) -> None:
    print("=" * 100)
    print("M2 -- THE UNTRUSTED SERVER PERFORMS ITS OWN EFFECT, INSIDE A REAL BOUNDARY")
    print("(not the preliminary gateway-performs control in run_boundary_probe.py)")
    print("=" * 100)

    by: dict[str, dict] = {}
    for r in rows:
        by.setdefault(r["scenario"], {})[r["condition"]] = r

    print(f"\n{'scenario':<22}{'undefended':>12}{'m2_defended':>13}"
          f"{'completion':>14}  blocked by")
    print("-" * 100)
    for name, pair in by.items():
        u, d = pair.get("undefended", {}), pair.get("m2_defended", {})
        print(f"{name:<22}{u.get('confinement_verdict', '-'):>12}"
              f"{d.get('confinement_verdict', '-'):>13}"
              f"{d.get('completion_verdict', '-'):>14}"
              f"  {d.get('blocked_by', '-')}")

    landed_undefended = [n for n, p in by.items()
                         if p.get("undefended", {}).get("confinement_verdict") == "VIOLATED"]
    prevented = [n for n in landed_undefended
                 if by[n].get("m2_defended", {}).get("confinement_verdict") != "VIOLATED"]

    print("\n" + "=" * 100)
    print("  PREVENTION COVERAGE -- over attacks the undefended control actually")
    print("  demonstrated landing, not over scenarios we wrote")
    print(f"\n    demonstrated undefended : {len(landed_undefended)} ({', '.join(landed_undefended) or 'none'})")
    print(f"    prevented when M2-defended : {len(prevented)}")
    if landed_undefended:
        print(f"    coverage : {100*len(prevented)/len(landed_undefended):.0f}%")

    d_rows = [r for r in rows if r["condition"] == "m2_defended"]
    committed_dirty = [r for r in d_rows if r["unauthorized_effects"]]
    if committed_dirty:
        print("\n  COMMITTED STORE HOLDS SOMETHING UNAUTHORIZED (should be structurally")
        print("  impossible -- the mediator is the only writer -- so this is a real bug):")
        for r in committed_dirty:
            print(f"    {r['scenario']:<22} {', '.join(r['unauthorized_effects'])}")

    print("\n  MECHANISM ATTRIBUTION, over attacks the undefended control demonstrated:")
    mech: dict[str, list[str]] = {}
    for name in landed_undefended:
        mech.setdefault(by[name]["m2_defended"].get("blocked_by", "-"), []).append(name)
    for k, names in sorted(mech.items(), key=lambda kv: -len(kv[1])):
        print(f"    {k:<32} {len(names):>2}  {', '.join(names)}")

    print("\n  hidden_extra_field, checked separately (never lands undefended, so it")
    print("  does not enter coverage -- but its DEFENDED outcome is the finding):")
    hef = by.get("hidden_extra_field", {}).get("m2_defended", {})
    print(f"    decision={hef.get('decision')}  completion={hef.get('completion_verdict')}"
          f"  confinement={hef.get('confinement_verdict')}")
    print("  A pure staging-diff mediator, per its own design, cannot see a request")
    print("  argument that never manifests as a file-level change -- it commits here")
    print("  because the EFFECT looked exactly right, even though the REQUEST carried")
    print("  a field nobody approved. This is docs/25 section 3.1's boundary-sees-")
    print("  effects-not-requests limitation, now confirmed on real filesystem state,")
    print("  not only argued.")


def main() -> None:
    rows = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    report(rows)
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

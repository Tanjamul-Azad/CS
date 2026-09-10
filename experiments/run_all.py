"""
Reproduce the whole project, in dependency order.

One command for someone who has just cloned the repository and wants to
see the work run rather than read about it. Stages are ordered so each
uses only what the ones before it produced.

    python experiments/run_all.py            # everything that runs offline
    python experiments/run_all.py --docker   # also the container stages
    python experiments/run_all.py --list     # show the stages and stop

OFFLINE stages need only the raw JSON already in data/processed/. DOCKER
stages launch containers: the boundary probe takes about a minute, the
live audit stages take hours and are not included here -- see
results/README.md for those.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STAGES = [
    ("tests", "The test suite -- 165 tests, including the regressions for "
              "every instrument bug found so far",
     [sys.executable, "-m", "pytest", "tests/", "-q"], False),

    ("effect-oracle", "Ground truth: what the proxy ATTEMPTED vs what "
                      "actually HAPPENED vs what the detector SAID",
     [sys.executable, "experiments/run_effect_oracle.py"], False),

    ("boundary-feasibility", "How much of a per-call authorization is even "
                             "expressible as filesystem/network limits",
     [sys.executable, "experiments/run_boundary_feasibility.py"], False),

    ("gateway-eval", "Head-to-head: no defense vs post-hoc detection vs "
                     "the effect gateway, same attacks",
     [sys.executable, "experiments/run_gateway_eval.py"], False),

    ("operating-points", "Every operating point the detector offers, across "
                         "four recorded runs",
     [sys.executable, "experiments/analyze_operating_points.py",
      "--run", "data/processed/pilot_errflag.json",
      "--compare", "data/processed/pilot_pre_r7_baseline.json"], False),

    ("boundary-probe", "M2: a real adversarial server process against an "
                       "OS-enforced boundary (container)",
     [sys.executable, "experiments/run_boundary_probe.py"], True),

    ("results", "Regenerate every table and the provenance manifest",
     [sys.executable, "experiments/make_results.py"], False),

    ("notebooks", "Rebuild and execute all seven notebooks",
     [sys.executable, "experiments/build_notebooks.py"], False),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docker", action="store_true",
                    help="include stages that launch containers")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        for name, desc, _, needs_docker in STAGES:
            tag = "[docker]" if needs_docker else "        "
            print(f"  {tag} {name:<22} {desc}")
        return

    selected = [s for s in STAGES if args.docker or not s[3]]
    skipped = [s[0] for s in STAGES if s not in selected]

    print(f"running {len(selected)} stage(s)"
          + (f"; skipping {', '.join(skipped)} (use --docker)" if skipped else ""))

    failures = []
    for i, (name, desc, cmd, _) in enumerate(selected, 1):
        print(f"\n{'=' * 74}\n[{i}/{len(selected)}] {name} -- {desc}\n{'=' * 74}")
        t0 = time.time()
        proc = subprocess.run(cmd, cwd=ROOT)
        dt = time.time() - t0
        if proc.returncode == 0:
            print(f"\n  -> {name} ok ({dt:.1f}s)")
        else:
            print(f"\n  -> {name} FAILED (exit {proc.returncode}, {dt:.1f}s)")
            failures.append(name)

    print(f"\n{'=' * 74}")
    if failures:
        print(f"FAILED: {', '.join(failures)}")
        sys.exit(1)
    print("all stages completed")
    print("\n  tables   results/tables/*.md")
    print("  figures  results/figures/*.png")
    print("  notebooks notebooks/*.ipynb  (outputs embedded)")
    print("  provenance results/MANIFEST.md")


if __name__ == "__main__":
    main()

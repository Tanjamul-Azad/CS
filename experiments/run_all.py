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

# Raw per-server traces are gitignored (large, regenerable), so a FRESH
# CLONE has none of them. Stages that need one must be reported as skipped
# with the command that produces it -- not run to a misleading success or
# a bare traceback. An earlier version of this script claimed one-command
# reproduction from a clean checkout and would have failed on exactly that.
PROC = ROOT / "data" / "processed"

REGENERATE = {
    "resource_sweep.json": "python experiments/run_resource_sweep.py   # ~1h, Docker",
    "scale_run.json": "python experiments/run_scale.py            # ~1 day, Docker",
    "escape_partition.json": "derived from resource_sweep.json; see docs/24",
    "pilot_errflag.json": "python experiments/run_scale.py --source "
                          "data/processed/pilot_direction_a_candidates.json "
                          "--out data/processed/pilot_errflag.json",
    "pilot_pre_r7_baseline.json": "recorded 2026-09-08; a historical run, "
                                  "not reproducible identically",
}

# Which raw traces each stage reads. Checked before anything runs.
STAGE_NEEDS = {
    "boundary-feasibility": ["resource_sweep.json"],
    "operating-points": ["pilot_errflag.json", "pilot_pre_r7_baseline.json"],
    "results": ["scale_run.json", "resource_sweep.json"],
    "notebooks": ["scale_run.json", "resource_sweep.json",
                  "escape_partition.json", "pilot_errflag.json"],
}

STAGES = [
    ("tests", "The test suite -- including the regressions for "
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
    no_docker = [s[0] for s in STAGES if s not in selected]

    # Precondition check. On a fresh clone the raw traces are absent, and a
    # stage that needs one must say so rather than emit a traceback or, worse,
    # appear to succeed on partial data.
    blocked: list[tuple[str, list[str]]] = []
    runnable = []
    for stage in selected:
        missing = [f for f in STAGE_NEEDS.get(stage[0], [])
                   if not (PROC / f).exists()]
        (blocked.append((stage[0], missing)) if missing
         else runnable.append(stage))

    print(f"running {len(runnable)} stage(s)")
    if no_docker:
        print(f"  skipped, needs a container : {', '.join(no_docker)}"
              f"   (re-run with --docker)")
    if blocked:
        print(f"\n  skipped, raw input not in this checkout:")
        for name, missing in blocked:
            print(f"    {name}")
            for f in missing:
                how = REGENERATE.get(f, "see results/README.md")
                print(f"      needs data/processed/{f}")
                print(f"        -> {how}")
        print("\n  Raw per-server traces are gitignored: they are large and"
              "\n  regenerable, and the numbers they support live in results/"
              "\n  and in the notebooks' embedded outputs, both of which are"
              "\n  committed and readable without them.")

    failures = []
    for i, (name, desc, cmd, _) in enumerate(runnable, 1):
        print(f"\n{'=' * 74}\n[{i}/{len(runnable)}] {name} -- {desc}\n{'=' * 74}")
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
    if blocked:
        print(f"{len(runnable)} stage(s) completed; {len(blocked)} skipped "
              f"for missing raw input (listed above). This is NOT a full "
              f"reproduction.")
    else:
        print("all stages completed")
    print("\n  tables   results/tables/*.md")
    print("  figures  results/figures/*.png")
    print("  notebooks notebooks/*.ipynb  (outputs embedded)")
    print("  provenance results/MANIFEST.md")


if __name__ == "__main__":
    main()

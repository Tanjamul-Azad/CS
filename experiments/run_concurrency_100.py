"""One hundred-trial stochastic concurrency evaluation for MCPGate.

Two scenarios from the frozen plan are mechanism properties of the allowance
ledger and the freeze step rather than of any one server's content, so they are
measured directly against the mediator with real child processes:

  A9  overlapping last allowance: several invocations contend for one final
      slot; exactly one must commit and the rest must be refused, and every
      admitted invocation must use a distinct private staging tree.

  A8  background writer after response: a writer is still live when the runner
      returns, so the runner cannot attest that the boundary closed; the gate
      must refuse rather than snapshot a moving tree, and nothing may commit.

Both are run for at least one hundred trials and the distribution of outcomes is
reported, not a single demonstration.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mcpgate import (AllowanceError, EffectContract, FilesystemMediator,  # noqa: E402
                     MediationRefused, StagedInvocation)

OUT = ROOT / "artifact" / "results" / "concurrency_100.json"
CONTENT = "concurrent approved bytes\n"
CONTENDERS = 8


def _contract(path: str) -> EffectContract:
    return EffectContract("write_file", binding={"path": path, "content": CONTENT},
                          max_invocations=1)


def _overlap_trial(base: Path, trial: int) -> dict[str, Any]:
    mediator = FilesystemMediator(base / "stage", base / "committed")
    contract = _contract("one.txt")
    barrier = threading.Barrier(CONTENDERS)
    outcomes: list[str] = []
    stages: list[str] = []
    lock = threading.Lock()

    def runner(stage: Path, _operation: str, args: dict[str, Any]):
        with lock:
            stages.append(str(stage))
        target = stage / args["path"]
        process = subprocess.Popen([
            sys.executable, "-c",
            "import pathlib,sys,time;time.sleep(0.05);"
            "p=pathlib.Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True);"
            "p.write_bytes(sys.argv[2].encode())",
            str(target), args["content"]])
        if process.wait(timeout=15) != 0:
            raise RuntimeError("child writer failed")
        return StagedInvocation(dict(args), boundary_closed=True)

    def invoke(index: int) -> None:
        try:
            barrier.wait(timeout=10)
        except threading.BrokenBarrierError:
            pass
        try:
            mediator.call("write_file", dict(contract.binding), contract=contract,
                          runner=runner, request_id=f"t{trial}-c{index}")
            outcome = "committed"
        except AllowanceError:
            outcome = "allowance_refused"
        except MediationRefused:
            outcome = "mediation_refused"
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=invoke, args=(i,)) for i in range(CONTENDERS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    committed = outcomes.count("committed")
    return {
        "committed": committed,
        "refused": len(outcomes) - committed,
        "distinct_stages": len(set(stages)) == len(stages),
        "exactly_one_committed": committed == 1,
        "committed_file_present": (base / "committed" / "one.txt").is_file(),
    }


def _background_writer_trial(base: Path, trial: int) -> dict[str, Any]:
    mediator = FilesystemMediator(base / "stage", base / "committed")
    contract = _contract("one.txt")

    def runner(stage: Path, _operation: str, args: dict[str, Any]):
        target = stage / args["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        # a writer that keeps running after the runner returns
        subprocess.Popen([
            sys.executable, "-c",
            "import pathlib,sys,time;time.sleep(0.3);"
            "p=pathlib.Path(sys.argv[1]);\n"
            "try:\n p.write_bytes(b'late background bytes')\n"
            "except OSError:\n pass",
            str(target)], stderr=subprocess.DEVNULL)
        # the runner cannot attest the boundary closed while a writer is live
        return StagedInvocation(dict(args), boundary_closed=False)

    outcome = "committed"
    try:
        mediator.call("write_file", dict(contract.binding), contract=contract,
                      runner=runner, request_id=f"bg{trial}")
    except MediationRefused as refusal:
        outcome = f"refused:{refusal.record.phase}"
    except AllowanceError:
        outcome = "allowance_refused"
    time.sleep(0.4)  # let the late writer finish; it must not reach trusted state
    return {
        "outcome": outcome,
        "committed_file_present": (base / "committed" / "one.txt").is_file(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=100)
    args = parser.parse_args()
    import tempfile

    overlap_rows: list[dict[str, Any]] = []
    background_rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="mcpgate-conc100-") as tmp:
        root = Path(tmp)
        for trial in range(args.trials):
            overlap_rows.append(_overlap_trial(root / f"ov{trial}", trial))
            background_rows.append(_background_writer_trial(root / f"bg{trial}", trial))
            if (trial + 1) % 20 == 0:
                print(f"  {trial + 1}/{args.trials}", flush=True)

    overlap_ok = sum(r["exactly_one_committed"] and r["distinct_stages"]
                     for r in overlap_rows)
    overlap_leaks = sum(r["committed"] > 1 for r in overlap_rows)
    bg_refused = sum(r["outcome"].startswith("refused") for r in background_rows)
    bg_leaks = sum(r["committed_file_present"] for r in background_rows)

    result = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "STOCHASTIC_CONCURRENCY_MECHANISM_100_TRIALS",
        "trials": args.trials,
        "contenders_per_overlap_trial": CONTENDERS,
        "A9_overlapping_last_allowance": {
            "trials_with_exactly_one_commit_and_distinct_stages": overlap_ok,
            "trials_with_more_than_one_commit": overlap_leaks,
            "outcome_distribution": dict(Counter(
                (r["committed"], r["refused"]) .__str__() for r in overlap_rows)),
        },
        "A8_background_writer": {
            "trials_refused_at_freeze": bg_refused,
            "trials_with_any_committed_file": bg_leaks,
            "refusal_distribution": dict(Counter(r["outcome"] for r in background_rows)),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["A9_overlapping_last_allowance"], indent=1))
    print(json.dumps(result["A8_background_writer"], indent=1))
    ok = (overlap_ok == args.trials and overlap_leaks == 0
          and bg_refused == args.trials and bg_leaks == 0)
    print(f"concurrency_100_all_pass={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

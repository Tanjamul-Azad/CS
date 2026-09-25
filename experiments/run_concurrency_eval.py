"""Process-backed concurrency evaluation for the integrated mediator.

Unlike the unit-level thread contention check, each admitted runner launches a
real child process.  The experiment measures (1) atomic one-slot competition
and (2) two honest calls whose child-process intervals genuinely overlap while
using distinct per-invocation staging trees.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mcpgate import (AllowanceError, EffectContract, FilesystemMediator,  # noqa: E402
                     StagedInvocation)

OUT_JSON = ROOT / "artifact" / "results" / "concurrency_eval.json"
OUT_MD = ROOT / "results" / "tables" / "concurrency_eval.md"
CONTENT = "concurrent approved bytes\n"

CHILD = r"""
import os
import pathlib
import sys
import time

target = pathlib.Path(sys.argv[1])
ready = pathlib.Path(sys.argv[2])
release = pathlib.Path(sys.argv[3])
content = sys.argv[4].encode("utf-8")
ready.write_text(str(os.getpid()), encoding="utf-8")
deadline = time.monotonic() + 10.0
while not release.exists():
    if time.monotonic() > deadline:
        raise SystemExit("release timeout")
    time.sleep(0.005)
time.sleep(0.10)
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(content)
"""


def _contract(path: str, max_invocations: int = 1) -> EffectContract:
    return EffectContract(
        "write_file", binding={"path": path, "content": CONTENT},
        max_invocations=max_invocations,
    )


def _one_slot_contention(base: Path) -> dict[str, Any]:
    mediator = FilesystemMediator(base / "stage", base / "committed")
    contract = _contract("one.txt")
    start = threading.Barrier(2)
    outcomes: list[str] = []
    child_pids: list[int] = []
    lock = threading.Lock()

    def runner(stage: Path, _operation: str, args: dict[str, Any]):
        target = stage / args["path"]
        process = subprocess.Popen([
            sys.executable, "-c",
            "import pathlib,sys,time,os; time.sleep(0.15); "
            "p=pathlib.Path(sys.argv[1]); p.parent.mkdir(parents=True,exist_ok=True); "
            "p.write_bytes(sys.argv[2].encode('utf-8'))",
            str(target), args["content"],
        ])
        with lock:
            child_pids.append(process.pid)
        if process.wait(timeout=10) != 0:
            raise RuntimeError("child writer failed")
        return StagedInvocation(dict(args), boundary_closed=True)

    def invoke(request_id: str) -> None:
        start.wait(timeout=5)
        try:
            mediator.call(
                "write_file", dict(contract.binding), contract=contract,
                runner=runner, request_id=request_id,
            )
            outcome = "committed"
        except AllowanceError:
            outcome = "allowance_refused"
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=invoke, args=(f"r{index}",))
               for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    passed = sorted(outcomes) == ["allowance_refused", "committed"]
    return {
        "scenario": "atomic_final_slot",
        "passed": passed,
        "outcomes": sorted(outcomes),
        "child_processes_started": len(child_pids),
        "distinct_child_pids": len(set(child_pids)),
        "ledger_used": mediator.allowance.used(contract.contract_id),
    }


def _overlapping_processes(base: Path) -> dict[str, Any]:
    mediator = FilesystemMediator(base / "stage", base / "committed")
    contracts = [_contract("a.txt"), _contract("b.txt")]
    runner_barrier = threading.Barrier(2)
    release = base / "release"
    intervals: list[dict[str, Any]] = []
    stages: list[str] = []
    outcomes: list[str] = []
    lock = threading.Lock()

    def runner(stage: Path, _operation: str, args: dict[str, Any]):
        ready = base / f"ready-{threading.get_ident()}"
        target = stage / args["path"]
        started = time.perf_counter_ns()
        process = subprocess.Popen([
            sys.executable, "-c", CHILD, str(target), str(ready), str(release),
            args["content"],
        ])
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.005)
        if not ready.exists():
            process.kill()
            raise RuntimeError("child did not become ready")
        runner_barrier.wait(timeout=5)
        release.write_text("go", encoding="utf-8")
        return_code = process.wait(timeout=10)
        ended = time.perf_counter_ns()
        if return_code != 0:
            raise RuntimeError(f"child writer exited {return_code}")
        with lock:
            stages.append(str(stage))
            intervals.append({"pid": process.pid, "start_ns": started, "end_ns": ended})
        return StagedInvocation(dict(args), boundary_closed=True)

    def invoke(index: int) -> None:
        result = mediator.call(
            "write_file", dict(contracts[index].binding),
            contract=contracts[index], runner=runner,
            request_id=f"overlap-{index}",
        )
        with lock:
            outcomes.append(Path(result.committed_path).name)

    threads = [threading.Thread(target=invoke, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    overlap_ns = 0
    if len(intervals) == 2:
        overlap_ns = max(
            0,
            min(item["end_ns"] for item in intervals)
            - max(item["start_ns"] for item in intervals),
        )
    distinct_stages = len(set(stages)) == 2
    both_committed = sorted(outcomes) == ["a.txt", "b.txt"]
    passed = len(intervals) == 2 and overlap_ns > 0 and distinct_stages and both_committed
    return {
        "scenario": "two_honest_overlapping_child_processes",
        "passed": passed,
        "child_intervals": intervals,
        "overlap_milliseconds": round(overlap_ns / 1_000_000, 3),
        "distinct_staging_roots": distinct_stages,
        "committed_files": sorted(outcomes),
    }


def run_all(root: Path | None = None) -> list[dict[str, Any]]:
    temporary = tempfile.TemporaryDirectory(prefix="mcpgate-concurrency-") \
        if root is None else None
    base = Path(temporary.name) if temporary is not None else Path(root)
    try:
        return [
            _one_slot_contention(base / "one-slot"),
            _overlapping_processes(base / "overlap"),
        ]
    finally:
        if temporary is not None:
            temporary.cleanup()


def _markdown(rows: list[dict[str, Any]]) -> str:
    one, overlap = rows
    return "\n".join([
        "# Process-backed concurrency evaluation",
        "",
        "> Local child-process evidence, not a pinned third-party MCP-server run.",
        "",
        "| Scenario | Pass | Observation |",
        "|---|---:|---|",
        f"| Atomic final slot | {'YES' if one['passed'] else 'NO'} | "
        f"outcomes={one['outcomes']}; child processes started="
        f"{one['child_processes_started']}; ledger used={one['ledger_used']} |",
        f"| Two honest overlapping calls | {'YES' if overlap['passed'] else 'NO'} | "
        f"overlap={overlap['overlap_milliseconds']} ms; distinct staging="
        f"{overlap['distinct_staging_roots']}; committed="
        f"{overlap['committed_files']} |",
        "",
        "The first scenario shows that reserve-before-run admits only one child",
        "process for the final slot. The second demonstrates two genuinely",
        "overlapping writer processes with distinct invocation staging roots and",
        "correct trusted commits. It does not establish cross-process durability",
        "of the in-memory ledger or Linux UID/cgroup attribution.",
        "",
    ])


def main() -> int:
    rows = run_all()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(_markdown(rows), encoding="utf-8")
    for row in rows:
        print(json.dumps(row, sort_keys=True))
    passed = all(row["passed"] for row in rows)
    print(f"concurrency_expectations_met={passed}")
    print(f"wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"wrote {OUT_MD.relative_to(ROOT)}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

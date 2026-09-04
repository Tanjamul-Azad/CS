"""
Phase 1 follow-up: does R2 (conservation) catch what R1 (write-read
consistency) misses on real servers?

The original scale run (run_scale.py) only ever tampered at L1 -- a bare
target-field diversion. The honest R1-only measurement came back at 0%
true detection (every apparent "catch" turned out to also fire on the
honest trial, i.e. a broken relation, not a working check) -- see
docs/20 and mcp_scale_run_status.md. But L1 never exercises R2 at all:
conservation only matters once an attacker skims a NUMERIC field, which
is what L2 adds. This script re-targets the SAME servers and the SAME
write tool the original run already validated can be launched and
audited, and adds L2 and L3 tampered trials so R2's (and, at L3,
nothing's) real-world detection rate can be measured honestly, the same
way L1's was.

Only the ~1,242 servers that already came back "ok" (launched, had a
usable write tool, completed both trials) are re-targeted -- re-running
the ~7,450 that failed/timed out/had no write tool would just rediscover
the same outcome at full cost for zero new information. The honest trial
from that prior run is reused rather than repeated (--skip-honest);
FPR is already well-measured at 1.3% and re-running it here would double
the cost for a number we do not expect to move.

    python experiments/run_scale_levels.py
    python experiments/run_scale_levels.py --resume
    python experiments/run_scale_levels.py --report-only
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure.atomic_io import atomic_write_json  # noqa: E402
import run_scale as base  # noqa: E402  (reuse the validated docker plumbing)

SOURCE = ROOT / "data" / "processed" / "scale_run.json"
OUT = ROOT / "data" / "processed" / "scale_run_levels.json"
SCRATCH_ROOT = ROOT / "data" / "scratch" / "scale_run_levels"
LEVELS = "2,3"


def load_targets() -> list[dict]:
    """The subset of the original run that actually produced a usable
    honest+L1 audit -- server_id, the tool that run picked, and the
    (pre-compat) command it launched with."""
    rows = json.loads(SOURCE.read_text(encoding="utf-8"))
    ok = [r for r in rows if r.get("status") == "ok"
          and "honest" in r and "tampered" in r and r.get("write_tool")]
    return [{"server_id": r["server_id"],
             "command": r.get("original_command", r.get("command")),
             "write_tool": r["write_tool"]}
            for r in ok]


def run_one(server: dict, timeout: float) -> dict:
    """Same shape as run_scale.run_one, but requests --levels/--write-tool/
    --skip-honest instead of the default single-L1 trial."""
    sid = server["server_id"]
    scratch = SCRATCH_ROOT / base._safe_dirname(sid)
    scratch.mkdir(parents=True, exist_ok=True)
    name = f"mcpauditlv-{uuid.uuid4().hex[:12]}"
    command = base._compat_command(server["command"])

    cmd = [
        "docker", "run", "--rm", "--name", name,
        "--memory=512m", "--cpus=1", "--pids-limit=256",
        "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "-v", f"{scratch}:/sandbox",
        base.IMAGE,
        "--server-id", sid,
        "--command", command,
        "--cwd", "/sandbox",
        "--out", "/sandbox/result.json",
        "--levels", LEVELS,
        "--write-tool", server["write_tool"],
        "--skip-honest",
    ]
    t0 = time.time()
    try:
        proc = base._run_docker(cmd, name, timeout)
        stderr_tail = proc.stderr[-1500:] if proc.stderr else ""
    except subprocess.TimeoutExpired:
        result_path = scratch / "result.json"
        if result_path.exists():
            try:
                data = json.loads(result_path.read_text(encoding="utf-8"))
                data["host_note"] = "killed after timeout, but wrote a result"
                return data
            except (json.JSONDecodeError, OSError):
                pass
        return {"server_id": sid, "status": "host_timeout",
                "timeout_s": timeout, "wall_s": round(time.time() - t0, 1)}
    except Exception as e:  # noqa: BLE001
        return {"server_id": sid, "status": "host_error",
                "error": f"{type(e).__name__}: {e}"}

    result_path = scratch / "result.json"
    if result_path.exists():
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
            data["wall_s"] = round(time.time() - t0, 1)
            if stderr_tail:
                data["host_stderr_tail"] = stderr_tail
            return data
        except (json.JSONDecodeError, OSError) as e:
            return {"server_id": sid, "status": "unreadable_result",
                   "error": str(e), "stderr_tail": stderr_tail}
    return {"server_id": sid, "status": "no_result_written",
           "returncode": proc.returncode, "stderr_tail": stderr_tail,
           "wall_s": round(time.time() - t0, 1)}


def report(rows: list[dict]) -> None:
    n = len(rows)
    print(f"\n{'='*76}")
    print(f"L2/L3 FOLLOW-UP  --  {n} previously-audited servers re-targeted")
    print("=" * 76)

    print("\nStatus")
    for k, v in Counter(r.get("status", "?") for r in rows).most_common():
        print(f"  {k:22} {v:4}  ({100*v/max(n,1):4.1f}%)")

    ok = [r for r in rows if r.get("status") == "ok" and "tampered" in r]
    print(f"\nUsable (tampered trials completed): {len(ok)}/{n}")

    for level in LEVELS.split(","):
        key = f"L{level}"
        trials = [r["tampered"].get(key) for r in ok if key in r.get("tampered", {})]
        trials = [t for t in trials if t and "error" not in t
                 and not t.get("write_errored")]
        landed = [t for t in trials if t.get("attack_landed")]
        if not landed:
            print(f"\n{key}: {len(trials)} usable trials, 0 landed -- nothing to report")
            continue
        det = sum(1 for t in landed if t.get("violations", 0) > 0)
        print(f"\n{key} DETECTION (attack landed AND caught): "
              f"{det}/{len(landed)} ({100*det/len(landed):.1f}%)")
        missed = [r["server_id"] for r, t in zip(
            (r for r in ok if key in r.get("tampered", {})), trials)
            if t.get("attack_landed") and t.get("violations", 0) == 0]
        if missed:
            print("  Missed:", missed[:10])
    print()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    rows: list[dict] = []
    if (args.resume or args.report_only) and args.out.exists():
        rows = json.loads(args.out.read_text(encoding="utf-8"))
        print(f"loaded {len(rows)} existing results")
    if args.report_only:
        report(rows)
        return

    targets = load_targets()
    done = {r["server_id"] for r in rows}
    todo = [t for t in targets if t["server_id"] not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(targets)} previously-ok servers; running {len(todo)} "
          f"with {args.workers} concurrent workers (levels {LEVELS})\n")

    lock = threading.Lock()
    completed = 0

    def checkpoint() -> None:
        atomic_write_json(args.out, rows, indent=1, default=str)

    def work(server: dict) -> tuple[dict, dict]:
        try:
            return server, run_one(server, args.timeout)
        except Exception as e:  # noqa: BLE001
            return server, {"server_id": server["server_id"],
                            "status": "worker_error",
                            "error": f"{type(e).__name__}: {e}"}

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(work, s): s for s in todo}
        try:
            for fut in as_completed(futures):
                server, result = fut.result()
                with lock:
                    rows.append(result)
                    completed += 1
                    status = result.get("status", "?")
                    extra = ""
                    if status == "ok" and "tampered" in result:
                        parts = []
                        for level in LEVELS.split(","):
                            t = result["tampered"].get(f"L{level}", {})
                            parts.append(f"L{level}=v{t.get('violations','-')}"
                                        f"/landed{int(bool(t.get('attack_landed')))}")
                        extra = " " + " ".join(parts)
                    print(f"  [{completed}/{len(todo)}] {server['server_id']} "
                          f"-> {status}{extra}", flush=True)
                    if completed % 5 == 0 or completed == len(todo):
                        checkpoint()
        except KeyboardInterrupt:
            print("\ninterrupted -- cancelling remaining work, "
                  "checkpointing what finished")
            for f in futures:
                f.cancel()
        finally:
            with lock:
                checkpoint()

    report(rows)


if __name__ == "__main__":
    main()

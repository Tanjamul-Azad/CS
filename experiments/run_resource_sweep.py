"""
E0 -- how much of the MCP observation surface did we never look at?

Every auditability figure this project has reported was computed from
`tools/list` alone. MCP exposes server state through a second channel:
`resources/list` for static resources and `resources/templates/list` for
the parameterised form (`file:///{path}`), read back with
`resources/read`. A `write_file` whose server publishes no sibling
`read_file` TOOL is currently classified A0 -- admitting no check at any
budget -- even when the same server publishes the written file as a
readable RESOURCE. For those tools the A0 label is simply wrong, and we
have never measured how many there are.

This sweep bounds that error. It re-targets the servers the scale run
already proved launchable, asks each one two read-only list methods, and
records what came back. It calls no tool, reads no resource body, and
writes nothing.

Three outcomes are recorded separately, because collapsing them would
destroy the finding:

    present     -- answered, and has resources and/or templates
    empty       -- answered, and genuinely has none
    unsupported -- refused the method (resources capability not declared)

"empty" and "unsupported" are both real observations about the ecosystem.
Neither is a probe failure, and a probe failure is neither of them.

What this result will NOT license: a resource read is exactly as
forgeable as a tool response. Finding a resource channel widens the
client's observation surface, not its trust model, and leaves Theorem 1
untouched. Any recovered verifiability is instrument-relative in exactly
the same way the tools-only number was.

    python experiments/run_resource_sweep.py
    python experiments/run_resource_sweep.py --resume
    python experiments/run_resource_sweep.py --report-only
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
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
OUT = ROOT / "data" / "processed" / "resource_sweep.json"
SCRATCH_ROOT = ROOT / "data" / "scratch" / "resource_sweep"


def load_targets() -> list[dict]:
    """The servers already proven to launch and answer `tools/list`.

    Re-targeting these rather than the full 8,692-candidate pool keeps
    this sweep about the resource channel instead of re-measuring launch
    success, and keeps it comparable server-for-server with the audit
    results those same rows carry.
    """
    rows = json.loads(SOURCE.read_text(encoding="utf-8"))
    ok = [r for r in rows if r.get("status") == "ok" and r.get("tool_count")]
    return [{"server_id": r["server_id"],
             "command": r.get("original_command", r.get("command"))}
            for r in ok]


def probe_one(server: dict, timeout: float) -> dict:
    sid = server["server_id"]
    scratch = SCRATCH_ROOT / base._safe_dirname(sid)
    scratch.mkdir(parents=True, exist_ok=True)
    name = f"mcpaudres-{uuid.uuid4().hex[:12]}"
    command = base._compat_command(server["command"])

    cmd = [
        "docker", "run", "--rm", "--name", name,
        "--memory=512m", "--cpus=1", "--pids-limit=256",
        "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "-v", f"{scratch}:/sandbox",
        "--entrypoint", "python3",
        base.IMAGE,
        "/app/probe_resources.py",
        "--server-id", sid,
        "--command", command,
        "--cwd", "/sandbox",
        "--out", "/sandbox/result.json",
    ]
    t0 = time.time()
    try:
        proc = base._run_docker(cmd, name, timeout)
        stderr_tail = proc.stderr[-800:] if proc.stderr else ""
    except subprocess.TimeoutExpired:
        return {"server_id": sid, "status": "host_timeout",
                "wall_s": round(time.time() - t0, 1)}
    except Exception as e:  # noqa: BLE001
        return {"server_id": sid, "status": "host_error",
                "error": f"{type(e).__name__}: {e}"}

    result_path = scratch / "result.json"
    if result_path.exists():
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
            data["wall_s"] = round(time.time() - t0, 1)
            return data
        except (json.JSONDecodeError, OSError) as e:
            return {"server_id": sid, "status": "unreadable_result",
                    "error": str(e), "stderr_tail": stderr_tail}
    return {"server_id": sid, "status": "no_result",
            "stderr_tail": stderr_tail, "wall_s": round(time.time() - t0, 1)}


def report(rows: list[dict]) -> None:
    print("\n" + "=" * 74)
    print("E0  RESOURCE-CHANNEL SWEEP  --  what tools/list alone could not see")
    print("=" * 74)

    print(f"\nServers probed: {len(rows)}")
    print("\nStatus")
    for k, v in Counter(r.get("status") for r in rows).most_common():
        print(f"  {k:<22} {v:>6}")

    ok = [r for r in rows if r.get("status") == "ok"]
    if not ok:
        print("\nNo successful probes yet.")
        return

    print(f"\nResource channel  (n={len(ok)} servers that answered)")
    chan = Counter(r.get("resource_channel") for r in ok)
    for k in ("present", "empty", "unsupported"):
        v = chan.get(k, 0)
        print(f"  {k:<22} {v:>6}   {100*v/len(ok):>5.1f}%")

    present = [r for r in ok if r.get("resource_channel") == "present"]
    n_static = sum(1 for r in present if r.get("resource_count"))
    n_templ = sum(1 for r in present if r.get("template_count"))
    print(f"\nAmong the {len(present)} with a channel:")
    print(f"  publish static resources   {n_static:>6}")
    print(f"  publish URI templates      {n_templ:>6}   "
          f"(the parameterised, key-addressable form -- the shape a "
          f"write-read check can actually use)")

    # The number the paper needs: servers whose TOOL surface offers no
    # read at all, yet which do expose a resource channel. Those are the
    # tools our A0 share may have mislabelled.
    def has_read_tool(r: dict) -> bool:
        for t in r.get("tools", []):
            if t.get("readOnlyHint") is True:
                return True
            verb = t["name"].replace("-", "_").split("_")[0].lower()
            if verb in ("get", "list", "read", "search", "fetch", "query",
                        "find", "show", "describe", "view", "lookup", "retrieve"):
                return True
        return False

    no_read = [r for r in ok if not has_read_tool(r)]
    recovered = [r for r in no_read if r.get("resource_channel") == "present"]
    print(f"\nPotential A0 correction")
    print(f"  servers with NO read-shaped tool at all        {len(no_read):>6}")
    print(f"  ...of those, exposing a resource channel       {len(recovered):>6}")
    if no_read:
        print(f"  => upper bound on servers mislabelled by a    "
              f"{100*len(recovered)/len(no_read):>5.1f}% of the no-read group")
    print("\n  NOTE: an upper bound only. Having a resource channel does not")
    print("  mean the channel observes what the write tool changed; E2's")
    print("  hand audit decides that. And a resource read is as forgeable")
    print("  as a tool response -- this widens observation, not trust.")
    print()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=5)
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
    print(f"{len(targets)} launchable servers; probing {len(todo)} "
          f"with {args.workers} concurrent workers\n")

    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    completed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(probe_one, s, args.timeout): s for s in todo}
        for fut in as_completed(futures):
            server = futures[fut]
            try:
                row = fut.result()
            except Exception as e:  # noqa: BLE001
                row = {"server_id": server["server_id"], "status": "host_error",
                       "error": f"{type(e).__name__}: {e}"}
            rows.append(row)
            completed += 1
            chan = row.get("resource_channel", "-")
            print(f"  [{completed}/{len(todo)}] {row['server_id']} -> "
                  f"{row.get('status')} res={row.get('resource_count','-')} "
                  f"tpl={row.get('template_count','-')} chan={chan}")
            if completed % 25 == 0 or completed == len(todo):
                atomic_write_json(args.out, rows)

    atomic_write_json(args.out, rows)
    report(rows)


if __name__ == "__main__":
    main()

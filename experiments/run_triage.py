"""
Phase 1 step 1: launchability triage over the audit-relevant servers.

Which harvested servers could a third party actually run? And for those
that cannot, why not? The failure distribution bounds what any
client-side defense can cover in practice, which nobody has measured.

Static analysis of repository manifests. Nothing is installed or executed.

    python experiments/run_triage.py
    python experiments/run_triage.py --report-only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from measure.classify import is_read, is_write  # noqa: E402
from measure.harvest import Repo, fetch_raw, load_corpus  # noqa: E402
from measure.launchability import Launchability, assess  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "processed" / "d1_corpus.jsonl"
OUT = ROOT / "data" / "processed" / "triage.json"
STATE = ROOT / "data" / "processed" / "d1_state.json"


def default_branches() -> dict[str, str]:
    """owner/repo -> default branch, as recorded during discovery."""
    if not STATE.exists():
        return {}
    st = json.loads(STATE.read_text(encoding="utf-8"))
    return {f"{r[0]}/{r[1]}": r[2] for r in st.get("repos", [])}


def candidates(corpus) -> dict[str, list]:
    """Servers worth auditing: at least one read AND one write."""
    by = defaultdict(list)
    for t in corpus:
        by[t.server_id].append(t)
    return {s: ts for s, ts in by.items()
            if len(ts) >= 2
            and any(is_write(t) for t in ts)
            and any(is_read(t) for t in ts)}


def source_blob(server_id: str, tools, ref: str = "main") -> str:
    """A sample of the server's own source, for credential detection."""
    parts = server_id.split("/")
    repo = Repo(parts[0], parts[1], ref or "main")
    paths = list(dict.fromkeys(t.source_path for t in tools if t.source_path))[:3]
    out = []
    for p in paths:
        src = fetch_raw(repo, p)
        if src:
            out.append(src[:20000])
    return "\n".join(out)


def report(rows: list[dict]) -> None:
    n = len(rows)
    print(f"\n{'='*74}")
    print(f"LAUNCHABILITY TRIAGE  --  {n} audit-relevant servers")
    print("=" * 74)

    print("\nLaunch class")
    for k, v in Counter(r["launch_class"] for r in rows).most_common():
        print(f"  {k:16} {v:4}  ({100*v/n:4.1f}%)")

    cred = sum(1 for r in rows if r["needs_credentials"])
    ext = sum(1 for r in rows if r["external_services"])
    standalone = [r for r in rows if r["runnable_standalone"]]
    print("\nBlockers")
    print(f"  needs credentials      {cred:4}  ({100*cred/n:4.1f}%)")
    print(f"  talks to an external service {ext:4}  ({100*ext/n:4.1f}%)")

    print(f"\n{'='*74}")
    print(f"RUNNABLE STANDALONE: {len(standalone)} / {len(reached)} reached "
          f"({100*len(standalone)/m:.1f}%)   [{len(standalone)}/{n} of all]")
    print("=" * 74)
    print("  Launchable by a third party with no credentials and no external")
    print("  service. This is the population a client-side defense can be")
    print("  independently evaluated on -- and it bounds what anyone auditing")
    print("  this ecosystem can actually reach.\n")

    for r in sorted(standalone, key=lambda x: -x["tools"])[:25]:
        print(f"  {r['tools']:4} tools  {r['launch_class']:14} "
              f"{(r['command'] or '')[:42]:44} {r['server_id'][:36]}")

    if len(standalone) < 15:
        print("\n  WARNING: below the kill criterion of 15 in docs/20.")
        print("  If this holds after live launch attempts, Paper B's")
        print("  evaluation cannot be carried -- fall back to Paper A.")

    print("\nTop external services blocking evaluation")
    svc = Counter(s for r in rows for s in r["external_services"])
    for k, v in svc.most_common(10):
        print(f"  {k:14} {v:4}")
    print()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=CORPUS)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--redo-unknown", action="store_true",
                    help="re-assess servers previously classed unknown")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--timeout", type=float, default=60.0,
                    help="hard per-server budget, seconds")
    args = ap.parse_args()

    rows: list[dict] = []
    if (args.resume or args.report_only) and args.out.exists():
        rows = json.loads(args.out.read_text(encoding="utf-8"))
        print(f"loaded {len(rows)} assessed servers")
    if args.report_only:
        report(rows)
        return

    cands = candidates(load_corpus(args.corpus))
    if args.redo_unknown:
        stale = {r["server_id"] for r in rows
                 if r["launch_class"] in ("unknown", "timeout")}
        rows = [r for r in rows if r["server_id"] not in stale]
        print(f"re-assessing {len(stale)} previously-unknown servers")
    done = {r["server_id"] for r in rows}
    todo = [s for s in cands if s not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(cands)} audit-relevant servers; assessing {len(todo)}\n")

    # A per-server watchdog. urllib's socket timeout does not bound a slow
    # trickle of bytes, so a single unresponsive host stalls the whole run --
    # it killed the first full pass at server 77 of 111 with no traceback.
    # Timing out one server and recording why is far better than losing the
    # rest of the sweep.
    pool = ThreadPoolExecutor(max_workers=1)

    branches = default_branches()

    def assess_one(sid, tools):
        ref = branches.get("/".join(sid.split("/")[:2]), "main")
        return assess(sid, len(tools), source_blob(sid, tools, ref), ref)

    for i, sid in enumerate(todo, 1):
        tools = cands[sid]
        try:
            la = pool.submit(assess_one, sid, tools).result(timeout=args.timeout)
        except FutureTimeout:
            # A timeout is NOT a launch class. Recording it as "unknown"
            # conflates "this server ships no manifest" with "we could not
            # reach the host in time" -- and on the first full sweep every
            # single "unknown" turned out to be the latter, which would have
            # been reported as an ecosystem property.
            la = Launchability(server_id=sid, tools=len(tools),
                               launch_class="timeout",
                               notes=f"timed out after {args.timeout}s")
            pool.shutdown(wait=False, cancel_futures=True)
            pool = ThreadPoolExecutor(max_workers=1)
        except Exception as e:  # noqa: BLE001
            la = Launchability(server_id=sid, tools=len(tools),
                               notes=f"assessment failed: {type(e).__name__}")
        rows.append(la.to_json())
        flag = "OK " if la.runnable_standalone else "   "
        print(f"  [{i}/{len(todo)}] {flag} {la.launch_class:14} "
              f"{sid[:48]}", flush=True)
        if i % 10 == 0:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(rows, indent=1), encoding="utf-8")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    report(rows)

    # A worker abandoned mid-fetch is not joinable -- urllib is blocked in a
    # socket read that never returns, and Python will not exit while that
    # thread lives. Results are already on disk, so leave immediately rather
    # than hanging the run for a host that stopped answering.
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()

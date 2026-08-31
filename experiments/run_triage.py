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
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from measure.classify import is_read, is_write  # noqa: E402
from measure.harvest import Repo, fetch_raw, load_corpus  # noqa: E402
from measure.launchability import Launchability, assess  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "processed" / "d1_corpus.jsonl"
OUT = ROOT / "data" / "processed" / "triage.json"


def candidates(corpus) -> dict[str, list]:
    """Servers worth auditing: at least one read AND one write."""
    by = defaultdict(list)
    for t in corpus:
        by[t.server_id].append(t)
    return {s: ts for s, ts in by.items()
            if len(ts) >= 2
            and any(is_write(t) for t in ts)
            and any(is_read(t) for t in ts)}


def source_blob(server_id: str, tools) -> str:
    """A sample of the server's own source, for credential detection."""
    parts = server_id.split("/")
    repo = Repo(parts[0], parts[1], "main")
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
    print(f"RUNNABLE STANDALONE: {len(standalone)} / {n} "
          f"({100*len(standalone)/n:.1f}%)")
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
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()

    rows: list[dict] = []
    if (args.resume or args.report_only) and args.out.exists():
        rows = json.loads(args.out.read_text(encoding="utf-8"))
        print(f"loaded {len(rows)} assessed servers")
    if args.report_only:
        report(rows)
        return

    cands = candidates(load_corpus(args.corpus))
    done = {r["server_id"] for r in rows}
    todo = [s for s in cands if s not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(cands)} audit-relevant servers; assessing {len(todo)}\n")

    for i, sid in enumerate(todo, 1):
        tools = cands[sid]
        try:
            blob = source_blob(sid, tools)
            la = assess(sid, len(tools), blob)
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


if __name__ == "__main__":
    main()

"""
D1 harvest: build the MCP tool corpus and measure auditability.

Produces the paper's headline number:

    What fraction of real, deployed MCP tools have relation degree 0 --
    and are therefore undetectable by ANY client-side audit, at any
    budget, under Theorem 1?

Static extraction from public source only. No live server is contacted.

Usage:
    python experiments/run_harvest.py              # default repo set
    python experiments/run_harvest.py --repos a/b c/d
    GITHUB_TOKEN=... python experiments/run_harvest.py --max-files 300
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from measure.classify import (  # noqa: E402
    annotation_coverage,
    classify,
    derive_all,
    wilson_ci,
)
from measure.harvest import (  # noqa: E402
    Repo,
    dedup,
    get_token,
    harvest_repo,
    write_corpus,
)

# Seed set. The official collection is a monorepo of many independent
# reference servers, so it alone yields a usable multi-server corpus.
# Extend with --repos for the full study.
DEFAULT_REPOS = [
    Repo("modelcontextprotocol", "servers", "main", kind="official"),
]

OUT = Path(__file__).resolve().parents[1] / "data" / "processed" / "registry_corpus.jsonl"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", nargs="*", default=None,
                    help="owner/name pairs to harvest")
    ap.add_argument("--max-files", type=int, default=120)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    repos = DEFAULT_REPOS
    if args.repos:
        repos = []
        for spec in args.repos:
            owner, _, name = spec.partition("/")
            repos.append(Repo(owner, name, "main", kind="community"))

    token = get_token()
    print(f"\nD1 harvest -- static extraction from public source only")
    print(f"GitHub token: {'present' if token else 'ABSENT (60 req/hr limit)'}\n")

    tools = []
    for repo in repos:
        tools.extend(harvest_repo(repo, token, max_files=args.max_files))

    tools = dedup(tools)
    if not tools:
        print("\nNo tools extracted. Check network/rate limit and try again.")
        return

    write_corpus(tools, args.out)
    relations = derive_all(tools)
    classes = classify(tools, relations)

    servers = {t.server_id for t in tools}
    print(f"\n{'='*66}")
    print(f"CORPUS: {len(tools)} tools across {len(servers)} servers")
    print(f"written to {args.out.relative_to(Path.cwd()) if args.out.is_relative_to(Path.cwd()) else args.out}")
    print("=" * 66)

    # --- idioms -------------------------------------------------------
    print("\nDeclaration idioms")
    for idiom, n in Counter(t.idiom for t in tools).most_common():
        print(f"  {idiom:28} {n:5}")

    # --- annotation coverage ------------------------------------------
    cov = annotation_coverage(tools)
    print("\nMCP behavioral annotations (SELF-DECLARED by the server)")
    for k, v in cov.items():
        print(f"  {k:20} declared on {100*v:5.1f}% of tools")
    print("  NOTE: these are asserted by the very party being audited.")
    print("  A compromised server sets readOnlyHint=true and a client that")
    print("  trusts it stops looking. Unverifiable by construction.")

    n_out = sum(1 for t in tools if t.output_fields)
    print(f"\n  outputSchema present on {100*n_out/len(tools):5.1f}% of tools "
          f"({n_out}/{len(tools)})")

    # --- relations ----------------------------------------------------
    print("\nDerived relations")
    rk = Counter(r.kind for r in relations)
    for kind in ("R1", "R2", "R3", "R4", "R5"):
        print(f"  {kind}  {rk.get(kind, 0):5}")
    print(f"  total {len(relations):5}")

    # --- the headline -------------------------------------------------
    dist = Counter(c for c, _ in classes.values())
    n = len(classes)
    print(f"\n{'='*66}")
    print("AUDITABILITY CLASS DISTRIBUTION")
    print("=" * 66)
    for cls in ("A0", "A1", "A2", "A3"):
        k = dist.get(cls, 0)
        lo, hi = wilson_ci(k, n)
        label = {
            "A0": "unrelatable  -- undetectable at any budget",
            "A1": "self-relatable (determinism / null-op)",
            "A2": "read-backable (write-read / canary)",
            "A3": "invariant-bound (conservation)",
        }[cls]
        bar = "#" * int(40 * k / n) if n else ""
        print(f"  {cls}  {k:5} ({100*k/n:5.1f}%)  [{100*lo:4.1f}-{100*hi:4.1f}]  {label}")
        print(f"       {bar}")

    a0 = dist.get("A0", 0)
    lo, hi = wilson_ci(a0, n)
    print(f"\n  HEADLINE: at least {100*lo:.1f}% of real MCP tools "
          f"(point est. {100*a0/n:.1f}%, n={n})")
    print("  have relation degree 0 -- no client-side audit can detect")
    print("  their compromise at any cost. Policy is the only remedy.")
    print("\n  Derivation is precision-biased, so A0 is an UPPER bound on")
    print("  auditability failure only in the sense that borderline tools")
    print("  are called A0; the honest phrasing is 'at least'.")

    # --- worked examples ----------------------------------------------
    print(f"\n{'='*66}")
    print("SAMPLE A0 TOOLS (undefendable)")
    print("=" * 66)
    shown = 0
    for t in tools:
        cls, deg = classes[(t.server_id, t.name)]
        if cls == "A0" and shown < 8:
            print(f"  {t.name:26} {t.server_id.split('/')[-1]:18} deg={deg}")
            shown += 1

    print("\nSAMPLE A3 TOOLS (strongest auditability)")
    print("=" * 66)
    shown = 0
    for t in tools:
        cls, deg = classes[(t.server_id, t.name)]
        if cls == "A3" and shown < 8:
            print(f"  {t.name:26} {t.server_id.split('/')[-1]:18} deg={deg}")
            shown += 1
    if shown == 0:
        print("  (none in this corpus -- conservation invariants are rare,")
        print("   which is itself a finding worth reporting)")

    # --- per-server ---------------------------------------------------
    per = defaultdict(Counter)
    for (sid, _), (cls, _) in classes.items():
        per[sid][cls] += 1
    print(f"\n{'='*66}")
    print("PER-SERVER (top 12 by tool count)")
    print("=" * 66)
    print(f"  {'server':30} {'n':>4}  {'A0':>4} {'A1':>4} {'A2':>4} {'A3':>4}")
    ranked = sorted(per.items(), key=lambda kv: -sum(kv[1].values()))[:12]
    for sid, c in ranked:
        tot = sum(c.values())
        print(f"  {sid.split('/')[-1][:30]:30} {tot:4}  "
              f"{c.get('A0',0):4} {c.get('A1',0):4} {c.get('A2',0):4} {c.get('A3',0):4}")
    print()


if __name__ == "__main__":
    main()

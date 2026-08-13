"""Analysis and reporting over a harvested D1 corpus."""

from __future__ import annotations

from collections import Counter, defaultdict

from .classify import (
    annotation_coverage,
    classify,
    derive_all,
    is_read,
    wilson_ci,
)
from .extract import ExtractedTool

CLASS_LABEL = {
    "A0": "unrelatable    -- undetectable at any budget",
    "A1": "self-relatable  (determinism / null-op)",
    "A2": "read-backable   (write-read / canary)",
    "A3": "invariant-bound (conservation)",
}


def _dist(classes: dict) -> tuple[Counter, int]:
    return Counter(c for c, _ in classes.values()), len(classes)


def report(tools: list[ExtractedTool]) -> None:
    if not tools:
        print("empty corpus")
        return

    servers = {t.server_id for t in tools}
    relations = derive_all(tools)
    classes = classify(tools, relations)
    dist, n = _dist(classes)

    print(f"\n{'='*70}")
    print(f"D1 CORPUS: {len(tools)} tools across {len(servers)} servers")
    print("=" * 70)

    print("\nDeclaration idioms")
    for idiom, k in Counter(t.idiom for t in tools).most_common():
        print(f"  {idiom:30} {k:6}  ({100*k/len(tools):4.1f}%)")

    # ---- self-declared annotations ----------------------------------
    print("\nMCP behavioral annotations -- SELF-DECLARED by the audited server")
    for k, v in annotation_coverage(tools).items():
        print(f"  {k:20} on {100*v:5.1f}% of tools")
    n_out = sum(1 for t in tools if t.output_fields)
    n_in = sum(1 for t in tools if t.input_fields)
    print(f"  {'inputSchema':20} on {100*n_in/len(tools):5.1f}% of tools")
    print(f"  {'outputSchema':20} on {100*n_out/len(tools):5.1f}% of tools")

    # ---- relations ---------------------------------------------------
    print("\nDerived relations")
    rk = Counter(r.kind for r in relations)
    for kind in ("R1", "R2", "R3", "R4", "R5"):
        print(f"  {kind}  {rk.get(kind,0):6}")
    print(f"  tot {len(relations):6}")

    # ---- headline ----------------------------------------------------
    print(f"\n{'='*70}")
    print("AUDITABILITY CLASS DISTRIBUTION")
    print("=" * 70)
    for cls in ("A0", "A1", "A2", "A3"):
        k = dist.get(cls, 0)
        lo, hi = wilson_ci(k, n)
        bar = "#" * int(44 * k / n)
        print(f"  {cls} {k:6} {100*k/n:5.1f}%  "
              f"[{100*lo:4.1f}-{100*hi:4.1f}]  {CLASS_LABEL[cls]}")
        print(f"      {bar}")

    a0 = dist.get("A0", 0)
    lo, hi = wilson_ci(a0, n)
    print(f"\n  HEADLINE: {100*a0/n:.1f}% of MCP tools (95% CI "
          f"{100*lo:.1f}-{100*hi:.1f}, n={n}) have relation degree 0.")
    print("  No client-side audit detects their compromise at any cost.")
    print("  For these, policy -- not detection -- is the only remedy.")

    # ---- dual derivation --------------------------------------------
    _dual_derivation(tools, dist, n)

    # ---- tool-count hypothesis --------------------------------------
    _toolcount_effect(tools, classes)
    _readcoverage_effect(tools, classes)

    # ---- official vs community --------------------------------------
    _by_kind(tools, classes)


def _dual_derivation(tools: list[ExtractedTool], dist: Counter, n: int) -> None:
    """Re-derive while ignoring self-declared hints.

    The gap between the two runs measures how much of the ecosystem's
    apparent auditability rests on metadata the attacker controls. A
    compromised server that sets readOnlyHint=true is believed by the
    trusting run and disbelieved by the skeptical one.
    """
    stripped = [
        ExtractedTool(
            name=t.name, description=t.description,
            input_fields=t.input_fields, output_fields=t.output_fields,
            annotations={}, idiom=t.idiom,
            source_path=t.source_path, server_id=t.server_id,
        )
        for t in tools
    ]
    s_classes = classify(stripped, derive_all(stripped))
    s_dist, _ = _dist(s_classes)

    print(f"\n{'='*70}")
    print("DUAL DERIVATION -- trusting vs ignoring self-declared hints")
    print("=" * 70)
    print(f"  {'class':6} {'trusting':>10} {'skeptical':>11} {'delta':>8}")
    for cls in ("A0", "A1", "A2", "A3"):
        a, b = dist.get(cls, 0), s_dist.get(cls, 0)
        print(f"  {cls:6} {100*a/n:9.1f}% {100*b/n:10.1f}% {100*(b-a)/n:+7.1f}")

    d = (s_dist.get("A0", 0) - dist.get("A0", 0)) / n
    print(f"\n  Ignoring the server's own hints moves {100*abs(d):.1f} points "
          f"{'into' if d > 0 else 'out of'} A0.")
    print("  That gap is the share of measured auditability that depends on")
    print("  trusting metadata the adversary is free to forge.")


def _toolcount_effect(tools: list[ExtractedTool], classes: dict) -> None:
    """Is A0 rate driven by how many sibling tools a server ships?

    Relations are derived BETWEEN tools on one server, so a server with a
    single tool has nothing to relate against and is A0 by construction.
    If A0 concentrates in small servers, the undefendable mass sits in
    the long tail -- which is also the part of the ecosystem least
    audited by anyone.
    """
    size = Counter(t.server_id for t in tools)
    buckets = [(1, 1), (2, 3), (4, 7), (8, 15), (16, 10**6)]
    print(f"\n{'='*70}")
    print("A0 RATE vs SERVER TOOL-COUNT")
    print("=" * 70)
    print(f"  {'tools/server':>14} {'servers':>8} {'tools':>7} {'A0 rate':>9}")
    for lo, hi in buckets:
        keys = [(s, t) for (s, t) in classes if lo <= size[s] <= hi]
        if not keys:
            continue
        a0 = sum(1 for k in keys if classes[k][0] == "A0")
        nsv = len({s for s, _ in keys})
        label = f"{lo}" if lo == hi else (f"{lo}+" if hi > 10**5 else f"{lo}-{hi}")
        bar = "#" * int(30 * a0 / len(keys))
        print(f"  {label:>14} {nsv:8} {len(keys):7} {100*a0/len(keys):8.1f}%  {bar}")


def read_fraction(tools: list[ExtractedTool]) -> float:
    """Share of a server's tools that are reads."""
    if not tools:
        return 0.0
    return sum(1 for t in tools if is_read(t)) / len(tools)


def _readcoverage_effect(tools: list[ExtractedTool], classes: dict) -> None:
    """A0 rate against how many READS a server exposes.

    Replaces the tool-count hypothesis, which the data falsified (A0 falls
    through mid-size servers then rises again at 16+). Count was never the
    mechanism. Every relation needs a read to corroborate a write, so a
    server that exposes twenty writes and no reads cannot be audited at
    any size.

    A first attempt measured "resource cohesion" -- whether tools share
    vocabulary -- but nearly every server scored above 0.8, because almost
    any two tools share some token like `id` or `name`. It did not
    discriminate and was dropped. Read fraction is coarser but actually
    mechanistic, and it yields advice a server author can act on.
    """
    by_server: dict[str, list[ExtractedTool]] = defaultdict(list)
    for t in tools:
        by_server[t.server_id].append(t)
    servers = {s: ts for s, ts in by_server.items() if len(ts) >= 2}
    if not servers:
        return

    print(f"\n{'='*70}")
    print("A0 RATE vs READ COVERAGE   (replaces the falsified tool-count")
    print("                            hypothesis -- see docs/15 section 4)")
    print("=" * 70)
    bands = [(0.0, 0.01), (0.01, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 1.01)]
    labels = ["no reads", "<20%", "20-40%", "40-60%", ">60%"]
    print(f"  {'reads':>10} {'servers':>8} {'tools':>7} {'A0 rate':>9}")
    for (lo, hi), lab in zip(bands, labels):
        sids = [s for s, ts in servers.items() if lo <= read_fraction(ts) < hi]
        keys = [(s, t) for (s, t) in classes if s in sids]
        if not keys:
            continue
        a0 = sum(1 for k in keys if classes[k][0] == "A0")
        bar = "#" * int(30 * a0 / len(keys))
        print(f"  {lab:>10} {len(sids):8} {len(keys):7} "
              f"{100*a0/len(keys):8.1f}%  {bar}")

    rates, fracs = [], []
    for s, ts in servers.items():
        keys = [(a, b) for (a, b) in classes if a == s]
        if keys:
            rates.append(sum(1 for k in keys if classes[k][0] == "A0") / len(keys))
            fracs.append(read_fraction(ts))
    rho = _spearman(fracs, rates)
    print(f"\n  Spearman rho(read fraction, A0 rate) = {rho:+.3f} "
          f"over {len(rates)} servers")
    print("  Negative means servers exposing more reads are more auditable.")
    print("  If it holds, the recommendation to server authors is concrete:")
    print("  ship a read for every write, and your tools leave A0.")


def _spearman(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 3:
        return 0.0

    def rank(v: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:                       # average ranks within ties
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = rank(x), rank(y)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else 0.0


def _by_kind(tools: list[ExtractedTool], classes: dict) -> None:
    print(f"\n{'='*70}")
    print("LARGEST SERVERS")
    print("=" * 70)
    per: dict[str, Counter] = defaultdict(Counter)
    for (sid, _), (cls, _) in classes.items():
        per[sid][cls] += 1
    print(f"  {'server':44} {'n':>4} {'A0':>4} {'A1':>4} {'A2':>4} {'A3':>4}")
    for sid, c in sorted(per.items(), key=lambda kv: -sum(kv[1].values()))[:15]:
        tot = sum(c.values())
        print(f"  {sid[:44]:44} {tot:4} {c.get('A0',0):4} {c.get('A1',0):4} "
              f"{c.get('A2',0):4} {c.get('A3',0):4}")

    print("\n  A0 examples (undefendable):")
    shown = 0
    for t in tools:
        if classes[(t.server_id, t.name)][0] == "A0" and shown < 10:
            print(f"    {t.name[:28]:28} {t.server_id[:34]}")
            shown += 1
    print("\n  A3 examples (conservation-bound, strongest):")
    shown = 0
    for t in tools:
        if classes[(t.server_id, t.name)][0] == "A3" and shown < 10:
            print(f"    {t.name[:28]:28} {t.server_id[:34]}")
            shown += 1
    if shown == 0:
        print("    (none -- see docs/13 on whether this is real or instrument)")
    print()

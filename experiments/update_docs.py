"""
Regenerate the numbers inside the findings docs from the current corpus.

Documentation that is hand-copied from terminal output drifts, and a stale
number in a findings document is worse than no number -- it looks
authoritative. So every figure that comes from the corpus lives inside a
marked block and is rewritten from the data:

    <!-- AUTO:name -->
    ...generated, do not edit by hand...
    <!-- /AUTO:name -->

Prose outside those markers is hand-written and never touched.

    python experiments/update_docs.py
    python experiments/update_docs.py --check     # CI: fail if stale
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from measure.classify import (  # noqa: E402
    annotation_coverage,
    classify,
    derive_all,
    wilson_ci,
)
from measure.harvest import load_corpus  # noqa: E402
from measure.report import read_fraction  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "processed" / "d1_corpus.jsonl"
DOCS = ROOT / "docs"

OFFICIAL_PREFIX = "modelcontextprotocol/"


# --- block builders ------------------------------------------------------

def b_headline(tools, classes) -> str:
    dist = Counter(c for c, _ in classes.values())
    n = len(classes)
    servers = len({t.server_id for t in tools})
    a0 = dist.get("A0", 0)
    lo, hi = wilson_ci(a0, n)

    rows = ["| Class | n | % | 95% CI |", "|---|---|---|---|"]
    names = {"A0": "**A0** unrelatable", "A1": "A1 self-relatable",
             "A2": "A2 read-backable", "A3": "A3 invariant-bound"}
    for c in ("A0", "A1", "A2", "A3"):
        k = dist.get(c, 0)
        clo, chi = wilson_ci(k, n)
        pct = f"**{100*k/n:.1f}%**" if c in ("A0", "A3") else f"{100*k/n:.1f}%"
        rows.append(f"| {names[c]} | {k:,} | {pct} | {100*clo:.1f}–{100*chi:.1f} |")

    return (
        f"**{100*a0/n:.1f}% of MCP tools have relation degree 0** "
        f"(95% CI {100*lo:.1f}–{100*hi:.1f}, n={n:,} tools across "
        f"{servers} servers).\n\n"
        "No client-side audit detects their compromise at any cost. Not with a "
        "bigger budget, not with a smarter checker — Theorem 1 applies and there "
        "is no relation to check. For these tools the remedy is policy: restrict "
        "the call, or put a human in front of it.\n\n"
        + "\n".join(rows)
    )


def b_official_vs_community(tools, classes) -> str:
    off = [t for t in tools if t.server_id.startswith(OFFICIAL_PREFIX)]
    com = [t for t in tools if not t.server_id.startswith(OFFICIAL_PREFIX)]
    if not off or not com:
        return ("*(This corpus contains no official reference servers; run "
                "`run_harvest.py` for the official control arm.)*")

    def a0_rate(ts):
        keys = [(t.server_id, t.name) for t in ts]
        keys = [k for k in keys if k in classes]
        return 100 * sum(1 for k in keys if classes[k][0] == "A0") / max(len(keys), 1)

    ca, cb = annotation_coverage(off), annotation_coverage(com)

    def pct(x):
        return f"{100*x:.1f}%"

    def outs(ts):
        return 100 * sum(1 for t in ts if t.output_fields) / max(len(ts), 1)

    return (
        f"| | Official reference (n={len(off):,}) | Community (n={len(com):,}) |\n"
        "|---|---|---|\n"
        f"| **A0 rate** | {a0_rate(off):.1f}% | **{a0_rate(com):.1f}%** |\n"
        f"| `readOnlyHint` declared | {pct(ca['readOnlyHint'])} | "
        f"**{pct(cb['readOnlyHint'])}** |\n"
        f"| `destructiveHint` declared | {pct(ca['destructiveHint'])} | "
        f"{pct(cb['destructiveHint'])} |\n"
        f"| `idempotentHint` declared | {pct(ca['idempotentHint'])} | "
        f"{pct(cb['idempotentHint'])} |\n"
        f"| `outputSchema` present | {outs(off):.1f}% | **{outs(com):.1f}%** |"
    )


def b_relations(tools) -> str:
    rk = Counter(r.kind for r in derive_all(tools))
    names = {"R1": "write-read consistency", "R2": "conservation",
             "R3": "determinism", "R4": "null-op", "R5": "canary"}
    rows = ["| Relation | n | |", "|---|---|---|"]
    for k in ("R1", "R2", "R3", "R4", "R5"):
        rows.append(f"| **{k}** | {rk.get(k,0):,} | {names[k]} |")
    return "\n".join(rows)


def b_read_coverage(tools, classes) -> str:
    by_server = defaultdict(list)
    for t in tools:
        by_server[t.server_id].append(t)
    servers = {s: ts for s, ts in by_server.items() if len(ts) >= 2}

    bands = [(0.0, 0.01, "**none**"), (0.01, 0.2, "<20%"), (0.2, 0.4, "20–40%"),
             (0.4, 0.6, "40–60%"), (0.6, 1.01, ">60%")]
    rows = ["| reads / tools | servers | tools | A0 rate |", "|---|---|---|---|"]
    best = (None, 101.0)
    for lo, hi, lab in bands:
        sids = [s for s, ts in servers.items() if lo <= read_fraction(ts) < hi]
        keys = [(s, t) for (s, t) in classes if s in sids]
        if not keys:
            continue
        rate = 100 * sum(1 for k in keys if classes[k][0] == "A0") / len(keys)
        if rate < best[1]:
            best = (lab, rate)
        mark = " ← minimum" if False else ""
        rows.append(f"| {lab} | {len(sids)} | {len(keys):,} | "
                    f"{'**' if lo == 0.0 else ''}{rate:.1f}%"
                    f"{'**' if lo == 0.0 else ''}{mark} |")
    rows.append("")
    rows.append(f"Lowest A0 rate is in the **{best[0]}** band "
                f"({best[1]:.1f}%) — the relationship is U-shaped, not "
                "monotonic, because a read also needs a write to corroborate it.")
    return "\n".join(rows)


def b_toolcount(tools, classes) -> str:
    size = Counter(t.server_id for t in tools)
    buckets = [(1, 1, "1"), (2, 3, "2–3"), (4, 7, "4–7"),
               (8, 15, "8–15"), (16, 10**6, "**16+**")]
    rows = ["| tools/server | servers | tools | A0 rate |", "|---|---|---|---|"]
    for lo, hi, lab in buckets:
        keys = [(s, t) for (s, t) in classes if lo <= size[s] <= hi]
        if not keys:
            continue
        rate = 100 * sum(1 for k in keys if classes[k][0] == "A0") / len(keys)
        rows.append(f"| {lab} | {len({s for s,_ in keys})} | {len(keys):,} | "
                    f"{rate:.1f}% |")
    return "\n".join(rows)


def b_idioms(tools) -> str:
    c = Counter(t.idiom for t in tools)
    rows = ["| Idiom | n | % |", "|---|---|---|"]
    for idiom, k in c.most_common():
        rows.append(f"| `{idiom}` | {k:,} | {100*k/len(tools):.1f}% |")
    return "\n".join(rows)


def b_schema_coverage(tools) -> str:
    n = len(tools)
    ni = sum(1 for t in tools if t.input_fields)
    no = sum(1 for t in tools if t.output_fields)
    cov = annotation_coverage(tools)
    rows = ["| Field | present on |", "|---|---|",
            f"| `inputSchema` | {100*ni/n:.1f}% |",
            f"| `outputSchema` | **{100*no/n:.1f}%** |"]
    for k, v in cov.items():
        rows.append(f"| `{k}` | {100*v:.1f}% |")
    return "\n".join(rows)


def b_corpus_line(tools, classes) -> str:
    servers = len({t.server_id for t in tools})
    dist = Counter(c for c, _ in classes.values())
    n = len(classes)
    return (f"**n = {n:,} tools across {servers} servers.** "
            f"A0 {100*dist.get('A0',0)/n:.1f}% · "
            f"A1 {100*dist.get('A1',0)/n:.1f}% · "
            f"A2 {100*dist.get('A2',0)/n:.1f}% · "
            f"A3 {100*dist.get('A3',0)/n:.1f}%. "
            f"Regenerated {date.today().isoformat()} by "
            "`python experiments/update_docs.py`.")


BUILDERS = {
    "headline": lambda t, c: b_headline(t, c),
    "official-vs-community": lambda t, c: b_official_vs_community(t, c),
    "relations": lambda t, c: b_relations(t),
    "read-coverage": lambda t, c: b_read_coverage(t, c),
    "toolcount": lambda t, c: b_toolcount(t, c),
    "idioms": lambda t, c: b_idioms(t),
    "schema-coverage": lambda t, c: b_schema_coverage(t),
    "corpus-line": lambda t, c: b_corpus_line(t, c),
}


# --- rewriting -----------------------------------------------------------

def rewrite(text: str, tools, classes) -> tuple[str, list[str]]:
    changed: list[str] = []

    def sub(m: re.Match) -> str:
        name = m.group("name")
        builder = BUILDERS.get(name)
        if builder is None:
            print(f"  warning: no builder for AUTO:{name}")
            return m.group(0)
        body = builder(tools, classes)
        new = (f"<!-- AUTO:{name} -->\n{body}\n<!-- /AUTO:{name} -->")
        if new.strip() != m.group(0).strip():
            changed.append(name)
        return new

    pattern = re.compile(
        r"<!-- AUTO:(?P<name>[\w-]+) -->.*?<!-- /AUTO:(?P=name) -->",
        re.DOTALL,
    )
    return pattern.sub(sub, text), changed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=CORPUS)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any doc is stale; changes nothing")
    args = ap.parse_args()

    if not args.corpus.exists():
        print(f"no corpus at {args.corpus} -- run experiments/run_d1.py first")
        raise SystemExit(1)

    tools = load_corpus(args.corpus)
    classes = classify(tools, derive_all(tools))
    print(f"corpus: {len(tools):,} tools / "
          f"{len({t.server_id for t in tools})} servers\n")

    stale = False
    for path in sorted(DOCS.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if "<!-- AUTO:" not in text:
            continue
        new, changed = rewrite(text, tools, classes)
        if changed:
            stale = True
            if args.check:
                print(f"  STALE {path.name}: {', '.join(changed)}")
            else:
                path.write_text(new, encoding="utf-8")
                print(f"  updated {path.name}: {', '.join(changed)}")
        else:
            print(f"  current {path.name}")

    if args.check and stale:
        print("\ndocs are stale -- run: python experiments/update_docs.py")
        raise SystemExit(1)
    print("\ndone" if not args.check else "\nall docs current")


if __name__ == "__main__":
    main()

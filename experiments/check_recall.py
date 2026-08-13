"""
Measure extractor recall against real server code.

The fixtures give 100% recall, but fixtures are written by the same person
who wrote the extractor and prove almost nothing. This samples real files
from the D1 corpus and compares full extraction against a deliberately
PERMISSIVE independent counter -- one that only looks for the bare
registration marker and ignores schemas, descriptions, and structure.

The comparison is not fully independent (both look for registration
syntax), so treat it as a LOWER bound on missed declarations rather than a
true recall figure. What it reliably catches is the failure mode that
actually bit us twice: a declaration that is plainly present in the source
but that full extraction drops because some structural assumption broke.

    python experiments/check_recall.py --n 60
"""

from __future__ import annotations

import argparse
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from measure.extract import extract  # noqa: E402
from measure.harvest import Repo, fetch_raw, get_token, load_corpus  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# Permissive markers: the minimum syntax that says "a tool is declared here".
MARKERS = {
    ".py": [
        re.compile(r"@\w+\.tool\s*\("),
        re.compile(r"@tool\s*\("),
        re.compile(r"\bTool\s*\(\s*\n?\s*name\s*="),
    ],
    ".ts": [
        re.compile(r"\.registerTool\s*\(\s*['\"`]"),
        re.compile(r"\.tool\s*\(\s*['\"`]"),
        re.compile(r"name\s*:\s*['\"`][\w\-]+['\"`]\s*,\s*description\s*:"),
    ],
}
MARKERS[".js"] = MARKERS[".mjs"] = MARKERS[".ts"]


def marker_count(source: str, path: str) -> int:
    ext = "." + path.rsplit(".", 1)[-1].lower()
    pats = MARKERS.get(ext, [])
    return max((len(p.findall(source)) for p in pats), default=0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path,
                    default=ROOT / "data" / "processed" / "d1_corpus.jsonl")
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()

    tools = load_corpus(args.corpus)
    # One entry per (server, file) that produced at least one tool.
    files: dict[tuple[str, str], str] = {}
    for t in tools:
        if t.source_path:
            files[(t.server_id, t.source_path)] = t.idiom

    rng = random.Random(args.seed)
    sample = rng.sample(sorted(files), min(args.n, len(files)))
    token = get_token()

    per_idiom: dict[str, list[tuple[int, int]]] = defaultdict(list)
    misses: list[tuple[str, str, int, int]] = []

    print(f"checking {len(sample)} real files...\n")
    for sid, path in sample:
        owner_repo = "/".join(sid.split("/")[:2])
        owner, _, name = owner_repo.partition("/")
        src = fetch_raw(Repo(owner, name, "main"), path)
        if not src:
            continue

        found = len(extract(src, path, server_id=sid))
        markers = marker_count(src, path)
        if markers == 0:
            continue

        ext = "." + path.rsplit(".", 1)[-1].lower()
        per_idiom[ext].append((found, markers))
        if found < markers:
            misses.append((sid, path, found, markers))

    print(f"{'ext':>6} {'files':>6} {'extracted':>10} {'markers':>8} {'recall':>8}")
    tot_f = tot_m = 0
    for ext, rows in sorted(per_idiom.items()):
        f = sum(a for a, _ in rows)
        m = sum(b for _, b in rows)
        tot_f, tot_m = tot_f + f, tot_m + m
        print(f"{ext:>6} {len(rows):6} {f:10} {m:8} "
              f"{100*min(f/m,1.0) if m else 0:7.1f}%")
    if tot_m:
        print(f"{'ALL':>6} {sum(len(v) for v in per_idiom.values()):6} "
              f"{tot_f:10} {tot_m:8} {100*min(tot_f/tot_m,1.0):7.1f}%")

    if misses:
        print(f"\nfiles where extraction found FEWER than the permissive count "
              f"({len(misses)}):")
        for sid, path, f, m in sorted(misses, key=lambda r: r[2] - r[3])[:15]:
            print(f"  -{m-f:<3} {f:>3}/{m:<3}  {sid.split('/')[-1][:22]:22} {path[-40:]}")
        print("\nEach is a declaration visible in the source that full")
        print("extraction dropped. Inspect before trusting the headline.")
    else:
        print("\nno file extracted fewer tools than the permissive count")

    print("\nNOTE: both counters look for registration syntax, so this is a")
    print("LOWER bound on missed declarations, not a true recall figure.")
    print("A declaration written in a form neither recognises is invisible")
    print("to both and cannot be counted here.")


if __name__ == "__main__":
    main()

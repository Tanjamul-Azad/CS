"""
Draw a stratified sample from the D1 corpus for human labeling.

Stratified by server tool-count, because A0 is expected to concentrate in
small servers and a naive random sample would be dominated by a handful
of large ones. See docs/14-labeling-codebook.md.

    python experiments/make_label_sample.py --n 300
"""

from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from measure.harvest import load_corpus  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BUCKETS = [(1, 1), (2, 3), (4, 7), (8, 15), (16, 10**6)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path,
                    default=ROOT / "data" / "processed" / "d1_corpus.jsonl")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--out", type=Path,
                    default=ROOT / "data" / "processed" / "label_sheet.tsv")
    args = ap.parse_args()

    tools = load_corpus(args.corpus)
    by_server = defaultdict(list)
    for t in tools:
        by_server[t.server_id].append(t)

    strata = defaultdict(list)
    for sid, ts in by_server.items():
        for lo, hi in BUCKETS:
            if lo <= len(ts) <= hi:
                strata[(lo, hi)].append(sid)
                break

    rng = random.Random(args.seed)
    per = max(args.n // max(len(strata), 1), 1)
    picked = []
    for bucket, sids in sorted(strata.items()):
        pool = [t for s in sids for t in by_server[s]]
        rng.shuffle(pool)
        take = pool[:per]
        picked.extend(take)
        print(f"  bucket {bucket[0]}-{bucket[1]}: {len(sids)} servers, "
              f"{len(pool)} tools -> sampled {len(take)}")

    rng.shuffle(picked)
    picked = picked[:args.n]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as f:
        f.write("server_id\ttool\tdescription\tinput_fields\tsiblings\t"
                "label\tcheck\thint_conflict\n")
        for t in picked:
            sibs = ", ".join(x.name for x in by_server[t.server_id]
                             if x.name != t.name)[:200]
            desc = (t.description or "").replace("\t", " ").replace("\n", " ")[:180]
            fields = ",".join(t.input_fields)[:80]
            f.write(f"{t.server_id}\t{t.name}\t{desc}\t{fields}\t{sibs}\t\t\t\n")

    print(f"\nwrote {len(picked)} rows -> {args.out}")
    print("Two annotators fill `label`, `check`, `hint_conflict` INDEPENDENTLY.")
    print("Then: python experiments/score_labels.py --a a.tsv --b b.tsv")


if __name__ == "__main__":
    main()

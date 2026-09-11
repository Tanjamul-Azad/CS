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
import json

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
            # Round 2 format (docs/14): name alone let Round 1 annotators
            # infer a plausible-sounding check from vocabulary rather than
            # from a demonstrated relation, and that was the cause of 40 of
            # 44 disagreements. Each sibling now carries its own
            # (truncated) description, so a judgment can be grounded in
            # what that tool actually claims to do.
            sib_entries = []
            for x in by_server[t.server_id]:
                if x.name == t.name:
                    continue
                sd = (x.description or "").replace("\t", " ").replace("\n", " ").strip()
                sd = sd[:100] if sd else "(no usable description)"
                sib_entries.append(f"{x.name}: {sd}")
            sibs = " | ".join(sib_entries)[:600]
            desc = (t.description or "").replace("\t", " ").replace("\n", " ")[:180]
            fields = ",".join(t.input_fields)[:80]
            f.write(f"{t.server_id}\t{t.name}\t{desc}\t{fields}\t{sibs}\t\t\t\n")

    # Archive the exact records sampled -- everything classify() needs
    # (output_fields, annotations), not the truncated display fields
    # written above. Without this, classifier-vs-human validation is
    # orphaned the moment the live corpus is regenerated: d1_corpus.jsonl
    # comes from a GitHub harvest that changes over time, so "the same
    # server_id" on a later date is not guaranteed to contain the same
    # tools, or to exist at all. This is what went wrong with the Round 1
    # sample -- see docs/28.
    archive = args.out.with_suffix(".corpus_archive.jsonl")
    with archive.open("w", encoding="utf-8") as f:
        for t in picked:
            f.write(json.dumps({
                "name": t.name, "server_id": t.server_id,
                "description": t.description,
                "input_fields": t.input_fields,
                "output_fields": t.output_fields,
                "annotations": t.annotations,
            }) + "\n")

    print(f"\nwrote {len(picked)} rows -> {args.out}")
    print(f"wrote the matching corpus archive -> {archive}")
    print("Two annotators fill `label`, `check`, `hint_conflict` INDEPENDENTLY.")
    print("Then: python experiments/score_labels.py --a a.tsv --b b.tsv")


if __name__ == "__main__":
    main()

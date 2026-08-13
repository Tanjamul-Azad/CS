"""
Score two annotators against each other and against the classifier.

    python experiments/score_labels.py --a a.tsv --b b.tsv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from measure.agreement import (  # noqa: E402
    cohens_kappa,
    interpret_kappa,
    print_validation,
)
from measure.classify import classify, derive_all  # noqa: E402
from measure.harvest import load_corpus  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def read_sheet(p: Path) -> dict[tuple[str, str], str]:
    out = {}
    with p.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            lab = (row.get("label") or "").strip().upper()
            if lab in ("A0", "A1", "A2", "A3"):
                out[(row["server_id"], row["tool"])] = lab
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", type=Path, required=True)
    ap.add_argument("--b", type=Path)
    ap.add_argument("--corpus", type=Path,
                    default=ROOT / "data" / "processed" / "d1_corpus.jsonl")
    args = ap.parse_args()

    A = read_sheet(args.a)
    if not A:
        print("no labels found in", args.a)
        return

    gold = A
    if args.b:
        B = read_sheet(args.b)
        shared = sorted(set(A) & set(B))
        if not shared:
            print("annotators share no labeled rows")
            return
        la, lb = [A[k] for k in shared], [B[k] for k in shared]
        k = cohens_kappa(la, lb)
        agree = sum(1 for x, y in zip(la, lb) if x == y) / len(shared)
        print(f"\n{'='*64}\nINTER-ANNOTATOR AGREEMENT\n{'='*64}")
        print(f"  n={len(shared)}  raw agreement={100*agree:.1f}%")
        print(f"  Cohen's kappa = {k:.3f}  ({interpret_kappa(k)})")
        if k < 0.60:
            print("  BELOW 0.60 -- the codebook is underspecified. Revise")
            print("  docs/14 and re-label; do not argue individual cases.")
        # Gold standard = rows the annotators agree on.
        gold = {kk: A[kk] for kk in shared if A[kk] == B[kk]}
        print(f"  gold standard: {len(gold)} agreed rows")

    tools = load_corpus(args.corpus)
    pred_map = classify(tools, derive_all(tools))
    keys = [k for k in gold if k in pred_map]
    if not keys:
        print("\nno overlap between labels and corpus -- is --corpus right?")
        return
    print_validation([gold[k] for k in keys],
                     [pred_map[k][0] for k in keys],
                     title="automatic classifier vs human gold")


if __name__ == "__main__":
    main()

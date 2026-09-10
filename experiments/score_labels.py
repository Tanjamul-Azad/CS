"""
Score two annotators against each other and against the classifier.

    python experiments/score_labels.py --a a.tsv --b b.tsv
"""

from __future__ import annotations

import argparse
import csv
import json
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

    # Kappa above measured whether two PEOPLE agree. It says nothing about
    # whether the CLASSIFIER is right, and that classifier's write-verb
    # list was extended after looking at corpus data (docs/19 R7). So the
    # numbers that matter are on servers it was never tuned against.
    split_path = ROOT / "data" / "processed" / "label_split.json"
    split = {}
    if split_path.exists():
        split = json.loads(split_path.read_text(encoding="utf-8")).get("split", {})

    if not split:
        print("\n  NO FROZEN SPLIT FOUND (data/processed/label_split.json).")
        print("  Reporting all rows together, which cannot separate fitted")
        print("  from held-out accuracy. Create one with:")
        print("    python experiments/prepare_label_sheets.py")
        print_validation([gold[k] for k in keys],
                         [pred_map[k][0] for k in keys],
                         title="classifier vs human gold (UNSPLIT)")
        return

    for part in ("tune", "heldout"):
        sub = [k for k in keys if split.get(k[0]) == part]
        if not sub:
            print(f"\n  no {part} rows labelled yet")
            continue
        servers = len({k[0] for k in sub})
        print_validation([gold[k] for k in sub],
                         [pred_map[k][0] for k in sub],
                         title=f"classifier vs human gold -- {part.upper()} "
                               f"({len(sub)} tools, {servers} servers)")

    print("\n  Tools are nested within servers and are not independent")
    print("  samples: several tools by one author share naming and sibling")
    print("  structure. A binomial interval over tools will be too narrow.")
    print("  Report a clustered interval. The server count above is a")
    print("  CLUSTER count, not automatically the effective sample size --")
    print("  that depends on the within-server correlation.")
    print("\n  HELD OUT means held out from LABEL fitting. The write-verb")
    print("  vocabulary was extended after inspecting the corpus and this")
    print("  split was drawn afterwards, so report it as: labels held out")
    print("  from tuning; corpus previously inspected. That is weaker than")
    print("  an untouched holdout, which needs a fresh sample of servers.")


if __name__ == "__main__":
    main()

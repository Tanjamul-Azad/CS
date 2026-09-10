"""
Prepare the human labelling sheets: prediction-hidden, split frozen.

Two properties the sheets must have, and neither is automatic:

PREDICTION-HIDDEN. An annotator who can see what the classifier said is
no longer independent of it, and the agreement number becomes a measure of
anchoring rather than of the codebook. The sheets therefore carry the tool
and its declaration and nothing else. The classifier's prediction is
written to a separate key file that annotators do not open.

SPLIT FROZEN, AND SPLIT BY SERVER. Cohen's kappa says whether two people
agree with each other; it says nothing about whether the classifier is
right. That needs precision and recall against the adjudicated labels, on
rows the classifier's vocabulary was not tuned on -- and the write-verb
list WAS extended after looking at corpus data (docs/19 R7), so a
held-out split is not optional here.

The split is by SERVER, not by tool. Tools from one server share naming
conventions, sibling structure and an author, so splitting at tool level
leaks the tune set into the held-out set and inflates held-out accuracy.
For the same reason confidence intervals must account for clustering.

The seed is fixed and recorded. Re-running reproduces the same split; the
split must not be redrawn after seeing results.

    python experiments/prepare_label_sheets.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
SHEET = PROC / "label_sheet.tsv"

ANNOTATOR_COLS = ["server_id", "tool", "description", "input_fields",
                  "siblings", "label", "check", "hint_conflict"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", type=Path, default=SHEET)
    ap.add_argument("--seed", type=int, default=20260910)
    ap.add_argument("--heldout-frac", type=float, default=0.5)
    ap.add_argument("--annotators", nargs="+", default=["A", "B"])
    args = ap.parse_args()

    if not args.sheet.exists():
        print(f"MISSING {args.sheet}\n  build it with: "
              f"python experiments/make_label_sample.py --n 300")
        sys.exit(2)

    rows = list(csv.DictReader(args.sheet.open(encoding="utf-8", newline=""),
                               delimiter="\t"))
    if not rows:
        print(f"{args.sheet} has no rows")
        sys.exit(2)

    # Refuse to overwrite work in progress.
    for name in args.annotators:
        p = PROC / f"labels_annotator_{name}.tsv"
        if p.exists():
            filled = sum(1 for r in csv.DictReader(
                p.open(encoding="utf-8", newline=""), delimiter="\t")
                if (r.get("label") or "").strip())
            if filled:
                print(f"REFUSING to overwrite {p.name}: {filled} row(s) "
                      f"already labelled.\n  Move it aside first if you "
                      f"really mean to restart.")
                sys.exit(3)

    servers = sorted({r["server_id"] for r in rows})
    rng = random.Random(args.seed)
    shuffled = servers[:]
    rng.shuffle(shuffled)
    cut = int(len(shuffled) * args.heldout_frac)
    heldout = set(shuffled[:cut])
    split = {s: ("heldout" if s in heldout else "tune") for s in servers}

    # Annotator sheets: declaration only. No prediction, no split -- the
    # split must not hint that a row is "being tested".
    for name in args.annotators:
        out = PROC / f"labels_annotator_{name}.tsv"
        with out.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=ANNOTATOR_COLS, delimiter="\t",
                               extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({**{c: "" for c in ANNOTATOR_COLS},
                            **{c: r.get(c, "") for c in ANNOTATOR_COLS
                               if c not in ("label", "check", "hint_conflict")}})
        print(f"  wrote {out.relative_to(ROOT)}   ({len(rows)} rows, unlabelled)")

    key = PROC / "label_split.json"
    payload = {
        "seed": args.seed,
        "heldout_frac": args.heldout_frac,
        "n_rows": len(rows),
        "n_servers": len(servers),
        "n_heldout_servers": len(heldout),
        "sheet_sha256": hashlib.sha256(
            args.sheet.read_bytes()).hexdigest()[:16],
        "split_by": "server_id",
        "split": split,
    }
    key.write_text(json.dumps(payload, indent=1, sort_keys=True),
                   encoding="utf-8")
    print(f"  wrote {key.relative_to(ROOT)}   "
          f"({len(servers)} servers, {len(heldout)} held out)")

    print(f"""
INSTRUCTIONS FOR ANNOTATORS

  Two people label independently. Do not discuss rows, do not compare
  sheets, and do not look at any classifier output until both are done --
  the whole point of the number is that you arrived at it separately.

  For each row put A0, A1, A2 or A3 in `label`, following
  docs/14-labeling-codebook.md. Use `check` to name the check you believe
  is possible, and `hint_conflict` if the server's own annotations
  contradict what the declaration suggests.

  If a row is genuinely undecidable from the declaration, say so in
  `check` rather than guessing. A forced guess damages the agreement
  number in a way that cannot be undone afterwards.

  When both sheets are complete:
      python experiments/score_labels.py --a data/processed/labels_annotator_A.tsv \\
                                          --b data/processed/labels_annotator_B.tsv

  Kappa below 0.60 means the codebook is underspecified. Revise docs/14
  and re-label -- do not argue individual rows into agreement.
""")


if __name__ == "__main__":
    main()

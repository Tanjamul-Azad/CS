"""
The evaluation: does MBA actually detect these attacks, and is it usable?

Runs every (domain x adversary x defense) cell and prints the paper's main
table.

    python experiments/run_eval.py
    python experiments/run_eval.py --trials 100
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcpmut.domains import compute, email, files  # noqa: E402
from mcpmut.domains.bank_stateful import (  # noqa: E402
    AdaptiveBank, FullShadowBank, HonestBank, ShadowLedgerBank,
    attacker_got_money,
)
from mcpmut.domains.base import Domain  # noqa: E402
from mcpmut.evaluate import (  # noqa: E402
    DEFENSES, evaluate_cell, false_positive_rate,
)

ROOT = Path(__file__).resolve().parents[1]

BANK_TOOLS = [
    {"name": "transfer_money",
     "description": "Transfer the specified amount to the specified recipient.",
     "inputSchema": {"type": "object", "properties": {
         "recipient": {"type": "string"}, "amount": {"type": "number"},
         "memo": {"type": "string"}}},
     "annotations": {"readOnlyHint": False, "destructiveHint": True}},
    {"name": "check_balance", "description": "Return the current account balance.",
     "inputSchema": {"type": "object", "properties": {}},
     "outputSchema": {"type": "object", "properties": {"balance": {}}},
     "annotations": {"readOnlyHint": True}},
    {"name": "list_transactions",
     "description": "List recent transactions on the account.",
     "inputSchema": {"type": "object", "properties": {}},
     "outputSchema": {"type": "object", "properties": {
         "recipient": {}, "amount": {}, "memo": {}}},
     "annotations": {"readOnlyHint": True}},
]

def _bank_noise(s):
    """A legitimate transfer made by another client of the same account."""
    s.ledger.append({"recipient": "Landlord", "amount": 50.0, "memo": "auto"})
    s.balance -= 50.0


BANKING = Domain(
    name="banking",
    tools=BANK_TOOLS,
    honest=lambda o: HonestBank(oracle=o),
    ladder=[("L1 forge response", 3, lambda o: AdaptiveBank(oracle=o)),
            ("L2 + shadow ledger", 9, lambda o: ShadowLedgerBank(oracle=o)),
            ("L3 + shadow balance", 17, lambda o: FullShadowBank(oracle=o))],
    task_tool="transfer_money",
    task_args={"recipient": "Alice", "amount": 100.0, "memo": "rent"},
    benign_calls=[("check_balance", {}), ("list_transactions", {})],
    attack_succeeded=attacker_got_money,
    noise_fn=_bank_noise,
)

DOMAINS = [BANKING, email.DOMAIN, files.DOMAIN, compute.DOMAIN]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=30)
    ap.add_argument("--fp-trials", type=int, default=200)
    ap.add_argument("--out", type=Path,
                    default=ROOT / "experiments" / "results" / "eval.json")
    args = ap.parse_args()

    cells = []
    print(f"\n{'='*78}")
    print("DETECTION  --  same effect every time; only the attacker's "
          "consistency machinery differs")
    print("=" * 78)
    print(f"  {'domain':9} {'adversary':22} {'LOC':>4} "
          + "".join(f"{d(  [] ).name:>14}" for d in DEFENSES))

    for dom in DOMAINS:
        for label, loc, make_server in dom.ladder:
            row = []
            for make_def in DEFENSES:
                c = evaluate_cell(dom, label, loc, make_server, make_def,
                                  trials=args.trials)
                cells.append(c)
                row.append(f"{100*c.dr:12.0f}%")
            print(f"  {dom.name:9} {label:22} {loc:4} " + "".join(row))
        print()

    print("=" * 78)
    print("FALSE POSITIVES  --  fully honest server; any flag is a false alarm")
    print("=" * 78)
    print("  Noise = probability of LEGITIMATE concurrent activity between")
    print("  calls (another client, a cron job, a human). A conservation")
    print("  check cannot distinguish that from an attacker's skim, so this")
    print("  is where a usable defense either survives or does not.")
    print("")
    fprs = {}
    for noise in (0.0, 0.1, 0.3, 0.5):
        print(f"  noise={noise:.0%}")
        print(f"    {'domain':9} " + "".join(f"{d([]).name:>14}" for d in DEFENSES))
        for dom in DOMAINS:
            row = []
            for make_def in DEFENSES:
                fpr = false_positive_rate(dom, make_def, trials=args.fp_trials,
                                          noise_rate=noise)
                fprs[f"{dom.name}|{make_def([]).name}|{noise}"] = fpr
                row.append(f"{100*fpr:12.1f}%")
            print(f"    {dom.name:9} " + "".join(row))
        print()

    print(f"\n{'='*78}")
    print("OVERHEAD  --  extra tool calls the defense issues per task call")
    print("=" * 78)
    for dom in DOMAINS:
        ovh = [c for c in cells if c.domain == dom.name and c.defense == "MBA"]
        if ovh:
            print(f"  {dom.name:9} MBA: {sum(c.overhead for c in ovh)/len(ovh):.2f} "
                  "extra calls per task call")

    print(f"\n{'='*78}")
    print("COST CURVE  --  MBA detection vs attacker effort, pooled")
    print("=" * 78)
    for loc in (3, 9, 17):
        rows = [c for c in cells if c.defense == "MBA" and c.loc == loc]
        if not rows:
            continue
        det = sum(c.detections for c in rows)
        att = sum(c.attacks for c in rows)
        bar = "#" * int(30 * det / max(att, 1))
        print(f"  {loc:3} LOC   detected {det:4}/{att:<4} "
              f"({100*det/max(att,1):5.1f}%)  {bar}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps([{
        "domain": c.domain, "adversary": c.adversary, "loc": c.loc,
        "defense": c.defense, "trials": c.trials, "attacks": c.attacks,
        "detections": c.detections, "asr": c.asr, "dr": c.dr,
        "overhead": c.overhead,
    } for c in cells] + [{"fpr": fprs}],
        indent=1), encoding="utf-8")
    print(f"\nwrote {args.out.relative_to(ROOT)}\n")


if __name__ == "__main__":
    main()

"""
E-BASE / E-ENUM -- what operating points does the auditor actually offer?

The finding this exists to quantify (docs/24): before the enumeration
check, the detector had exactly two settings on real servers, and neither
was usable --

    count only VIOLATION   0/205 detected   at  1.8% false-positive rate
    count WARNING too      5/205 detected   at 76.5% false-positive rate

The 5 were real catches that the false-positive control discarded. This
script recomputes both operating points from any pilot run, so a change to
the auditor can be scored as a movement in (detection, FPR) space rather
than as a single number that hides the tradeoff.

Definitions, chosen so a "detection" cannot be an artifact:

  landed     the tampering proxy reports it actually diverted something.
             Trials where no attack occurred are excluded -- an
             unconditioned rate silently mixes them in and was how an
             earlier run reported 57.6% detection that did not exist.

  detection  the attack landed AND the tampered trial fired AND the
             honest trial on the same server stayed silent. The honest
             cross-check is what turns an apparent catch into a real one.

  FPR        the honest trial fired at all. Measured over every usable
             server, not just those where an attack landed.

    python experiments/analyze_operating_points.py                    # latest
    python experiments/analyze_operating_points.py --compare BASE.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "data" / "processed" / "pilot_r7.json"


def _load(p: Path) -> list[dict]:
    return [r for r in json.loads(p.read_text(encoding="utf-8"))
            if r.get("status") == "ok"]


def _honest(r: dict) -> list[str]:
    return r.get("honest", {}).get("alerts", []) or []


def _tampered(r: dict) -> dict:
    t = r.get("tampered", {})
    return t.get("L1", t) if isinstance(t, dict) else {}


def _fired(alerts: list[str], permissive: bool) -> bool:
    sev = ("[VIOLATION]", "[WARNING]") if permissive else ("[VIOLATION]",)
    return any(a.startswith(s) for a in alerts for s in sev)


def operating_point(rows: list[dict], permissive: bool) -> dict:
    landed = [r for r in rows if _tampered(r).get("attack_landed")]
    tp = [r for r in landed
          if _fired(_tampered(r).get("alerts", []), permissive)
          and not _fired(_honest(r), permissive)]
    fp = [r for r in rows if _fired(_honest(r), permissive)]
    return {
        "landed": len(landed), "usable": len(rows),
        "tp": len(tp), "fp": len(fp),
        "detection": len(tp) / len(landed) if landed else 0.0,
        "fpr": len(fp) / len(rows) if rows else 0.0,
        "tp_ids": [r["server_id"] for r in tp],
    }


def relation_mix(rows: list[dict]) -> Counter:
    """Which relation raised each violation -- R1 read-back vs R7
    enumeration. The point of the enumeration work is that R7 should
    carry detections R1 structurally cannot."""
    c: Counter = Counter()
    for r in rows:
        for a in _tampered(r).get("alerts", []):
            if a.startswith("[VIOLATION]"):
                c[a.split("/")[1].split(":")[0].strip() if "/" in a else "?"] += 1
    return c


def report(rows: list[dict], label: str) -> dict:
    print(f"\n{'=' * 72}\n{label}   (n={len(rows)} usable servers)\n{'=' * 72}")
    out = {}
    for permissive, name in ((False, "strict   (VIOLATION only)"),
                             (True, "permissive (+ WARNING)")):
        op = operating_point(rows, permissive)
        out["permissive" if permissive else "strict"] = op
        print(f"\n  {name}")
        print(f"    attacks landed        {op['landed']:>5}")
        print(f"    true detections       {op['tp']:>5}   "
              f"= {100 * op['detection']:.1f}% of landed")
        print(f"    false positives       {op['fp']:>5}   "
              f"= {100 * op['fpr']:.1f}% FPR")
    mix = relation_mix(rows)
    if mix:
        print("\n  violations by relation")
        for k, v in mix.most_common():
            print(f"    {k:<10} {v:>5}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, default=DEFAULT)
    ap.add_argument("--compare", type=Path, default=None,
                    help="baseline run to diff against (same servers)")
    args = ap.parse_args()

    rows = _load(args.run)
    cur = report(rows, f"CURRENT  {args.run.name}")

    if args.compare and args.compare.exists():
        base_rows = _load(args.compare)
        base = report(base_rows, f"BASELINE {args.compare.name}")

        print(f"\n{'=' * 72}\nMOVEMENT IN (detection, FPR) SPACE\n{'=' * 72}")
        print(f"\n  {'point':<14}{'detection':>22}{'FPR':>20}")
        for k in ("strict", "permissive"):
            b, c = base[k], cur[k]
            print(f"  {k:<14}"
                  f"{100*b['detection']:>9.1f}% -> {100*c['detection']:>7.1f}%"
                  f"{100*b['fpr']:>13.1f}% -> {100*c['fpr']:>5.1f}%")

        gained = set(cur["strict"]["tp_ids"]) - set(base["strict"]["tp_ids"])
        lost = set(base["strict"]["tp_ids"]) - set(cur["strict"]["tp_ids"])
        print(f"\n  newly detected (strict): {len(gained)}")
        for s in sorted(gained):
            print(f"    + {s}")
        if lost:
            print(f"\n  no longer detected: {len(lost)}")
            for s in sorted(lost):
                print(f"    - {s}")

        print("\n  Pre-registered rule (docs/24 §10): the enumeration check")
        print("  must move strict detection up without pushing FPR above 10%.")
    print()


if __name__ == "__main__":
    main()

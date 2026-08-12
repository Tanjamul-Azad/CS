"""
Metamorphic Behavioral Auditing: the consistency-cost result.

This is the experiment that answers the objection that killed the first
design ("server-side access pawa to tough"). The auditor here needs no
server cooperation, no downstream cooperation, and no independent
channel. Every call it makes is a tool the client was already approved
to use.

What it shows
-------------
Four adversaries divert exactly the same money. They differ only in how
much machinery they maintain to keep the client's relation checks
satisfied. Detection falls as that machinery grows -- and the machinery
is countable.

  D-resp catches nobody past M4.
  MBA/R1 catches M5.        Attacker answer: keep a shadow ledger  (+6 LOC)
  MBA/R2 catches M7.        Attacker answer: fake balance too      (+8 LOC)
  Nothing catches M8 -- Theorem 1, as promised.

The headline is not that M8 wins. It is the SLOPE: each layer of defense
forces a measurable increase in attacker burden, and every publicly
documented MCP compromise to date sits at the M5 end of that curve.

Run:  python experiments/demo_mba.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcpmut.core import EffectOracle  # noqa: E402
from mcpmut.domains.bank_stateful import (  # noqa: E402
    AdaptiveBank,
    FullShadowBank,
    HonestBank,
    ShadowLedgerBank,
    attacker_got_money,
)
from mcpmut.relations import (  # noqa: E402
    ConservationRelation,
    WriteReadRelation,
    auditability_class,
    relation_degree,
)

USER_INTENT = {"recipient": "Alice", "amount": 100.0}

R1 = WriteReadRelation("transfer_money", "list_transactions", ("recipient", "amount"))
R2 = ConservationRelation("check_balance", "balance", "amount", sign=-1)


def response_validator(intent, response) -> bool:
    """D-resp: the naive defense. Blocked == True."""
    return any(intent.get(f) != response.get(f) for f in ("recipient", "amount"))


def run(bank_cls, use_r1: bool, use_r2: bool):
    oracle = EffectOracle()
    bank = bank_cls(oracle=oracle)
    call = bank.call

    detections = []

    before = R2.before(call) if use_r2 else None
    response = call("transfer_money", dict(USER_INTENT))

    if response_validator(USER_INTENT, response):
        detections.append("D-resp")

    if use_r1 and R1.check(call, USER_INTENT).violated:
        detections.append("MBA/R1")

    if use_r2:
        after = float(call("check_balance", {})["balance"])
        if R2.check_delta(before, after, USER_INTENT).violated:
            detections.append("MBA/R2")

    stolen = oracle.attack_succeeded("live", attacker_got_money)
    return stolen, detections, bank_cls.loc


def main() -> None:
    print("\nMetamorphic Behavioral Auditing -- consistency cost")
    print("No server cooperation. No independent channel. Client-side only.\n")

    variants = [
        ("Honest", HonestBank),
        ("M5  forge response", AdaptiveBank),
        ("M7  + shadow ledger", ShadowLedgerBank),
        ("M8  + shadow balance", FullShadowBank),
    ]

    hdr = f"{'Server':<24}{'Stole?':<9}{'Atk LOC':<10}{'Detected by'}"
    print(hdr)
    print("-" * 72)
    for label, cls in variants:
        stolen, det, loc = run(cls, use_r1=True, use_r2=True)
        mark = "YES" if stolen else "no"
        who = ", ".join(det) if det else "-- NOBODY --"
        print(f"{label:<24}{mark:<9}{loc:<10}{who}")

    print("\nRelation degree and auditability class")
    print("-" * 72)
    rels = [R1, R2]
    for tool in ("transfer_money", "check_balance", "list_transactions", "send_webhook"):
        deg = relation_degree(tool, rels)
        cls_ = auditability_class(tool, rels)
        note = "  <- no relation exists: undetectable at any cost" if cls_ == "A0" else ""
        print(f"  {tool:<22} deg={deg}  class={cls_}{note}")

    print("\nReading of the result")
    print("-" * 72)
    print("  Every variant steals money through an approved tool whose")
    print("  declaration never changed, so hash pinning is blind to all of")
    print("  them. What changes is the attacker's burden:")
    print("    3 LOC  -> defeats response validation, caught by R1 write-read")
    print("    9 LOC  -> shadow ledger defeats R1, caught by R2 conservation")
    print("   17 LOC  -> shadow balance defeats R2, caught by nothing")
    print("  Each defense layer does not stop the attacker -- it prices them.")
    print()
    print("  M8 wins, and Theorem 1 says it always will. That is the ceiling,")
    print("  stated honestly. The contribution is the slope below it, plus the")
    print("  fact that documented real-world MCP compromises (e.g. the Postmark")
    print("  BCC leak) are M5-class one-line patches that maintain no shadow")
    print("  state at all.")
    print()
    print("  'send_webhook' is class A0: it participates in no relation, so no")
    print("  audit policy touches it at any budget. Policy is the only remedy.")
    print()


if __name__ == "__main__":
    main()

"""
mcpaudit against the adversary ladder -- the deployable defense, end to end.

Same theft in every case. The declaration never changes, so hash pinning
is blind throughout. What changes is only how much machinery the attacker
must run to stay consistent under audit.

Run:  python experiments/demo_mcpaudit.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcpaudit import Auditor, Policy  # noqa: E402
from mcpmut.core import EffectOracle  # noqa: E402
from mcpmut.domains.bank_stateful import (  # noqa: E402
    AdaptiveBank,
    FullShadowBank,
    HonestBank,
    ShadowLedgerBank,
    attacker_got_money,
)

# Exactly what a server advertises over tools/list. Identical for every
# variant below -- honest and compromised servers are indistinguishable here.
TOOLS_LIST = [
    {
        "name": "transfer_money",
        "description": "Transfer the specified amount to the specified recipient.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "recipient": {"type": "string"},
                "amount": {"type": "number"},
                "memo": {"type": "string"},
            },
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": True},
    },
    {
        "name": "check_balance",
        "description": "Return the current account balance.",
        "inputSchema": {"type": "object", "properties": {}},
        "outputSchema": {"type": "object", "properties": {"balance": {"type": "number"}}},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "list_transactions",
        "description": "List recent transactions on the account.",
        "inputSchema": {"type": "object", "properties": {}},
        "outputSchema": {
            "type": "object",
            "properties": {"recipient": {}, "amount": {}, "memo": {}},
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "send_webhook",
        "description": "Post a payload to a configured webhook URL.",
        "inputSchema": {"type": "object", "properties": {"url": {}, "payload": {}}},
        "annotations": {"readOnlyHint": False},
    },
]

TASK = {"recipient": "Alice", "amount": 100.0, "memo": "rent"}


def run(bank_cls, label: str) -> tuple[bool, bool, int]:
    oracle = EffectOracle()
    bank = bank_cls(oracle=oracle)
    auditor = Auditor.from_mcp_tools(TOOLS_LIST, server_id="bank", policy=Policy.default())

    decision = auditor.before_call("transfer_money", TASK,
                                   call_fn=lambda n, a: bank.call(n, a))
    if decision.blocked:
        return (False, False, bank_cls.loc)

    result = bank.call("transfer_money", TASK)
    alerts = auditor.after_call("transfer_money", TASK, result,
                                call_fn=lambda n, a: bank.call(n, a))

    stolen = any(attacker_got_money(e) for e in oracle._effects)
    caught = any(a.severity == "violation" for a in alerts)

    flag = "CAUGHT" if caught else ("MISSED" if stolen else "clean")
    print(f"  {label:26} loc={bank_cls.loc:3}  stolen={str(stolen):5}  {flag}")
    for a in alerts:
        if a.severity != "info":
            print(f"      {a}")
    return (stolen, caught, bank_cls.loc)


def main() -> None:
    print("\n" + "=" * 72)
    print("mcpaudit -- zero-cooperation behavioral auditing")
    print("=" * 72)

    auditor = Auditor.from_mcp_tools(TOOLS_LIST, server_id="bank")
    cov = auditor.coverage()
    print("\nCoverage derived from the advertised tool list alone:")
    print("  " + cov.summary())

    print("\nPer-tool auditability:")
    for t in auditor.tools:
        cls, deg = auditor._cls(t.name)
        d = auditor.before_call(t.name, {})
        print(f"  {t.name:20} {cls}  degree={deg}  policy={d.action.value}")
        if d.action.value in ("confirm", "deny"):
            print(f"      -> {d.rule.reason}")

    print("\n" + "=" * 72)
    print("THE ADVERSARY LADDER  (same theft, same declaration, every time)")
    print("=" * 72)
    rows = [
        run(HonestBank, "HonestBank (baseline)"),
        run(AdaptiveBank, "M5 forge response"),
        run(ShadowLedgerBank, "M7 + shadow ledger"),
        run(FullShadowBank, "M8 + shadow balance"),
    ]

    print("\n" + "=" * 72)
    print("WHAT IT COST THE ATTACKER")
    print("=" * 72)
    print(f"  {'adversary':26} {'LOC':>4}  {'stole':>6}  {'detected':>9}")
    labels = ["honest", "M5 forge response", "M7 + shadow ledger", "M8 + shadow balance"]
    for (stolen, caught, loc), lab in zip(rows, labels):
        print(f"  {lab:26} {loc:4}  {str(stolen):>6}  {str(caught):>9}")

    print("\n  Response inspection alone stops none of these -- the response")
    print("  is honest in every compromised case (Theorem 1).")
    print("  Read-back auditing forces the attacker up the ladder. M8 wins,")
    print("  and Theorem 1 says something always will. The contribution is")
    print("  the slope below that ceiling: real-world MCP compromises are")
    print("  3-LOC-class patches that maintain no shadow state at all.")
    print("\n  Note send_webhook: A0, mutating, degree 0. No audit will ever")
    print("  check it. That is why policy, not detection, is the answer there.\n")


if __name__ == "__main__":
    main()

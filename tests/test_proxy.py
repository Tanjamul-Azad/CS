"""The declaration-driven tampering proxy.

Its whole purpose is to be an adversary the auditor did NOT see coming --
derived from declarations alone, so detection numbers on servers we did
not write mean something. These tests pin that it reproduces the
hand-written ladder's DETECTION SEMANTICS without any per-domain code, so
a result on a real third-party server sits on the same axis as the
benchmark.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

import pytest  # noqa: E402

from mcpaudit import Auditor, Policy  # noqa: E402
from mcpmut.core import EffectOracle  # noqa: E402
from mcpmut.domains.bank_stateful import HonestBank  # noqa: E402
from mcpmut.proxy import TamperingProxy, _divert_value, attack_landed  # noqa: E402
from run_eval import BANKING  # noqa: E402

WRITES = {"transfer_money"}
READS = {"check_balance", "list_transactions"}
ARGS = {"recipient": "Alice", "amount": 100.0, "memo": "rent"}


def _run(level: int):
    oracle = EffectOracle()
    bank = HonestBank(oracle=oracle)
    proxy = TamperingProxy(inner=lambda n, a: bank.call(n, a),
                           write_tools=WRITES, read_tools=READS, level=level)
    aud = Auditor.from_mcp_tools(
        BANKING.tools, server_id="s",
        policy=Policy(**{**Policy.default().__dict__, "audit_budget": 50.0}))
    cf = lambda n, a: proxy.call(n, a)  # noqa: E731
    aud.before_call("transfer_money", ARGS, call_fn=cf)
    res = proxy.call("transfer_money", ARGS)
    alerts = aud.after_call("transfer_money", ARGS, res, call_fn=cf)
    violations = [a for a in alerts if a.severity == "violation"]
    return proxy, bank, violations


def test_diverted_value_shares_no_token_with_original():
    # Otherwise a read-back would find the original inside it and pass.
    assert "Alice" not in str(_divert_value("Alice"))
    assert "report" not in str(_divert_value("/work/report.txt"))
    assert _divert_value("a@b.com") == "attacker@evil.example"


def test_L1_forge_caught_by_R1():
    proxy, bank, v = _run(1)
    assert attack_landed(proxy.plans)
    assert v and v[0].relation == "R1"


def test_L2_skim_caught_by_R2():
    proxy, bank, v = _run(2)
    assert attack_landed(proxy.plans)
    assert v and v[0].relation == "R2"


def test_L3_full_shadow_evades():
    proxy, bank, v = _run(3)
    assert attack_landed(proxy.plans)
    assert v == []                      # Theorem 1: the ceiling


def test_real_effect_lands_on_the_server_not_just_claimed():
    # Ground truth: the diversion actually happened to the real bank.
    proxy, bank, _ = _run(1)
    assert bank.ledger[-1]["recipient"] != "Alice"


def test_no_target_field_forwards_honestly():
    # A write with nothing divertible must not be fabricated.
    oracle = EffectOracle()
    calls = []
    proxy = TamperingProxy(
        inner=lambda n, a: calls.append((n, a)) or {"ok": True},
        write_tools={"ping"}, read_tools=set(), level=1)
    proxy.call("ping", {"flag": True})
    assert calls == [("ping", {"flag": True})]
    assert not attack_landed(proxy.plans)

"""Relation derivation, classification, and the deployable auditor.

The safety tests matter most: an auditor that issues writes the agent did
not request is not deployable, whatever its detection rate.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from mcpaudit import Auditor, Policy  # noqa: E402
from mcpaudit.policy import Action  # noqa: E402
from measure.agreement import classifier_report, cohens_kappa  # noqa: E402
from measure.classify import classify, derive_all, is_write  # noqa: E402
from measure.extract import ExtractedTool  # noqa: E402


def tool(name, desc="", fields=(), out=(), ann=None, server="s"):
    return ExtractedTool(name=name, description=desc, input_fields=list(fields),
                         output_fields=list(out), annotations=ann or {},
                         server_id=server)


BANK = [
    tool("transfer_money", "Transfer the specified amount to the specified recipient.",
         ["recipient", "amount", "memo"]),
    tool("check_balance", "Return the current account balance.",
         [], ["balance"]),
    tool("list_transactions", "List recent transactions on the account.",
         [], ["recipient", "amount", "memo"]),
    tool("send_webhook", "Post a payload to a configured webhook URL.",
         ["url", "payload"]),
]


# --- derivation ----------------------------------------------------------

def test_r1_from_field_overlap_not_just_nouns():
    """transfer_money <-> list_transactions share no noun.

    They are related because the read RETURNS the fields the write
    ACCEPTS. Noun matching alone misses the canonical case the whole
    method is built on.
    """
    kinds = {(r.kind, r.tools) for r in derive_all(BANK)}
    assert ("R1", ("transfer_money", "list_transactions")) in kinds


def test_r2_not_gated_behind_r1():
    """Conservation must be derived independently.

    transfer_money and check_balance share no noun and no field, yet
    balance_after == balance_before - amount is exactly the invariant
    that catches a skimming server. Gating R2 behind R1's overlap test
    deleted the strongest relation class before it could fire.
    """
    kinds = {(r.kind, r.tools) for r in derive_all(BANK)}
    assert ("R2", ("transfer_money", "check_balance")) in kinds


def test_a0_for_unrelatable_tool():
    classes = classify(BANK, derive_all(BANK))
    assert classes[("s", "send_webhook")][0] == "A0"


def test_conservation_gives_a3():
    classes = classify(BANK, derive_all(BANK))
    assert classes[("s", "transfer_money")][0] == "A3"


def test_single_tool_server_is_a0_by_construction():
    solo = [tool("fetch", "Fetch a URL.", ["url"])]
    assert classify(solo, derive_all(solo))[("s", "fetch")][0] == "A0"


def test_relations_never_cross_servers():
    """A read on another server proves nothing about this one."""
    split = [
        tool("write_note", "Write a note.", ["content"], server="a"),
        tool("list_notes", "List notes.", [], ["content"], server="b"),
    ]
    assert derive_all(split) == []


# --- write detection -----------------------------------------------------

@pytest.mark.parametrize("name", [
    "purge_sessions", "prune_tools", "approve_prompt", "export_session",
    "revoke_token", "reset_database", "deploy_stack", "charge_card",
])
def test_destructive_verbs_detected_as_writes(name):
    """Missing a write is the dangerous error -- the tool then looks
    harmless to the policy layer."""
    assert is_write(tool(name))


def test_self_declared_hint_overrides_verb():
    assert not is_write(tool("delete_thing", ann={"readOnlyHint": True}))


# --- auditor safety ------------------------------------------------------

def _auditor(**kw):
    return Auditor(BANK, **kw)


def test_auditor_never_issues_unrequested_writes():
    """The core deployability property.

    A probe write is a real write. If the auditor ever calls a mutating
    tool on its own initiative, it is unsafe to run against production
    regardless of how well it detects.
    """
    called: list[str] = []

    def call_fn(name, args):
        called.append(name)
        return {"balance": 900.0} if name == "check_balance" else []

    a = _auditor()
    a.before_call("transfer_money", {"recipient": "Alice", "amount": 100.0},
                  call_fn=call_fn)
    a.after_call("transfer_money", {"recipient": "Alice", "amount": 100.0},
                 {"status": "ok"}, call_fn=call_fn)

    assert called, "auditor should have probed something"
    writes = [n for n in called if is_write(a.by_name[n])]
    assert writes == [], f"auditor issued unrequested writes: {writes}"


def test_probe_writes_stay_off_by_default():
    a = _auditor()
    assert not a._safe_to_call("transfer_money")
    assert a._safe_to_call("check_balance")
    assert Auditor(BANK, allow_probe_writes=True)._safe_to_call("transfer_money")


def test_a0_mutation_requires_human_by_default():
    d = _auditor().before_call("send_webhook", {"url": "x", "payload": {}})
    assert d.a_class == "A0"
    assert d.action is Action.CONFIRM


def test_strict_policy_denies_unverifiable_mutation():
    d = Auditor(BANK, policy=Policy.strict()).before_call("send_webhook", {})
    assert d.action is Action.DENY and d.blocked


def test_a0_readonly_tool_is_allowed():
    """A0 means unverifiable, not dangerous. Read-only A0 still proceeds."""
    solo = [tool("fetch", "Fetch a URL.", ["url"], ann={"readOnlyHint": True})]
    assert Auditor(solo).before_call("fetch", {}).action is Action.ALLOW


def test_coverage_names_unverifiable_mutations():
    cov = _auditor().coverage()
    assert "send_webhook" in cov.unverifiable_writes
    assert cov.total == 4


def test_from_mcp_tools_reads_live_payload_shape():
    a = Auditor.from_mcp_tools([{
        "name": "send_email",
        "description": "Send an email.",
        "inputSchema": {"type": "object",
                        "properties": {"to": {}, "body": {}}},
        "annotations": {"readOnlyHint": False},
    }])
    t = a.by_name["send_email"]
    assert t.input_fields == ["to", "body"]
    assert t.annotations["readOnlyHint"] is False


# --- detection -----------------------------------------------------------

def test_conservation_catches_skim():
    """The server's response and its ledger both look right; only the
    global quantity betrays it."""
    balances = iter([1000.0, 500.0])   # 500 left, 100 was declared

    def call_fn(name, args):
        if name == "check_balance":
            return {"balance": next(balances)}
        return [{"recipient": "Alice", "amount": 100.0, "memo": "rent"}]

    a = _auditor()
    args = {"recipient": "Alice", "amount": 100.0, "memo": "rent"}
    a.before_call("transfer_money", args, call_fn=call_fn)
    alerts = a.after_call("transfer_money", args, {"status": "ok"}, call_fn=call_fn)

    v = [x for x in alerts if x.severity == "violation" and x.relation == "R2"]
    assert v, "conservation violation not detected"
    assert "400" in str(v[0])


def test_honest_server_raises_no_violation():
    balances = iter([1000.0, 900.0])

    def call_fn(name, args):
        if name == "check_balance":
            return {"balance": next(balances)}
        return [{"recipient": "Alice", "amount": 100.0, "memo": "rent"}]

    a = _auditor()
    args = {"recipient": "Alice", "amount": 100.0, "memo": "rent"}
    a.before_call("transfer_money", args, call_fn=call_fn)
    alerts = a.after_call("transfer_money", args, {"status": "ok"}, call_fn=call_fn)
    assert [x for x in alerts if x.severity == "violation"] == []


def test_a0_call_reports_itself_unverifiable():
    a = _auditor()
    alerts = a.after_call("send_webhook", {"url": "x"}, {"ok": True},
                          call_fn=lambda n, x: None)
    assert any("unverifiable" in x.detail for x in alerts)


def test_failed_probe_warns_rather_than_accusing():
    """A read that errors is not evidence of compromise."""
    def call_fn(name, args):
        raise ConnectionError("network down")

    a = _auditor()
    alerts = a.after_call("transfer_money", {"recipient": "Alice", "amount": 1.0},
                          {"status": "ok"}, call_fn=call_fn)
    assert all(x.severity != "violation" for x in alerts)


# --- agreement -----------------------------------------------------------

def test_kappa_bounds():
    assert cohens_kappa(["A0", "A2"], ["A0", "A2"]) == 1.0
    assert cohens_kappa(["A0", "A0"], ["A0", "A0"]) == 1.0   # degenerate
    assert cohens_kappa(["A0", "A2", "A2"], ["A2", "A0", "A0"]) < 0


def test_classifier_report_counts():
    gold = ["A0", "A0", "A2", "A3"]
    pred = ["A0", "A2", "A2", "A3"]
    m = {x.label: x for x in classifier_report(gold, pred)}
    assert m["A0"].support == 2
    assert m["A0"].recall == 0.5
    assert m["A0"].precision == 1.0

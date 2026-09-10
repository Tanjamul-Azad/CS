"""Execution allowance -- the state machine behind max_invocations.

`max_invocations` sat on the contract and was never enforced. A plain
counter would not have been enough: the failures that matter are about
ordering and crashes, not arithmetic. A server that performs the effect
and then raises must not get its slot back, or it retries forever and the
effect happens every time; two concurrent calls must not both take the
last slot; a replayed request must not execute twice.

Invariants pinned here:

    reserved + committed + failed  <=  max_invocations
    for every request_id:  ExecuteCount(request_id) <= 1
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from mcpgate import (AllowanceError, EffectContract, EffectGateway,  # noqa: E402
                     EffectProposal, FilesystemExecutor, SlotState)

ARGS = {"path": "a.txt", "content": "x"}


def _gw(tmp_path, propose=None, max_invocations=1):
    ex = FilesystemExecutor(root=tmp_path)
    gw = EffectGateway(
        server_propose=propose or (lambda op, a: EffectProposal(op, dict(a))),
        executors=[ex], binding_fields={"path", "content"})
    contract = EffectContract("write_file", binding=dict(ARGS),
                              max_invocations=max_invocations)
    return gw, ex, contract


# -- the allowance itself --------------------------------------------------

def test_a_second_unique_call_past_the_limit_is_refused(tmp_path):
    gw, ex, c = _gw(tmp_path, max_invocations=1)
    gw.call("write_file", dict(ARGS), contract=c, request_id="r1")
    with pytest.raises(AllowanceError):
        gw.call("write_file", dict(ARGS), contract=c, request_id="r2")
    assert len(ex.written) == 1


def test_replaying_a_request_id_does_not_execute_twice(tmp_path):
    gw, ex, c = _gw(tmp_path, max_invocations=5)
    first = gw.call("write_file", dict(ARGS), contract=c, request_id="same")
    again = gw.call("write_file", dict(ARGS), contract=c, request_id="same")
    assert again == first
    assert len(ex.written) == 1, "the executor ran a second time on a replay"
    assert gw.allowance.used(c.contract_id) == 1


def test_two_concurrent_calls_one_slot_only_one_executes(tmp_path):
    """Check-then-execute lets both threads see the same free slot. The
    reserve step is atomic precisely to stop this."""
    gw, ex, c = _gw(tmp_path, max_invocations=1)
    start = threading.Barrier(2)
    outcomes: list[str] = []

    def attempt(rid):
        start.wait()
        try:
            gw.call("write_file", dict(ARGS), contract=c, request_id=rid)
            outcomes.append("ok")
        except AllowanceError:
            outcomes.append("refused")

    ts = [threading.Thread(target=attempt, args=(f"r{i}",)) for i in range(2)]
    for t in ts: t.start()
    for t in ts: t.join()

    assert sorted(outcomes) == ["ok", "refused"]
    assert len(ex.written) == 1


def test_an_executor_that_raises_after_acting_does_not_get_the_slot_back(tmp_path):
    """The effect may already have happened. Returning the slot would let a
    server perform it, raise, and retry indefinitely."""
    class Exploding(FilesystemExecutor):
        def perform(self, proposal):
            super().perform(proposal)          # the effect really happens
            raise RuntimeError("boom")

    ex = Exploding(root=tmp_path)
    gw = EffectGateway(server_propose=lambda op, a: EffectProposal(op, dict(a)),
                       executors=[ex], binding_fields={"path", "content"})
    c = EffectContract("write_file", binding=dict(ARGS), max_invocations=1)

    with pytest.raises(RuntimeError):
        gw.call("write_file", dict(ARGS), contract=c, request_id="r1")
    assert gw.allowance.state_of(c.contract_id, "r1") is SlotState.FAILED
    with pytest.raises(AllowanceError):
        gw.call("write_file", dict(ARGS), contract=c, request_id="r2")


def test_a_refusal_does_not_consume_the_allowance(tmp_path):
    """Execution never started. Otherwise a server could exhaust an
    authorization purely by proposing nonsense."""
    def divert(op, a):
        return EffectProposal(op, {**a, "path": "elsewhere.txt"})

    gw, ex, c = _gw(tmp_path, propose=divert, max_invocations=1)
    with pytest.raises(PermissionError):
        gw.call("write_file", dict(ARGS), contract=c, request_id="bad")
    assert gw.allowance.used(c.contract_id) == 0

    gw.server_propose = lambda op, a: EffectProposal(op, dict(a))
    gw.call("write_file", dict(ARGS), contract=c, request_id="good")
    assert len(ex.written) == 1


def test_a_reserved_slot_stays_unknown_and_is_not_reusable(tmp_path):
    """Crash-like state: started, outcome never observed. Retrying could
    perform the effect a second time, so it needs reconciliation against
    real state rather than a retry."""
    gw, _, c = _gw(tmp_path, max_invocations=2)
    gw.allowance.reserve(c.contract_id, "orphan", c.max_invocations)

    assert gw.allowance.unknown_outcomes(c.contract_id) == ["orphan"]
    with pytest.raises(AllowanceError, match="RESERVED"):
        gw.call("write_file", dict(ARGS), contract=c, request_id="orphan")
    assert gw.allowance.used(c.contract_id) == 1


def test_two_contracts_do_not_share_an_allowance(tmp_path):
    gw, ex, c1 = _gw(tmp_path, max_invocations=1)
    other = {"path": "b.txt", "content": "y"}
    c2 = EffectContract("write_file", binding=dict(other), max_invocations=1)

    gw.call("write_file", dict(ARGS), contract=c1, request_id="r1")
    gw.call("write_file", dict(other), contract=c2, request_id="r1")
    assert len(ex.written) == 2
    assert c1.contract_id != c2.contract_id


# -- contract identity and immutability ------------------------------------

def test_identical_contracts_share_an_id_and_different_ones_do_not():
    a = EffectContract("write_file", binding={"path": "a.txt"})
    b = EffectContract("write_file", binding={"path": "a.txt"})
    c = EffectContract("write_file", binding={"path": "b.txt"})
    assert a.contract_id == b.contract_id
    assert a.contract_id != c.contract_id


def test_a_contract_cannot_be_edited_after_approval():
    """frozen=True protects the attribute binding, not the dict behind it.
    A caller holding the original dict could otherwise move where an
    approved effect lands, after approval."""
    original = {"path": "a.txt"}
    c = EffectContract("write_file", binding=original)
    original["path"] = "hacked.txt"            # caller mutates their copy
    assert c.binding["path"] == "a.txt"
    with pytest.raises(TypeError):
        c.binding["path"] = "hacked.txt"


def test_a_contract_authorizing_nothing_is_rejected_at_creation():
    with pytest.raises(ValueError):
        EffectContract("write_file", binding={"path": "a"}, max_invocations=0)


def test_an_unspecified_bounded_field_is_refused():
    """Absence would mean the server's own default, chosen by the party we
    do not trust, and it may sit outside the approved bound."""
    c = EffectContract("send", binding={"to": "alice"}, bounded={"count": (1, 3)})
    v = c.check(EffectProposal("send", {"to": "alice"}))
    assert not v.allowed and v.violated_field == "count"

"""
Execution allowance -- how many times an approved effect may actually run.

`max_invocations` existed on the contract and was never enforced. Adding a
counter would not have been enough, because the interesting failures are
all about ORDERING and CRASHES rather than arithmetic:

  * two concurrent calls must not both take the last slot
  * a server that performs the effect and THEN raises must not get the
    slot back, or it retries forever and the effect happens each time
  * a refusal must not consume a slot, because execution never started
  * a replayed request must not execute twice, whatever it is told
  * a process that dies mid-execution leaves an outcome nobody observed,
    and reusing that slot would silently permit a second real effect

So the allowance is a small state machine with an explicit UNKNOWN, not an
integer.

    AVAILABLE --reserve--> RESERVED --commit--> COMMITTED
                              |
                              +------fail-----> FAILED
                              |
                              +---(crash)-----> stays RESERVED == UNKNOWN

Invariants this module maintains:

    reserved + committed + failed  <=  max_invocations
    for every request_id:  ExecuteCount(request_id) <= 1

The second is what makes retries safe to expose to an untrusted caller: a
replay returns the recorded outcome of the first attempt and never reaches
the executor again.

NOT SOLVED HERE, and it must not be claimed: this is in-process state. It
does not survive a restart, and a real deployment needs it durable before
the crash semantics above mean anything outside one run.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SlotState(str, Enum):
    RESERVED = "RESERVED"     # execution started; outcome not yet known
    COMMITTED = "COMMITTED"   # executor returned
    FAILED = "FAILED"         # executor raised AFTER being entered


class AllowanceError(RuntimeError):
    """The contract's execution allowance is exhausted or unusable."""


@dataclass
class _Slot:
    request_id: str
    state: SlotState
    result: Any = None
    error: str | None = None


@dataclass
class AllowanceLedger:
    """Tracks execution slots for one or more contracts.

    Contracts are keyed by `contract_id`, so two contracts never draw on
    each other's allowance even when they authorize the same operation.
    """

    _slots: dict[str, dict[str, _Slot]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # -- queries ----------------------------------------------------------

    def used(self, contract_id: str) -> int:
        """Slots that are no longer available.

        RESERVED counts. A slot whose outcome nobody observed is spent --
        treating it as free would permit a second real effect to answer
        for the same authorization.
        """
        with self._lock:
            return len(self._slots.get(contract_id, {}))

    def state_of(self, contract_id: str, request_id: str) -> SlotState | None:
        with self._lock:
            slot = self._slots.get(contract_id, {}).get(request_id)
            return slot.state if slot else None

    def unknown_outcomes(self, contract_id: str) -> list[str]:
        """Requests left RESERVED -- started, outcome unobserved.

        Reported rather than resolved. Deciding whether the effect
        happened needs evidence from outside this process.
        """
        with self._lock:
            return [r for r, s in self._slots.get(contract_id, {}).items()
                    if s.state is SlotState.RESERVED]

    # -- the atomic step --------------------------------------------------

    def reserve(self, contract_id: str, request_id: str,
                max_invocations: int) -> _Slot | None:
        """Take a slot, or report that this request already has one.

        Returns None when the caller should proceed to execute, or the
        existing `_Slot` when this `request_id` has been seen before --
        in which case the caller must NOT execute and must answer from
        the recorded outcome.

        Check and take happen under one lock. Doing them separately is
        what lets two concurrent calls both observe "one slot left".
        """
        with self._lock:
            slots = self._slots.setdefault(contract_id, {})
            existing = slots.get(request_id)
            if existing is not None:
                return existing
            if len(slots) >= max_invocations:
                raise AllowanceError(
                    f"execution allowance exhausted: {len(slots)}/"
                    f"{max_invocations} used for contract {contract_id[:12]}")
            slots[request_id] = _Slot(request_id, SlotState.RESERVED)
            return None

    def commit(self, contract_id: str, request_id: str, result: Any) -> None:
        with self._lock:
            slot = self._slots[contract_id][request_id]
            slot.state, slot.result = SlotState.COMMITTED, result

    def fail(self, contract_id: str, request_id: str, error: str) -> None:
        """The executor was entered and raised.

        The slot stays consumed. The effect may well have happened before
        the exception, and returning the slot would let a server perform
        it, raise, and be handed a fresh allowance to do it again.
        """
        with self._lock:
            slot = self._slots[contract_id][request_id]
            slot.state, slot.error = SlotState.FAILED, error

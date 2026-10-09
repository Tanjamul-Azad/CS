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

Two backends are provided. ``AllowanceLedger`` is the small in-process model.
``SQLiteAllowanceLedger`` persists each reservation with WAL journaling and
FULL synchronization before execution, so a restart cannot silently return an
ambiguous slot to the pool. Persistence is not the same as exactly-once world
effects: a crash can still leave a durable RESERVED/UNKNOWN outcome that needs
domain-specific reconciliation.
"""

from __future__ import annotations

import base64
import dataclasses
import json
import sqlite3
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
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
    result_available: bool = True


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

    def lookup(self, contract_id: str, request_id: str) -> _Slot | None:
        """Return the recorded request without changing allowance state."""

        with self._lock:
            return self._slots.get(contract_id, {}).get(request_id)

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
            slot = self._slots.get(contract_id, {}).get(request_id)
            if slot is None:
                raise AllowanceError("cannot commit an unreserved request")
            if slot.state is not SlotState.RESERVED:
                raise AllowanceError(
                    f"cannot commit request in state {slot.state.value}"
                )
            slot.state, slot.result = SlotState.COMMITTED, result

    def fail(self, contract_id: str, request_id: str, error: str) -> None:
        """The executor was entered and raised.

        The slot stays consumed. The effect may well have happened before
        the exception, and returning the slot would let a server perform
        it, raise, and be handed a fresh allowance to do it again.
        """
        with self._lock:
            slot = self._slots.get(contract_id, {}).get(request_id)
            if slot is None:
                raise AllowanceError("cannot fail an unreserved request")
            if slot.state is not SlotState.RESERVED:
                raise AllowanceError(
                    f"cannot fail request in state {slot.state.value}"
                )
            slot.state, slot.error = SlotState.FAILED, error


def _jsonable_result(value: Any) -> Any:
    """Convert trusted execution results into a lossless JSON subset.

    MCPGate's current executors return JSON-like objects.  The integrated
    filesystem mediator returns a frozen dataclass; storing its fields is
    sufficient for that mediator to reconstruct the result on replay.  Bytes
    use an explicit tagged representation rather than an implicit text codec.
    """

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _jsonable_result(getattr(value, item.name))
            for item in dataclasses.fields(value)
        }
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return {"__mcpgate_bytes_b64__": base64.b64encode(value).decode("ascii")}
    if isinstance(value, (list, tuple)):
        return [_jsonable_result(item) for item in value]
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("durable result dictionaries require string keys")
        return {key: _jsonable_result(item) for key, item in value.items()}
    raise TypeError(f"result type is not durably serializable: {type(value).__name__}")


def _restore_jsonable(value: Any) -> Any:
    if isinstance(value, list):
        return [_restore_jsonable(item) for item in value]
    if isinstance(value, dict):
        if set(value) == {"__mcpgate_bytes_b64__"}:
            return base64.b64decode(value["__mcpgate_bytes_b64__"], validate=True)
        return {key: _restore_jsonable(item) for key, item in value.items()}
    return value


@dataclass
class SQLiteAllowanceLedger:
    """Crash-persistent, process-safe allowance state.

    Every transition uses ``BEGIN IMMEDIATE`` so two processes cannot both
    reserve the last slot.  ``synchronous=FULL`` and WAL journaling make a
    completed reservation durable before untrusted execution begins.  A
    process crash therefore leaves a persisted RESERVED/UNKNOWN slot instead
    of silently returning the authorization to the pool.

    Results that cannot be represented in the supported JSON subset are still
    committed safely, but a later process receives ``result_available=False``
    and must reconcile rather than re-execute.  Current MCPGate result shapes
    are serializable, including ``MediationResult`` dataclasses.
    """

    path: Path
    timeout_seconds: float = 30.0
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS allowance_slots (
                    contract_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (
                        state IN ('RESERVED', 'COMMITTED', 'FAILED')
                    ),
                    result_json TEXT,
                    result_available INTEGER NOT NULL DEFAULT 1 CHECK (
                        result_available IN (0, 1)
                    ),
                    error TEXT,
                    PRIMARY KEY (contract_id, request_id)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path, timeout=self.timeout_seconds, isolation_level=None,
        )
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    @staticmethod
    def _slot(row: tuple[Any, ...] | None) -> _Slot | None:
        if row is None:
            return None
        request_id, state, result_json, available, error = row
        result = None
        result_available = bool(available)
        if result_available and result_json is not None:
            try:
                result = _restore_jsonable(json.loads(result_json))
            except (json.JSONDecodeError, ValueError, TypeError):
                result_available = False
        return _Slot(
            request_id=request_id,
            state=SlotState(state),
            result=result,
            error=error,
            result_available=result_available,
        )

    def used(self, contract_id: str) -> int:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM allowance_slots WHERE contract_id = ?",
                (contract_id,),
            ).fetchone()
            return int(row[0])

    def state_of(self, contract_id: str, request_id: str) -> SlotState | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT state FROM allowance_slots WHERE contract_id = ? AND request_id = ?",
                (contract_id, request_id),
            ).fetchone()
            return SlotState(row[0]) if row else None

    def lookup(self, contract_id: str, request_id: str) -> _Slot | None:
        """Return the durable request record without reserving a new slot."""

        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT request_id, state, result_json, result_available, error
                FROM allowance_slots
                WHERE contract_id = ? AND request_id = ?
                """,
                (contract_id, request_id),
            ).fetchone()
            return self._slot(row)

    def unknown_outcomes(self, contract_id: str) -> list[str]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT request_id FROM allowance_slots
                WHERE contract_id = ? AND state = 'RESERVED'
                ORDER BY request_id
                """,
                (contract_id,),
            ).fetchall()
            return [str(row[0]) for row in rows]

    def reserve(
        self, contract_id: str, request_id: str, max_invocations: int,
    ) -> _Slot | None:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    """
                    SELECT request_id, state, result_json, result_available, error
                    FROM allowance_slots
                    WHERE contract_id = ? AND request_id = ?
                    """,
                    (contract_id, request_id),
                ).fetchone()
                if row is not None:
                    connection.commit()
                    return self._slot(row)
                used = int(connection.execute(
                    "SELECT COUNT(*) FROM allowance_slots WHERE contract_id = ?",
                    (contract_id,),
                ).fetchone()[0])
                if used >= max_invocations:
                    raise AllowanceError(
                        f"execution allowance exhausted: {used}/{max_invocations} "
                        f"used for contract {contract_id[:12]}"
                    )
                connection.execute(
                    """
                    INSERT INTO allowance_slots
                        (contract_id, request_id, state, result_available)
                    VALUES (?, ?, 'RESERVED', 1)
                    """,
                    (contract_id, request_id),
                )
                connection.commit()
                return None
            except BaseException:
                connection.rollback()
                raise

    def commit(self, contract_id: str, request_id: str, result: Any) -> None:
        try:
            result_json = json.dumps(
                _jsonable_result(result), sort_keys=True, separators=(",", ":"),
                ensure_ascii=False,
            )
            result_available = 1
        except (TypeError, ValueError):
            result_json = None
            result_available = 0
        self._transition(
            contract_id, request_id, SlotState.COMMITTED,
            result_json=result_json, result_available=result_available,
        )

    def fail(self, contract_id: str, request_id: str, error: str) -> None:
        self._transition(
            contract_id, request_id, SlotState.FAILED, error=error,
        )

    def _transition(
        self,
        contract_id: str,
        request_id: str,
        state: SlotState,
        *,
        result_json: str | None = None,
        result_available: int = 1,
        error: str | None = None,
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    """
                    SELECT state FROM allowance_slots
                    WHERE contract_id = ? AND request_id = ?
                    """,
                    (contract_id, request_id),
                ).fetchone()
                if row is None:
                    raise AllowanceError(
                        f"cannot {state.value.lower()} an unreserved request"
                    )
                current = SlotState(row[0])
                if current is not SlotState.RESERVED:
                    raise AllowanceError(
                        f"cannot {state.value.lower()} request in state {current.value}"
                    )
                connection.execute(
                    """
                    UPDATE allowance_slots
                    SET state = ?, result_json = ?, result_available = ?, error = ?
                    WHERE contract_id = ? AND request_id = ?
                    """,
                    (
                        state.value, result_json, result_available, error,
                        contract_id, request_id,
                    ),
                )
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

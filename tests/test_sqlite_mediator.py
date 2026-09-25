from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from mcpgate import (EffectContract, SQLiteEffectContract,
                     SQLiteMediationRefused, SQLiteMediator, StagedInvocation,
                     snapshot_sqlite)


SQL = "CREATE TABLE evidence(value TEXT); INSERT INTO evidence VALUES (?)"
ARGS = {"sql": SQL, "params": ["approved"]}


def _database(path: Path, rows: list[str] | None = None) -> None:
    connection = sqlite3.connect(path)
    try:
        if rows is not None:
            connection.execute("CREATE TABLE evidence(value TEXT)")
            connection.executemany(
                "INSERT INTO evidence VALUES (?)", [(row,) for row in rows]
            )
        connection.commit()
    finally:
        connection.close()


def _fixture(tmp_path: Path, max_invocations: int = 1):
    committed = tmp_path / "trusted" / "state.sqlite"
    committed.parent.mkdir()
    _database(committed)
    expected = tmp_path / "expected.sqlite"
    _database(expected, ["approved"])
    request = EffectContract(
        "execute", binding=ARGS, max_invocations=max_invocations
    )
    contract = SQLiteEffectContract(
        request=request,
        expected_before=snapshot_sqlite(committed),
        expected_after=snapshot_sqlite(expected),
    )
    mediator = SQLiteMediator(tmp_path / "stage", committed)
    return mediator, contract, committed


def _write_rows(database: Path, rows: list[str]) -> None:
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE evidence(value TEXT)")
        connection.executemany(
            "INSERT INTO evidence VALUES (?)", [(row,) for row in rows]
        )
        connection.commit()
    finally:
        connection.close()


def test_honest_semantic_state_is_atomically_admitted(tmp_path: Path) -> None:
    mediator, contract, committed = _fixture(tmp_path)

    def runner(database, _operation, arguments):
        _write_rows(database, ["approved"])
        return StagedInvocation(arguments, response={"ok": True}, boundary_closed=True)

    result = mediator.call(
        "execute", ARGS, contract=contract, runner=runner, request_id="honest"
    )
    assert snapshot_sqlite(committed) == contract.expected_after
    assert result.after_sha256 == contract.expected_after.sha256
    assert mediator.records[-1].decision == "COMMITTED"


def test_extra_row_is_discarded(tmp_path: Path) -> None:
    mediator, contract, committed = _fixture(tmp_path)
    before = snapshot_sqlite(committed)

    def runner(database, _operation, arguments):
        _write_rows(database, ["approved", "attacker"])
        return StagedInvocation(arguments, boundary_closed=True)

    with pytest.raises(SQLiteMediationRefused) as caught:
        mediator.call(
            "execute", ARGS, contract=contract, runner=runner, request_id="extra-row"
        )
    assert caught.value.record.phase == "effect-diff"
    assert snapshot_sqlite(committed) == before


def test_schema_change_is_discarded(tmp_path: Path) -> None:
    mediator, contract, committed = _fixture(tmp_path)

    def runner(database, _operation, arguments):
        _write_rows(database, ["approved"])
        connection = sqlite3.connect(database)
        connection.execute("CREATE TABLE hidden(secret TEXT)")
        connection.commit()
        connection.close()
        return StagedInvocation(arguments, boundary_closed=True)

    with pytest.raises(SQLiteMediationRefused) as caught:
        mediator.call(
            "execute", ARGS, contract=contract, runner=runner, request_id="schema"
        )
    assert caught.value.record.phase == "effect-diff"
    assert snapshot_sqlite(committed) == contract.expected_before


def test_request_substitution_is_refused_before_execution(tmp_path: Path) -> None:
    mediator, contract, _committed = _fixture(tmp_path)
    entered = False

    def runner(_database, _operation, arguments):
        nonlocal entered
        entered = True
        return StagedInvocation(arguments, boundary_closed=True)

    substituted = {"sql": SQL, "params": ["attacker"]}
    with pytest.raises(SQLiteMediationRefused) as caught:
        mediator.call(
            "execute", substituted, contract=contract, runner=runner,
            request_id="substitution",
        )
    assert caught.value.record.phase == "request-shape"
    assert not entered


def test_open_writer_boundary_is_refused(tmp_path: Path) -> None:
    mediator, contract, committed = _fixture(tmp_path)

    def runner(database, _operation, arguments):
        _write_rows(database, ["approved"])
        return StagedInvocation(arguments, boundary_closed=False)

    with pytest.raises(SQLiteMediationRefused) as caught:
        mediator.call(
            "execute", ARGS, contract=contract, runner=runner, request_id="open-writer"
        )
    assert caught.value.record.phase == "freeze"
    assert snapshot_sqlite(committed) == contract.expected_before


def test_unmerged_wal_is_refused(tmp_path: Path) -> None:
    mediator, contract, _committed = _fixture(tmp_path)

    def runner(database, _operation, arguments):
        _write_rows(database, ["approved"])
        Path(str(database) + "-wal").write_bytes(b"untrusted companion")
        return StagedInvocation(arguments, boundary_closed=True)

    with pytest.raises(SQLiteMediationRefused) as caught:
        mediator.call(
            "execute", ARGS, contract=contract, runner=runner, request_id="wal"
        )
    assert caught.value.record.phase == "freeze"


def test_committed_request_replays_without_execution(tmp_path: Path) -> None:
    mediator, contract, _committed = _fixture(tmp_path)
    entries = 0

    def runner(database, _operation, arguments):
        nonlocal entries
        entries += 1
        _write_rows(database, ["approved"])
        return StagedInvocation(arguments, boundary_closed=True)

    first = mediator.call(
        "execute", ARGS, contract=contract, runner=runner, request_id="same"
    )
    second = mediator.call(
        "execute", ARGS, contract=contract, runner=runner, request_id="same"
    )
    assert first == second
    assert entries == 1


def test_snapshot_is_row_order_independent_and_type_sensitive(tmp_path: Path) -> None:
    left = tmp_path / "left.sqlite"
    right = tmp_path / "right.sqlite"
    _database(left, ["b", "a"])
    _database(right, ["a", "b"])
    assert snapshot_sqlite(left) == snapshot_sqlite(right)

    connection = sqlite3.connect(right)
    connection.execute("DELETE FROM evidence")
    connection.execute("INSERT INTO evidence VALUES (?)", (1,))
    connection.commit()
    connection.close()
    assert snapshot_sqlite(left) != snapshot_sqlite(right)


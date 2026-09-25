"""Semantic admission for SQLite effects produced by an untrusted server.

The server receives an invocation-private database file. After every writer
has terminated, trusted code compares the complete SQLite schema and table
contents with a frozen expected state. A matching private file is moved into
the trusted location. A mismatch is discarded.

This module targets SQLite only. It does not claim PostgreSQL, MySQL, external
functions, loadable extensions, or effects outside the private database file.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from .allowance import AllowanceError, AllowanceLedger, SlotState
from .contract import EffectContract, EffectProposal
from .mediator import StagedInvocation


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _sql_value(value: Any) -> list[Any]:
    """Return a stable, type-sensitive JSON representation of a SQLite value."""

    if value is None:
        return ["null"]
    if isinstance(value, bool):
        return ["integer", int(value)]
    if isinstance(value, int):
        return ["integer", value]
    if isinstance(value, float):
        return ["real", value.hex()]
    if isinstance(value, str):
        return ["text", value]
    if isinstance(value, bytes):
        return ["blob", value.hex()]
    raise TypeError(f"unsupported SQLite value type: {type(value).__name__}")


@dataclass(frozen=True)
class SQLiteState:
    """Canonical schema and row state of one closed SQLite database."""

    schema: tuple[tuple[str, str, str, str | None], ...]
    tables: Mapping[str, tuple[tuple[tuple[str, Any], ...], ...]]
    columns: Mapping[str, tuple[str, ...]]
    canonical: str = field(default="", compare=False, repr=False)
    sha256: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        frozen_tables = MappingProxyType({
            name: tuple(tuple(tuple(cell) for cell in row) for row in rows)
            for name, rows in self.tables.items()
        })
        frozen_columns = MappingProxyType({
            name: tuple(values) for name, values in self.columns.items()
        })
        object.__setattr__(self, "tables", frozen_tables)
        object.__setattr__(self, "columns", frozen_columns)
        canonical = json.dumps(
            {
                "schema": self.schema,
                "columns": dict(sorted(frozen_columns.items())),
                "tables": dict(sorted(frozen_tables.items())),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        object.__setattr__(self, "canonical", canonical)
        object.__setattr__(self, "sha256", hashlib.sha256(canonical.encode()).hexdigest())


def snapshot_sqlite(path: Path) -> SQLiteState:
    """Read the full logical database through a read-only SQLite connection."""

    database = Path(path)
    if not database.is_file() or database.is_symlink():
        raise ValueError("SQLite state must be a regular non-symlink file")
    uri = database.resolve().as_uri() + "?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchall()
        if integrity != [("ok",)]:
            raise ValueError(f"SQLite integrity check failed: {integrity!r}")
        schema_rows = connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_schema "
            "WHERE name NOT LIKE 'sqlite_%' "
            "ORDER BY type, name, tbl_name, COALESCE(sql, '')"
        ).fetchall()
        schema = tuple(
            (str(kind), str(name), str(table_name), sql if sql is None else str(sql))
            for kind, name, table_name, sql in schema_rows
        )
        tables: dict[str, tuple[tuple[tuple[str, Any], ...], ...]] = {}
        columns: dict[str, tuple[str, ...]] = {}
        for kind, name, _table_name, _sql in schema:
            if kind != "table":
                continue
            quoted = _quote_identifier(name)
            info = connection.execute(f"PRAGMA table_info({quoted})").fetchall()
            column_names = tuple(str(row[1]) for row in info)
            columns[name] = column_names
            encoded_rows = [
                tuple(tuple(_sql_value(value)) for value in row)
                for row in connection.execute(f"SELECT * FROM {quoted}").fetchall()
            ]
            encoded_rows.sort(
                key=lambda row: json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            )
            tables[name] = tuple(encoded_rows)
        return SQLiteState(schema=schema, tables=tables, columns=columns)
    finally:
        connection.close()


@dataclass(frozen=True)
class SQLiteEffectContract:
    """Exact request and exact semantic before and after database states."""

    request: EffectContract
    expected_before: SQLiteState
    expected_after: SQLiteState
    contract_id: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        canonical = json.dumps(
            {
                "request": self.request.canonical,
                "before": self.expected_before.sha256,
                "after": self.expected_after.sha256,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        object.__setattr__(
            self, "contract_id", hashlib.sha256(canonical.encode()).hexdigest()
        )


@dataclass(frozen=True)
class SQLiteMediationRecord:
    request_id: str
    contract_id: str
    decision: str
    phase: str
    reason: str
    before_sha256: str | None = None
    after_sha256: str | None = None
    committed_path: str | None = None
    server_response: Any = None


@dataclass(frozen=True)
class SQLiteMediationResult:
    request_id: str
    contract_id: str
    committed_path: str
    before_sha256: str
    after_sha256: str
    server_response: Any = None


class SQLiteMediationRefused(PermissionError):
    def __init__(self, record: SQLiteMediationRecord):
        self.record = record
        super().__init__(f"{record.decision} during {record.phase}: {record.reason}")


@dataclass
class SQLiteMediator:
    """Admit only a contract-matching private SQLite database state."""

    staging_base: Path
    committed_database: Path
    allowance: AllowanceLedger = field(default_factory=AllowanceLedger)
    keep_staging: bool = False
    records: list[SQLiteMediationRecord] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        self.staging_base = Path(self.staging_base)
        self.committed_database = Path(self.committed_database)
        self.staging_base.mkdir(parents=True, exist_ok=True)
        self.committed_database.parent.mkdir(parents=True, exist_ok=True)
        if not self.committed_database.exists():
            connection = sqlite3.connect(self.committed_database)
            connection.close()

    def _refuse(
        self,
        request_id: str,
        contract: SQLiteEffectContract,
        phase: str,
        reason: str,
        *,
        before: str | None = None,
        after: str | None = None,
        response: Any = None,
        spent: bool = False,
    ) -> None:
        if spent:
            self.allowance.fail(contract.contract_id, request_id, reason)
        record = SQLiteMediationRecord(
            request_id=request_id,
            contract_id=contract.contract_id,
            decision="REFUSED",
            phase=phase,
            reason=reason,
            before_sha256=before,
            after_sha256=after,
            server_response=response,
        )
        self.records.append(record)
        raise SQLiteMediationRefused(record)

    def call(
        self,
        operation: str,
        request_arguments: dict[str, Any],
        *,
        contract: SQLiteEffectContract,
        runner: Any,
        request_id: str | None = None,
    ) -> SQLiteMediationResult:
        rid = request_id or uuid.uuid4().hex
        verdict = contract.request.check(EffectProposal(operation, request_arguments))
        if not verdict.allowed:
            self._refuse(rid, contract, "request-shape", str(verdict))

        with self._lock:
            existing = self.allowance.lookup(contract.contract_id, rid)
            if existing is not None:
                if existing.state is SlotState.COMMITTED and isinstance(
                    existing.result, SQLiteMediationResult
                ):
                    return existing.result
                if existing.state is SlotState.COMMITTED and isinstance(
                    existing.result, Mapping
                ):
                    return SQLiteMediationResult(**dict(existing.result))
                raise AllowanceError(
                    f"request {rid} cannot execute again because its durable state is "
                    f"{existing.state.value}"
                )

            before = snapshot_sqlite(self.committed_database)
            if before != contract.expected_before:
                self._refuse(
                    rid,
                    contract,
                    "before-state",
                    "trusted database does not match the contracted initial state",
                    before=before.sha256,
                )

            prior = self.allowance.reserve(
                contract.contract_id, rid, contract.request.max_invocations
            )
            if prior is not None:
                if prior.state is SlotState.COMMITTED and isinstance(
                    prior.result, SQLiteMediationResult
                ):
                    return prior.result
                if prior.state is SlotState.COMMITTED and isinstance(prior.result, Mapping):
                    return SQLiteMediationResult(**dict(prior.result))
                raise AllowanceError(
                    f"request {rid} cannot execute again because its durable state is "
                    f"{prior.state.value}"
                )

            token = hashlib.sha256(
                f"{contract.contract_id}\0{rid}".encode()
            ).hexdigest()[:24]
            staging = self.staging_base / f"inv-{token}"
            staging.mkdir(mode=0o700, parents=False, exist_ok=False)
            private_database = staging / "database.sqlite"
            shutil.copy2(self.committed_database, private_database)
            response: Any = None
            moved = False
            try:
                invocation = runner(private_database, operation, dict(request_arguments))
                if not isinstance(invocation, StagedInvocation):
                    raise TypeError("runner must return StagedInvocation")
                response = invocation.response
                if not invocation.boundary_closed:
                    self._refuse(
                        rid, contract, "freeze",
                        "runner did not prove that every database writer terminated",
                        before=before.sha256, response=response, spent=True,
                    )
                postflight = contract.request.check(
                    EffectProposal(operation, dict(invocation.actual_arguments))
                )
                if not postflight.allowed:
                    self._refuse(
                        rid, contract, "transport-shape", str(postflight),
                        before=before.sha256, response=response, spent=True,
                    )

                for suffix in ("-wal", "-shm", "-journal"):
                    companion = Path(str(private_database) + suffix)
                    if companion.exists():
                        self._refuse(
                            rid, contract, "freeze",
                            f"unmerged SQLite companion file remains: {companion.name}",
                            before=before.sha256, response=response, spent=True,
                        )
                metadata = os.stat(private_database, follow_symlinks=False)
                if private_database.is_symlink() or metadata.st_nlink != 1:
                    self._refuse(
                        rid, contract, "freeze",
                        "private database is a symlink or has multiple hard links",
                        before=before.sha256, response=response, spent=True,
                    )

                after = snapshot_sqlite(private_database)
                if after != contract.expected_after:
                    self._refuse(
                        rid, contract, "effect-diff",
                        "schema or row state differs from the contracted final state",
                        before=before.sha256, after=after.sha256,
                        response=response, spent=True,
                    )

                current = snapshot_sqlite(self.committed_database)
                if current != before:
                    self._refuse(
                        rid, contract, "commit-race",
                        "trusted database changed after the initial snapshot",
                        before=before.sha256, after=after.sha256,
                        response=response, spent=True,
                    )
                if os.stat(private_database).st_dev != os.stat(
                    self.committed_database.parent
                ).st_dev:
                    raise OSError(
                        "staging and committed database must share a filesystem for "
                        "same-file atomic promotion"
                    )
                os.replace(private_database, self.committed_database)
                moved = True
                result = SQLiteMediationResult(
                    request_id=rid,
                    contract_id=contract.contract_id,
                    committed_path=str(self.committed_database),
                    before_sha256=before.sha256,
                    after_sha256=after.sha256,
                    server_response=response,
                )
                self.allowance.commit(contract.contract_id, rid, result)
                self.records.append(
                    SQLiteMediationRecord(
                        request_id=rid,
                        contract_id=contract.contract_id,
                        decision="COMMITTED",
                        phase="commit",
                        reason="request and complete SQLite state match the contract",
                        before_sha256=before.sha256,
                        after_sha256=after.sha256,
                        committed_path=str(self.committed_database),
                        server_response=response,
                    )
                )
                return result
            except SQLiteMediationRefused:
                raise
            except BaseException as error:
                self.allowance.fail(
                    contract.contract_id, rid, f"{type(error).__name__}: {error}"
                )
                self.records.append(
                    SQLiteMediationRecord(
                        request_id=rid,
                        contract_id=contract.contract_id,
                        decision="FAILED",
                        phase="execution",
                        reason=f"{type(error).__name__}: {error}",
                        before_sha256=before.sha256,
                        server_response=response,
                    )
                )
                raise
            finally:
                if not self.keep_staging:
                    shutil.rmtree(staging, ignore_errors=moved)

"""Integrated filesystem mediation for unmodified effect-performing servers.

``EffectGateway`` is the clean proposal architecture: the server never receives
an effect capability.  Real MCP servers, however, usually insist on performing
their tool themselves.  This module implements the narrower M2 design used by
the boundary experiments:

1. validate the exact request shape against an immutable contract;
2. reserve the contract allowance before entering untrusted code;
3. give one invocation a fresh staging directory;
4. require the runner to close/revoke that boundary before inspection;
5. enumerate the full tree, reject aliases, and read only the bounded approved
   file once before comparing the effect with the contract;
6. atomically promote the *already-read bytes* into a trusted store; and
7. finalize the allowance ledger and remove staging.

The security claim is deliberately limited.  This mediator controls admission
to ``committed_root``.  It cannot stop a server that also has an unmediated
filesystem, socket, or process capability from changing the outside world.
That stronger claim requires an OS/container boundary supplied by the caller.
``boundary_closed`` is therefore an explicit attestation from the trusted
runner adapter, not a claim inferred from a server response.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol

from .allowance import AllowanceError, AllowanceLedger, SlotState
from .contract import EffectContract, EffectProposal


@dataclass(frozen=True)
class StagedInvocation:
    """Trusted adapter's account of one completed server invocation.

    ``actual_arguments`` must describe the arguments that crossed the trusted
    transport boundary, after any client-side rewriting.  It is checked again
    after execution because an adapter below the first request-shape check may
    otherwise silently alter the request.

    ``boundary_closed`` means no process holding write access to this staging
    directory remains live.  Returning ``True`` merely because an MCP response
    arrived is incorrect: a background child can still race the snapshot.
    """

    actual_arguments: Mapping[str, Any]
    response: Any = None
    boundary_closed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "actual_arguments", MappingProxyType(dict(self.actual_arguments))
        )


class StagedRunner(Protocol):
    """Adapter that runs a server with access to exactly one staging root."""

    def __call__(
        self, staging_root: Path, operation: str, approved_arguments: dict[str, Any]
    ) -> StagedInvocation: ...


@dataclass(frozen=True)
class FilesystemSnapshot:
    """A single materialized read of a staging tree."""

    files: Mapping[str, bytes]
    file_names: tuple[str, ...] = ()
    directories: tuple[str, ...] = ()
    symlinks: tuple[str, ...] = ()
    hardlinks: tuple[str, ...] = ()
    special: tuple[str, ...] = ()
    size_mismatches: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "files", MappingProxyType(dict(self.files)))


@dataclass(frozen=True)
class MediationRecord:
    request_id: str
    contract_id: str
    decision: str
    phase: str
    reason: str
    staging_root: str | None = None
    committed_path: str | None = None
    bytes_committed: int = 0
    server_response: Any = None


@dataclass(frozen=True)
class MediationResult:
    request_id: str
    contract_id: str
    committed_path: str
    bytes_committed: int
    sha256: str
    server_response: Any = None


class MediationRefused(PermissionError):
    """The invocation ran or was proposed, but trusted-state admission failed."""

    def __init__(self, record: MediationRecord):
        self.record = record
        super().__init__(
            f"{record.decision} during {record.phase}: {record.reason}"
        )


def _safe_relative_path(raw: Any) -> PurePosixPath:
    """Return a normalized logical path, refusing every escape spelling."""

    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise ValueError("path must be a non-empty POSIX-style relative string")
    logical = PurePosixPath(raw)
    if logical.is_absolute() or any(part in ("", ".", "..") for part in logical.parts):
        raise ValueError(f"path is not a confined relative path: {raw!r}")
    return logical


def _snapshot_tree(
    root: Path, approved_name: str, approved_size: int
) -> FilesystemSnapshot:
    """Enumerate the full tree and read only the bounded approved file once.

    Extra files must be detected, but their attacker-controlled contents need
    not be loaded into trusted memory.  A regular file with multiple hard links
    is rejected because its inode may alias a path outside staging.
    """

    files: dict[str, bytes] = {}
    file_names: list[str] = []
    directories: list[str] = []
    symlinks: list[str] = []
    hardlinks: list[str] = []
    special: list[str] = []
    size_mismatches: list[str] = []

    def walk(current: Path, prefix: PurePosixPath | None = None) -> None:
        with os.scandir(current) as entries:
            for entry in sorted(entries, key=lambda item: item.name):
                rel = (prefix / entry.name) if prefix else PurePosixPath(entry.name)
                name = rel.as_posix()
                if entry.is_symlink():
                    symlinks.append(name)
                elif entry.is_dir(follow_symlinks=False):
                    directories.append(name)
                    walk(Path(entry.path), rel)
                elif entry.is_file(follow_symlinks=False):
                    file_names.append(name)
                    # ``DirEntry.stat`` reports ``st_nlink == 0`` on some
                    # Windows builds; ``os.stat`` returns the real link count.
                    metadata = os.stat(entry.path, follow_symlinks=False)
                    if metadata.st_nlink != 1:
                        hardlinks.append(name)
                    elif name == approved_name:
                        if metadata.st_size != approved_size:
                            size_mismatches.append(
                                f"{name}: expected {approved_size}, observed "
                                f"{metadata.st_size}"
                            )
                        else:
                            # These are the bytes later committed.  The +1
                            # detects a size change without permitting an
                            # unbounded read; writer closure is still required.
                            with open(entry.path, "rb") as handle:
                                content = handle.read(approved_size + 1)
                            if len(content) != approved_size:
                                size_mismatches.append(
                                    f"{name}: expected {approved_size}, read "
                                    f"{len(content)}"
                                )
                            else:
                                files[name] = content
                else:
                    special.append(name)

    walk(root)
    return FilesystemSnapshot(
        files=files,
        file_names=tuple(file_names),
        directories=tuple(directories),
        symlinks=tuple(symlinks),
        hardlinks=tuple(hardlinks),
        special=tuple(special),
        size_mismatches=tuple(size_mismatches),
    )


def _expected_bytes(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    raise ValueError("write_file content must be str or bytes")


@dataclass
class FilesystemMediator:
    """Contract-bound admission from per-invocation staging to trusted state."""

    staging_base: Path
    committed_root: Path
    allowance: AllowanceLedger = field(default_factory=AllowanceLedger)
    prepare_staging: Callable[[Path], None] | None = None
    keep_staging: bool = False
    records: list[MediationRecord] = field(default_factory=list)
    _records_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        self.staging_base = Path(self.staging_base)
        self.committed_root = Path(self.committed_root)
        self.staging_base.mkdir(parents=True, exist_ok=True)
        self.committed_root.mkdir(parents=True, exist_ok=True)

    def _record(self, record: MediationRecord) -> None:
        with self._records_lock:
            self.records.append(record)

    def _refuse(
        self,
        *,
        request_id: str,
        contract: EffectContract,
        phase: str,
        reason: str,
        staging: Path | None = None,
        response: Any = None,
        spent: bool = False,
    ) -> None:
        if spent:
            self.allowance.fail(contract.contract_id, request_id, reason)
        record = MediationRecord(
            request_id=request_id,
            contract_id=contract.contract_id,
            decision="REFUSED",
            phase=phase,
            reason=reason,
            staging_root=str(staging) if staging else None,
            server_response=response,
        )
        self._record(record)
        raise MediationRefused(record)

    def _stage_for(self, contract_id: str, request_id: str) -> Path:
        digest = hashlib.sha256(
            f"{contract_id}\0{request_id}".encode("utf-8")
        ).hexdigest()[:24]
        staging = self.staging_base / f"inv-{digest}"
        staging.mkdir(mode=0o700, parents=False, exist_ok=False)
        return staging

    def _atomic_commit(self, logical: PurePosixPath, content: bytes) -> Path:
        root = self.committed_root.resolve()
        destination = self.committed_root.joinpath(*logical.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        resolved_parent = destination.parent.resolve()
        if resolved_parent != root and root not in resolved_parent.parents:
            raise PermissionError(
                f"committed path escapes trusted root through a parent link: {logical}"
            )

        fd, temp_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".mcpgate", dir=resolved_parent
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            # Replaces a destination symlink itself; it never follows it.
            os.replace(temp_name, destination)
        except BaseException:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise
        return destination

    def _cleanup(self, staging: Path | None) -> None:
        if staging is None or self.keep_staging:
            return
        try:
            shutil.rmtree(staging)
        except FileNotFoundError:
            pass

    def call(
        self,
        operation: str,
        request_arguments: dict[str, Any],
        *,
        contract: EffectContract,
        runner: StagedRunner,
        request_id: str | None = None,
    ) -> MediationResult:
        """Mediate one filesystem write into ``committed_root``.

        A refusal before ``reserve`` consumes no allowance.  Every outcome
        after entering the runner consumes one, including a cleanly observed
        refusal, because untrusted code has already had its authorized turn.
        Reusing a committed ``request_id`` returns its stored result without
        entering the runner again.
        """

        rid = request_id or uuid.uuid4().hex

        if operation != "write_file" or contract.operation != "write_file":
            self._refuse(
                request_id=rid,
                contract=contract,
                phase="preflight",
                reason="filesystem mediator currently supports only write_file",
            )
        if "path" not in contract.binding or "content" not in contract.binding:
            self._refuse(
                request_id=rid,
                contract=contract,
                phase="preflight",
                reason="write_file contract must bind both path and content exactly",
            )

        try:
            logical = _safe_relative_path(contract.binding["path"])
            expected = _expected_bytes(contract.binding["content"])
        except ValueError as error:
            self._refuse(
                request_id=rid,
                contract=contract,
                phase="preflight",
                reason=str(error),
            )

        preflight = contract.check(EffectProposal(operation, dict(request_arguments)))
        if not preflight.allowed:
            self._refuse(
                request_id=rid,
                contract=contract,
                phase="request-shape",
                reason=str(preflight),
            )

        prior = self.allowance.reserve(
            contract.contract_id, rid, contract.max_invocations
        )
        if prior is not None:
            if prior.state is SlotState.COMMITTED:
                if not prior.result_available:
                    raise AllowanceError(
                        f"request {rid} committed before restart, but its result "
                        "is unavailable; reconcile trusted state without "
                        "re-executing the server"
                    )
                if isinstance(prior.result, MediationResult):
                    return prior.result
                if isinstance(prior.result, Mapping):
                    try:
                        return MediationResult(**dict(prior.result))
                    except TypeError as error:
                        raise AllowanceError(
                            f"request {rid} has an invalid durable result: {error}"
                        ) from error
                raise AllowanceError(
                    f"request {rid} has an unrecognized durable result; "
                    "do not re-execute it"
                )
            if prior.state is SlotState.FAILED:
                raise AllowanceError(
                    f"request {rid} already failed after execution began: {prior.error}"
                )
            raise AllowanceError(
                f"request {rid} is still RESERVED; reconcile real state before retrying"
            )

        staging: Path | None = None
        response: Any = None
        try:
            staging = self._stage_for(contract.contract_id, rid)
            if self.prepare_staging is not None:
                self.prepare_staging(staging)

            invocation = runner(staging, operation, dict(request_arguments))
            if not isinstance(invocation, StagedInvocation):
                raise TypeError("runner must return StagedInvocation")
            response = invocation.response

            if not invocation.boundary_closed:
                self._refuse(
                    request_id=rid,
                    contract=contract,
                    phase="freeze",
                    reason=(
                        "runner did not attest that all staging writers were closed; "
                        "a stable snapshot is not available"
                    ),
                    staging=staging,
                    response=response,
                    spent=True,
                )

            postflight = contract.check(
                EffectProposal(operation, dict(invocation.actual_arguments))
            )
            if not postflight.allowed:
                self._refuse(
                    request_id=rid,
                    contract=contract,
                    phase="transport-shape",
                    reason=str(postflight),
                    staging=staging,
                    response=response,
                    spent=True,
                )

            snapshot = _snapshot_tree(
                staging, logical.as_posix(), approved_size=len(expected)
            )
            allowed_directories = {
                PurePosixPath(*logical.parts[:index]).as_posix()
                for index in range(1, len(logical.parts))
            }
            problems: list[str] = []
            if snapshot.symlinks:
                problems.append(f"symbolic links present: {list(snapshot.symlinks)}")
            if snapshot.hardlinks:
                problems.append(
                    f"multiply-linked files present: {list(snapshot.hardlinks)}"
                )
            if snapshot.special:
                problems.append(f"special files present: {list(snapshot.special)}")
            if snapshot.size_mismatches:
                problems.append(
                    f"approved file size changed: {list(snapshot.size_mismatches)}"
                )
            extra_dirs = set(snapshot.directories) - allowed_directories
            if extra_dirs:
                problems.append(f"unapproved directories present: {sorted(extra_dirs)}")
            if set(snapshot.file_names) != {logical.as_posix()}:
                problems.append(
                    "staged file set differs from the single approved path: "
                    f"{sorted(snapshot.file_names)}"
                )
            elif logical.as_posix() not in snapshot.files:
                problems.append("approved file was not safely materialized")
            elif snapshot.files[logical.as_posix()] != expected:
                problems.append("staged bytes differ from the bound content")

            if problems:
                self._refuse(
                    request_id=rid,
                    contract=contract,
                    phase="effect-diff",
                    reason="; ".join(problems),
                    staging=staging,
                    response=response,
                    spent=True,
                )

            # Commit the materialized bytes, never a second read from staging.
            committed = self._atomic_commit(logical, snapshot.files[logical.as_posix()])
            result = MediationResult(
                request_id=rid,
                contract_id=contract.contract_id,
                committed_path=str(committed),
                bytes_committed=len(expected),
                sha256=hashlib.sha256(expected).hexdigest(),
                server_response=response,
            )
            self.allowance.commit(contract.contract_id, rid, result)
            self._record(
                MediationRecord(
                    request_id=rid,
                    contract_id=contract.contract_id,
                    decision="COMMITTED",
                    phase="commit",
                    reason="request shape and staged effect match the contract",
                    staging_root=str(staging),
                    committed_path=str(committed),
                    bytes_committed=len(expected),
                    server_response=response,
                )
            )
            return result
        except MediationRefused:
            raise
        except BaseException as error:
            # The slot was reserved.  Even setup/adapter failures remain spent:
            # the caller cannot prove that no effect occurred before the error.
            self.allowance.fail(
                contract.contract_id, rid, f"{type(error).__name__}: {error}"
            )
            record = MediationRecord(
                request_id=rid,
                contract_id=contract.contract_id,
                decision="FAILED",
                phase="execution",
                reason=f"{type(error).__name__}: {error}",
                staging_root=str(staging) if staging else None,
                server_response=response,
            )
            self._record(record)
            raise
        finally:
            self._cleanup(staging)

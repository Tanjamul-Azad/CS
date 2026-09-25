"""Generalized whole-tree effect mediation for multi-file workflows.

The exact-write mediator is intentionally strict and supports one known file.
Real MCP workflows may create several files, generated names, JSON records, or
DOCX archives. This module admits such workflows through declarative path and
content rules while preserving three fail-closed properties:

1. every changed filesystem object must match exactly one frozen rule;
2. the complete tree is snapshotted only after all writers terminate; and
3. the validated directory itself is promoted, so commit does not re-read
   attacker-controlled bytes.

The initial implementation promotes into a previously absent trusted path. It
does not claim atomic replacement of an existing non-empty tree.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import threading
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from .allowance import AllowanceError, AllowanceLedger, SlotState
from .contract import EffectContract, EffectProposal
from .mediator import StagedInvocation


@dataclass(frozen=True)
class TreeEntry:
    kind: str
    size: int = 0
    sha256: str | None = None
    content: bytes | None = field(default=None, repr=False)


@dataclass(frozen=True)
class TreeSnapshot:
    entries: Mapping[str, TreeEntry]
    canonical: str = field(default="", compare=False, repr=False)
    sha256: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        frozen = MappingProxyType(dict(sorted(self.entries.items())))
        object.__setattr__(self, "entries", frozen)
        canonical = json.dumps(
            {
                path: {
                    "kind": entry.kind,
                    "size": entry.size,
                    "sha256": entry.sha256,
                }
                for path, entry in frozen.items()
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        object.__setattr__(self, "canonical", canonical)
        object.__setattr__(self, "sha256", hashlib.sha256(canonical.encode()).hexdigest())


@dataclass(frozen=True)
class TreeChange:
    path: str
    operation: str
    before: TreeEntry | None
    after: TreeEntry | None


def snapshot_tree(
    root: Path,
    *,
    max_entries: int = 4096,
    max_file_bytes: int = 16 * 1024 * 1024,
    max_total_bytes: int = 64 * 1024 * 1024,
) -> TreeSnapshot:
    """Materialize a bounded, no-follow snapshot of a directory tree."""

    base = Path(root)
    if not base.is_dir() or base.is_symlink():
        raise ValueError("tree root must be a real directory")
    entries: dict[str, TreeEntry] = {}
    total_bytes = 0

    def add(path: str, entry: TreeEntry) -> None:
        if len(entries) >= max_entries:
            raise ValueError(f"tree exceeds {max_entries} entries")
        entries[path] = entry

    def walk(current: Path, prefix: str = "") -> None:
        nonlocal total_bytes
        with os.scandir(current) as children:
            for child in sorted(children, key=lambda item: item.name):
                relative = f"{prefix}/{child.name}" if prefix else child.name
                if child.is_symlink():
                    add(relative, TreeEntry("symlink"))
                    continue
                if child.is_dir(follow_symlinks=False):
                    add(relative, TreeEntry("directory"))
                    walk(Path(child.path), relative)
                    continue
                if child.is_file(follow_symlinks=False):
                    metadata = os.stat(child.path, follow_symlinks=False)
                    if metadata.st_nlink not in (0, 1):
                        add(relative, TreeEntry("hardlink", size=metadata.st_size))
                        continue
                    if metadata.st_size > max_file_bytes:
                        raise ValueError(
                            f"file {relative!r} exceeds {max_file_bytes} byte limit"
                        )
                    total_bytes += metadata.st_size
                    if total_bytes > max_total_bytes:
                        raise ValueError(
                            f"tree exceeds {max_total_bytes} materialized bytes"
                        )
                    with open(child.path, "rb") as handle:
                        content = handle.read(max_file_bytes + 1)
                    if len(content) != metadata.st_size:
                        raise ValueError(f"file changed while snapshotting: {relative}")
                    add(
                        relative,
                        TreeEntry(
                            "file",
                            size=len(content),
                            sha256=hashlib.sha256(content).hexdigest(),
                            content=content,
                        ),
                    )
                    continue
                add(relative, TreeEntry("special"))

    walk(base)
    return TreeSnapshot(entries)


def diff_trees(before: TreeSnapshot, after: TreeSnapshot) -> tuple[TreeChange, ...]:
    changes: list[TreeChange] = []
    for path in sorted(set(before.entries) | set(after.entries)):
        old = before.entries.get(path)
        new = after.entries.get(path)
        if old == new:
            continue
        if old is None:
            operation = "create"
        elif new is None:
            operation = "delete"
        elif old.kind != new.kind:
            operation = "replace"
        else:
            operation = "modify"
        changes.append(TreeChange(path, operation, old, new))
    return tuple(changes)


@dataclass(frozen=True)
class ContentPredicate:
    """A bounded content check for one changed regular file."""

    mode: str = "any"
    value: str | None = None

    def check(self, content: bytes) -> tuple[bool, str]:
        if self.mode == "any":
            return True, "content is explicitly unconstrained"
        if self.mode == "exact_sha256":
            observed = hashlib.sha256(content).hexdigest()
            return observed == self.value, f"sha256={observed}"
        if self.mode == "utf8_contains":
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError as error:
                return False, f"content is not UTF-8: {error}"
            return self.value in text, "required UTF-8 marker presence"
        if self.mode == "json_contains":
            try:
                decoded = json.loads(content.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                return False, f"content is not valid UTF-8 JSON: {error}"
            canonical = json.dumps(decoded, ensure_ascii=False, sort_keys=True)
            return self.value in canonical, "required marker in canonical JSON"
        if self.mode == "docx_xml_contains":
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                    text = "\n".join(
                        archive.read(name).decode("utf-8", errors="strict")
                        for name in sorted(archive.namelist())
                        if name.endswith(".xml")
                    )
            except (zipfile.BadZipFile, KeyError, UnicodeDecodeError) as error:
                return False, f"content is not a valid readable DOCX archive: {error}"
            return self.value in text, "required marker in DOCX XML"
        return False, f"unknown content predicate mode: {self.mode}"


@dataclass(frozen=True)
class PathRule:
    """One disjoint rule for changed paths in a whole-tree effect."""

    name: str
    pattern: str
    kinds: frozenset[str] = frozenset({"file"})
    operations: frozenset[str] = frozenset({"create", "modify"})
    min_matches: int = 0
    max_matches: int = 1
    content: ContentPredicate = field(default_factory=ContentPredicate)
    _compiled: re.Pattern[str] = field(init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("path rule name must not be empty")
        if self.min_matches < 0 or self.max_matches < self.min_matches:
            raise ValueError("invalid path-rule match bounds")
        object.__setattr__(self, "_compiled", re.compile(self.pattern))

    def matches_path(self, path: str) -> bool:
        return self._compiled.fullmatch(path) is not None


@dataclass(frozen=True)
class TreeVerdict:
    allowed: bool
    reason: str
    matched_counts: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class TreeEffectContract:
    request: EffectContract
    expected_before: TreeSnapshot
    rules: tuple[PathRule, ...]
    max_entries: int = 4096
    max_file_bytes: int = 16 * 1024 * 1024
    max_total_bytes: int = 64 * 1024 * 1024
    contract_id: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        canonical = json.dumps(
            {
                "request": self.request.canonical,
                "before": self.expected_before.sha256,
                "rules": [
                    {
                        "name": rule.name,
                        "pattern": rule.pattern,
                        "kinds": sorted(rule.kinds),
                        "operations": sorted(rule.operations),
                        "min_matches": rule.min_matches,
                        "max_matches": rule.max_matches,
                        "content_mode": rule.content.mode,
                        "content_value": rule.content.value,
                    }
                    for rule in self.rules
                ],
                "bounds": [
                    self.max_entries, self.max_file_bytes, self.max_total_bytes
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        object.__setattr__(
            self, "contract_id", hashlib.sha256(canonical.encode()).hexdigest()
        )

    def evaluate(self, after: TreeSnapshot) -> TreeVerdict:
        changes = diff_trees(self.expected_before, after)
        counts = {rule.name: 0 for rule in self.rules}
        problems: list[str] = []
        for change in changes:
            candidates = [rule for rule in self.rules if rule.matches_path(change.path)]
            if len(candidates) != 1:
                problems.append(
                    f"{change.path}: matched {len(candidates)} rules instead of exactly one"
                )
                continue
            rule = candidates[0]
            counts[rule.name] += 1
            if change.operation not in rule.operations:
                problems.append(
                    f"{change.path}: operation {change.operation} not allowed by {rule.name}"
                )
                continue
            observed = change.after if change.after is not None else change.before
            if observed is None or observed.kind not in rule.kinds:
                kind = observed.kind if observed is not None else "missing"
                problems.append(
                    f"{change.path}: kind {kind} not allowed by {rule.name}"
                )
                continue
            if change.after is not None and change.after.kind == "file":
                content = change.after.content
                if content is None:
                    problems.append(f"{change.path}: file bytes were not materialized")
                    continue
                content_ok, detail = rule.content.check(content)
                if not content_ok:
                    problems.append(
                        f"{change.path}: content failed {rule.name}: {detail}"
                    )
        for rule in self.rules:
            count = counts[rule.name]
            if not rule.min_matches <= count <= rule.max_matches:
                problems.append(
                    f"{rule.name}: expected {rule.min_matches}..{rule.max_matches} "
                    f"matches, observed {count}"
                )
        return TreeVerdict(
            allowed=not problems,
            reason="effect matches every tree rule" if not problems else "; ".join(problems),
            matched_counts=MappingProxyType(counts),
        )


@dataclass(frozen=True)
class TreeMediationRecord:
    request_id: str
    contract_id: str
    decision: str
    phase: str
    reason: str
    before_sha256: str | None = None
    after_sha256: str | None = None
    committed_root: str | None = None
    server_response: Any = None


@dataclass(frozen=True)
class TreeMediationResult:
    request_id: str
    contract_id: str
    committed_root: str
    before_sha256: str
    after_sha256: str
    matched_counts: Mapping[str, int]
    server_response: Any = None


class TreeMediationRefused(PermissionError):
    def __init__(self, record: TreeMediationRecord):
        self.record = record
        super().__init__(f"{record.decision} during {record.phase}: {record.reason}")


@dataclass
class TreeMediator:
    staging_base: Path
    committed_root: Path
    baseline_root: Path
    allowance: AllowanceLedger = field(default_factory=AllowanceLedger)
    keep_staging: bool = False
    records: list[TreeMediationRecord] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        self.staging_base = Path(self.staging_base)
        self.committed_root = Path(self.committed_root)
        self.baseline_root = Path(self.baseline_root)
        self.staging_base.mkdir(parents=True, exist_ok=True)
        if not self.baseline_root.is_dir():
            raise ValueError("baseline_root must exist and be a directory")
        self.committed_root.parent.mkdir(parents=True, exist_ok=True)

    def _refuse(
        self,
        rid: str,
        contract: TreeEffectContract,
        phase: str,
        reason: str,
        *,
        before: str | None = None,
        after: str | None = None,
        response: Any = None,
        spent: bool = False,
    ) -> None:
        if spent:
            self.allowance.fail(contract.contract_id, rid, reason)
        record = TreeMediationRecord(
            rid, contract.contract_id, "REFUSED", phase, reason,
            before, after, None, response,
        )
        self.records.append(record)
        raise TreeMediationRefused(record)

    def call(
        self,
        operation: str,
        request_arguments: dict[str, Any],
        *,
        contract: TreeEffectContract,
        runner: Any,
        request_id: str | None = None,
    ) -> TreeMediationResult:
        rid = request_id or uuid.uuid4().hex
        proposal = contract.request.check(EffectProposal(operation, request_arguments))
        if not proposal.allowed:
            self._refuse(rid, contract, "request-shape", str(proposal))

        with self._lock:
            existing = self.allowance.lookup(contract.contract_id, rid)
            if existing is not None:
                if existing.state is SlotState.COMMITTED and isinstance(
                    existing.result, TreeMediationResult
                ):
                    return existing.result
                if existing.state is SlotState.COMMITTED and isinstance(
                    existing.result, Mapping
                ):
                    return TreeMediationResult(**dict(existing.result))
                raise AllowanceError(
                    f"request {rid} cannot execute again because its state is "
                    f"{existing.state.value}"
                )

            baseline = snapshot_tree(
                self.baseline_root,
                max_entries=contract.max_entries,
                max_file_bytes=contract.max_file_bytes,
                max_total_bytes=contract.max_total_bytes,
            )
            if baseline != contract.expected_before:
                self._refuse(
                    rid, contract, "before-state",
                    "baseline tree differs from the contracted initial state",
                    before=baseline.sha256,
                )
            prior = self.allowance.reserve(
                contract.contract_id, rid, contract.request.max_invocations
            )
            if prior is not None:
                raise AllowanceError("request state changed while mediator lock was held")

            token = hashlib.sha256(
                f"{contract.contract_id}\0{rid}".encode()
            ).hexdigest()[:24]
            stage = self.staging_base / f"inv-{token}"
            shutil.copytree(self.baseline_root, stage)
            response: Any = None
            moved = False
            try:
                invocation = runner(stage, operation, dict(request_arguments))
                if not isinstance(invocation, StagedInvocation):
                    raise TypeError("runner must return StagedInvocation")
                response = invocation.response
                if not invocation.boundary_closed:
                    self._refuse(
                        rid, contract, "freeze",
                        "runner did not prove that every tree writer terminated",
                        before=baseline.sha256, response=response, spent=True,
                    )
                postflight = contract.request.check(
                    EffectProposal(operation, dict(invocation.actual_arguments))
                )
                if not postflight.allowed:
                    self._refuse(
                        rid, contract, "transport-shape", str(postflight),
                        before=baseline.sha256, response=response, spent=True,
                    )
                after = snapshot_tree(
                    stage,
                    max_entries=contract.max_entries,
                    max_file_bytes=contract.max_file_bytes,
                    max_total_bytes=contract.max_total_bytes,
                )
                dangerous = [
                    path for path, entry in after.entries.items()
                    if entry.kind in {"symlink", "hardlink", "special"}
                ]
                if dangerous:
                    self._refuse(
                        rid, contract, "effect-diff",
                        f"tree contains unsafe object types: {dangerous}",
                        before=baseline.sha256, after=after.sha256,
                        response=response, spent=True,
                    )
                verdict = contract.evaluate(after)
                if not verdict.allowed:
                    self._refuse(
                        rid, contract, "effect-diff", verdict.reason,
                        before=baseline.sha256, after=after.sha256,
                        response=response, spent=True,
                    )
                if self.committed_root.exists():
                    self._refuse(
                        rid, contract, "commit",
                        "trusted destination already exists; replacement is unsupported",
                        before=baseline.sha256, after=after.sha256,
                        response=response, spent=True,
                    )
                if os.stat(stage).st_dev != os.stat(self.committed_root.parent).st_dev:
                    raise OSError(
                        "staging and trusted destination must share a filesystem"
                    )
                os.replace(stage, self.committed_root)
                moved = True
                result = TreeMediationResult(
                    request_id=rid,
                    contract_id=contract.contract_id,
                    committed_root=str(self.committed_root),
                    before_sha256=baseline.sha256,
                    after_sha256=after.sha256,
                    matched_counts=verdict.matched_counts,
                    server_response=response,
                )
                self.allowance.commit(contract.contract_id, rid, result)
                self.records.append(
                    TreeMediationRecord(
                        rid, contract.contract_id, "COMMITTED", "commit",
                        "request and complete tree effect match the contract",
                        baseline.sha256, after.sha256,
                        str(self.committed_root), response,
                    )
                )
                return result
            except TreeMediationRefused:
                raise
            except BaseException as error:
                self.allowance.fail(
                    contract.contract_id, rid, f"{type(error).__name__}: {error}"
                )
                self.records.append(
                    TreeMediationRecord(
                        rid, contract.contract_id, "FAILED", "execution",
                        f"{type(error).__name__}: {error}",
                        baseline.sha256, None, None, response,
                    )
                )
                raise
            finally:
                if not self.keep_staging and not moved:
                    shutil.rmtree(stage, ignore_errors=True)


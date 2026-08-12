"""
Metamorphic relations and the audit engine.

This is the mechanism that answers the objection that killed the first
design: it needs NO cooperation from the server, NO cooperation from any
downstream provider, and NO independent observation channel. Every call
the auditor makes is a tool the client was already approved to use.

The client cannot know ground truth. It does not need to. It needs
relations between observations that must hold if the server is honest.
A server that diverts effects must then lie CONSISTENTLY across every
relation the client might check -- which means maintaining a shadow copy
of the honest world. That burden is the security argument, and it is
measurable.

See docs/11-runtime-validation-design.md.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class RelationKind(str, Enum):
    R1_WRITE_READ = "R1"      # a write must appear in a companion read
    R2_CONSERVATION = "R2"    # numeric quantities obey arithmetic
    R3_DETERMINISM = "R3"     # pure tools repeat themselves
    R4_NULL_OP = "R4"         # degenerate input changes nothing
    R5_CANARY = "R5"          # client-invented value must survive a round trip
    R6_CROSS_TOOL = "R6"      # overlapping reads must agree


@dataclass
class AuditFinding:
    violated: bool
    relation: RelationKind
    detail: str = ""

    def __bool__(self) -> bool:
        return self.violated


class Relation(ABC):
    """A predicate over a transcript fragment the client can produce itself."""

    kind: RelationKind
    tools: tuple[str, ...]

    @abstractmethod
    def check(self, call: Callable[[str, dict], Any], intent: dict) -> AuditFinding:
        """`call(tool, args)` issues a real tool call. `intent` is what the
        user actually asked for -- the auditor's reference point."""
        ...


# --------------------------------------------------------------------------
# R1 -- write-read consistency
# --------------------------------------------------------------------------

class WriteReadRelation(Relation):
    """After a write, a companion read must reflect what was requested.

    Catches recipient diversion: the money went to Bob, so unless the
    server also rewrites its own transaction log, the log shows Bob.
    """

    kind = RelationKind.R1_WRITE_READ

    def __init__(self, write_tool: str, read_tool: str, match_fields: tuple[str, ...]):
        self.write_tool, self.read_tool = write_tool, read_tool
        self.match_fields = match_fields
        self.tools = (write_tool, read_tool)

    def check(self, call, intent) -> AuditFinding:
        records = call(self.read_tool, {}) or []
        for rec in records:
            if all(rec.get(f) == intent.get(f) for f in self.match_fields):
                return AuditFinding(False, self.kind, "write observed in read-back")
        return AuditFinding(
            True, self.kind,
            f"no record in {self.read_tool} matching "
            + ", ".join(f"{f}={intent.get(f)!r}" for f in self.match_fields),
        )


# --------------------------------------------------------------------------
# R2 -- conservation
# --------------------------------------------------------------------------

class ConservationRelation(Relation):
    """A monitored quantity must move by exactly the requested delta.

    Catches amount inflation (server sends 500 while the user asked for
    100). Does NOT catch pure recipient diversion -- the balance falls by
    the same amount either way. Different relations cover different
    attacks; that is why relation DEGREE matters, not just presence.
    """

    kind = RelationKind.R2_CONSERVATION

    def __init__(self, read_tool: str, quantity: str, delta_field: str, sign: int = -1):
        self.read_tool, self.quantity = read_tool, quantity
        self.delta_field, self.sign = delta_field, sign
        self.tools = (read_tool,)

    def before(self, call) -> float:
        return float(call(self.read_tool, {})[self.quantity])

    def check_delta(self, before: float, after: float, intent: dict) -> AuditFinding:
        expected = before + self.sign * float(intent[self.delta_field])
        if abs(after - expected) > 1e-9:
            return AuditFinding(
                True, self.kind,
                f"{self.quantity}: expected {expected}, observed {after}",
            )
        return AuditFinding(False, self.kind, "conservation holds")

    def check(self, call, intent) -> AuditFinding:  # pragma: no cover
        raise NotImplementedError("use before()/check_delta() around the write")


# --------------------------------------------------------------------------
# R5 -- canary round trip
# --------------------------------------------------------------------------

class CanaryRelation(Relation):
    """Write a value only the client just invented; read it back.

    Forces shadow state to be content-accurate rather than merely
    structurally plausible. A server synthesizing responses must actually
    store the nonce to survive this.
    """

    kind = RelationKind.R5_CANARY

    def __init__(self, write_tool: str, read_tool: str, canary_field: str):
        self.write_tool, self.read_tool = write_tool, read_tool
        self.canary_field = canary_field
        self.tools = (write_tool, read_tool)

    def check(self, call, intent) -> AuditFinding:
        nonce = f"audit-{uuid.uuid4().hex[:8]}"
        call(self.write_tool, {**intent, self.canary_field: nonce})
        records = call(self.read_tool, {}) or []
        if any(r.get(self.canary_field) == nonce for r in records):
            return AuditFinding(False, self.kind, "canary survived round trip")
        return AuditFinding(True, self.kind, f"canary {nonce} not found in read-back")


# --------------------------------------------------------------------------
# Relation derivation from declarations
# --------------------------------------------------------------------------

WRITE_VERBS = ("send", "transfer", "write", "create", "delete", "post", "update", "set")
READ_VERBS = ("list", "get", "read", "search", "check", "fetch", "query")


def _verb(name: str) -> str:
    return name.split("_")[0].lower()


def _noun(name: str) -> str:
    parts = name.split("_")
    return parts[-1].lower() if len(parts) > 1 else name.lower()


def derive_relations(declarations: list) -> list[Relation]:
    """Derive relations from tool declarations alone.

    This is the step that makes the approach deployable at ecosystem
    scale: nobody hand-writes relations for thousands of third-party
    tools. The client derives them from what MCP already gives it.

    Deliberately conservative -- a false relation produces a false
    positive, which is far more damaging to a security tool than a missed
    one. Recall is traded for precision on purpose.
    """
    rels: list[Relation] = []
    writes = [d for d in declarations if _verb(d.name) in WRITE_VERBS]
    reads = [d for d in declarations if _verb(d.name) in READ_VERBS]

    for w in writes:
        w_fields = set(w.input_schema.get("properties", {}))
        for r in reads:
            # R1: pair a write with a read whose noun overlaps.
            if _noun(w.name) in r.name.lower() or _noun(r.name) in w.name.lower() \
               or _shares_resource(w, r):
                match = tuple(sorted(w_fields & _readable_fields(r)))
                if match:
                    rels.append(WriteReadRelation(w.name, r.name, match))

    return rels


def _readable_fields(decl) -> set[str]:
    """Fields a read tool is declared to return.

    MCP does not mandate output schemas, so this falls back to a
    description scan. The gap is itself a finding: clients cannot tell
    what a tool returns, which caps how many relations are derivable --
    and that cap is part of the ecosystem measurement.
    """
    declared = getattr(decl, "output_fields", None)
    if declared:
        return set(declared)
    return set()


def _shares_resource(a, b) -> bool:
    a_words = set(a.name.lower().split("_")) | set(a.description.lower().split())
    b_words = set(b.name.lower().split("_")) | set(b.description.lower().split())
    return len(a_words & b_words & _RESOURCE_WORDS) > 0


_RESOURCE_WORDS = {
    "transaction", "transactions", "transfer", "balance", "account",
    "email", "mail", "message", "inbox", "file", "files", "record",
}


# --------------------------------------------------------------------------
# Auditability classification
# --------------------------------------------------------------------------

def relation_degree(tool_name: str, relations: list[Relation]) -> int:
    return sum(1 for r in relations if tool_name in r.tools)


def auditability_class(tool_name: str, relations: list[Relation]) -> str:
    """A0-A3. See docs/05-verifiability-taxonomy.md section 5."""
    kinds = {r.kind for r in relations if tool_name in r.tools}
    if not kinds:
        return "A0"  # unrelatable -- undetectable at any cost
    if kinds & {RelationKind.R2_CONSERVATION, RelationKind.R6_CROSS_TOOL}:
        return "A3"
    if kinds & {RelationKind.R1_WRITE_READ, RelationKind.R5_CANARY}:
        return "A2"
    return "A1"


# --------------------------------------------------------------------------
# The auditor
# --------------------------------------------------------------------------

@dataclass
class Auditor:
    """Runs relation checks against a live (untrusted) server.

    `budget` caps audit calls per task so overhead stays measurable --
    the detection-vs-cost curve is the systems result (figure F6).
    """

    relations: list[Relation]
    rng: Any = None
    budget: int = 4
    findings: list[AuditFinding] = field(default_factory=list)

    def __post_init__(self):
        if self.rng is None:
            import random
            self.rng = random.Random(0xA11D17)

    def audit(self, call, intent: dict, tool: str) -> list[AuditFinding]:
        """Check relations involving `tool`, randomized and budget-capped.

        Randomization is not cosmetic: a deterministic audit schedule is
        one a T3 adversary learns and evades.
        """
        applicable = [r for r in self.relations if tool in r.tools]
        self.rng.shuffle(applicable)
        out = []
        for rel in applicable[: self.budget]:
            try:
                out.append(rel.check(call, intent))
            except NotImplementedError:
                continue  # R2 is driven around the write, not from here
        self.findings.extend(out)
        return out

    @property
    def detected(self) -> bool:
        return any(f.violated for f in self.findings)

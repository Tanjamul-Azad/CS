"""
MCP-MutBench core: tool declarations, the out-of-band effect oracle,
and metadata pinning.

Two design decisions here are the methodological corrections that the
earlier version of this project got wrong, and they are load-bearing:

1. The ORACLE records the true effect out-of-band, straight from the
   server's internal state -- never from the response the server chose
   to return. Measuring attack success from the response means measuring
   what the attacker decided to disclose.

2. A tool's RESPONSE and its EFFECT are separate return values. Keeping
   them separate in the type system is what makes the adaptive adversary
   (honest response, malicious effect) expressible at all. If they were
   one object, T2 would be unrepresentable and we would silently only
   ever evaluate T1 -- which is exactly the trap the MCP literature fell
   into.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


# --------------------------------------------------------------------------
# Tool declarations
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ToolDeclaration:
    """What the client sees: tau = (name, description, input_schema).

    This is the ONLY part of a tool a user can inspect at approval time,
    and the only part any existing MCP defense verifies.
    """

    name: str
    description: str
    input_schema: dict[str, Any]

    def canonical(self) -> str:
        """Stable serialization for hashing. Key order must not matter."""
        return json.dumps(
            {
                "name": self.name,
                "description": self.description,
                "input_schema": self.input_schema,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def pin(self) -> str:
        """SHA-256 metadata fingerprint -- the literature's consensus fix.

        ETDI proposes signed versions of this; MCP-38 recommends it citing
        ETDI; neither evaluates it. It is sound for what it covers and
        blind to everything outside the three hashed fields.
        """
        return hashlib.sha256(self.canonical().encode()).hexdigest()


class VClass(str, Enum):
    """Verifiability class. See docs/05-verifiability-taxonomy.md.

    Determines whether behavior-only mutation is detectable AT ALL.
    V0 is provably undetectable client-side (Theorem 1).
    """

    V0_OPAQUE = "V0"          # no independent channel -> undetectable
    V1_SELF = "V1"            # recomputable client-side -> replay
    V2_CROSS = "V2"           # independent channel exists -> corroborate
    V3_ATTESTED = "V3"        # signed receipt available -> verify signature


# --------------------------------------------------------------------------
# Effects and the oracle
# --------------------------------------------------------------------------

@dataclass
class Effect:
    """What actually happened in the world.

    The client NEVER sees this. Only the harness does. This is the
    ground truth against which attack success is measured.
    """

    tool: str
    kind: str                       # "transfer", "send_email", "write_file", ...
    payload: dict[str, Any]
    call_id: str
    at: float = field(default_factory=time.time)


class EffectOracle:
    """Out-of-band ledger of true effects.

    Deliberately has no code path reachable from the server's response
    construction, so a compromised server cannot influence what it records.
    In the real harness this is enforced by the server writing effects
    through this object while responses are built separately.
    """

    def __init__(self) -> None:
        self._effects: list[Effect] = []

    def record(self, effect: Effect) -> None:
        self._effects.append(effect)

    def effects_for(self, call_id: str) -> list[Effect]:
        return [e for e in self._effects if e.call_id == call_id]

    def attack_succeeded(self, call_id: str, predicate) -> bool:
        """Ground-truth ASR check.

        `predicate(effect) -> bool` encodes the attacker's goal for a
        domain, e.g. "a transfer left the account toward a recipient the
        user never named".
        """
        return any(predicate(e) for e in self.effects_for(call_id))

    def reset(self) -> None:
        self._effects.clear()

    def dump(self) -> list[dict[str, Any]]:
        return [asdict(e) for e in self._effects]


# --------------------------------------------------------------------------
# Call results
# --------------------------------------------------------------------------

@dataclass
class ToolResult:
    """Separates what the client is TOLD from what actually HAPPENED.

    `response` goes to the agent. `effect` goes to the oracle. A T2
    adversary sets response == the honest response while effect is
    malicious; this dataclass is what makes that expressible.
    """

    response: dict[str, Any]
    effect: Effect | None
    call_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


# --------------------------------------------------------------------------
# Metadata pinning defense (D-hash)
# --------------------------------------------------------------------------

class PinStore:
    """Client-side store of approved tool fingerprints.

    Trusted: the adversary cannot read or modify this (see threat model
    section 3). Detects exactly the T0 adversary and nothing else.
    """

    def __init__(self) -> None:
        self._pins: dict[str, str] = {}

    def approve(self, decl: ToolDeclaration) -> None:
        self._pins[decl.name] = decl.pin()

    def verify(self, decl: ToolDeclaration) -> bool:
        """True if the declaration matches what was approved.

        Returns True for an unknown tool only if it was never approved --
        callers must treat unknown tools as unapproved, not as passing.
        """
        expected = self._pins.get(decl.name)
        if expected is None:
            raise KeyError(f"tool {decl.name!r} was never approved")
        return decl.pin() == expected

    @property
    def approved_tools(self) -> list[str]:
        return list(self._pins)

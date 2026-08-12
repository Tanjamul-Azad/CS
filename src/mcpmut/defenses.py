"""
Defense conditions D-none, D-hash, D-resp, D-bim.

D-resp is the naive response validator -- the defense this project
originally proposed and the one the MCP literature implicitly assumes.
It is implemented here faithfully and honestly so that we can show it
collapsing against T2. Demonstrating the failure of our own earlier
design is the most credible move available to us.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

from .core import PinStore, ToolDeclaration, ToolResult, VClass


@dataclass
class Verdict:
    blocked: bool
    reason: str = ""
    detector: str = ""


class Defense(ABC):
    name: str

    @abstractmethod
    def check(
        self,
        decl: ToolDeclaration,
        args: dict[str, Any],
        result: ToolResult,
        ctx: dict[str, Any] | None = None,
    ) -> Verdict:
        ...


class NoDefense(Defense):
    name = "D-none"

    def check(self, decl, args, result, ctx=None) -> Verdict:
        return Verdict(blocked=False)


class HashPinDefense(Defense):
    """SHA-256 pin over (name, description, schema).

    Sound and complete for T0. Structurally blind to T1+ -- the hash is
    computed over fields the behavior-only adversary never touches.
    """

    name = "D-hash"

    def __init__(self, pins: PinStore) -> None:
        self.pins = pins

    def check(self, decl, args, result, ctx=None) -> Verdict:
        if not self.pins.verify(decl):
            return Verdict(True, "metadata fingerprint mismatch", self.name)
        return Verdict(False, detector=self.name)


class ResponseValidator(Defense):
    """Compare requested arguments against the observed response.

    Catches T1. Provably useless against T2 -- see Theorem 1. We keep it
    to quantify exactly how useless, and to make the point that a defense
    can look excellent against a strawman adversary.
    """

    name = "D-resp"

    def __init__(self, watched_fields: tuple[str, ...] = ("recipient", "amount")) -> None:
        self.watched_fields = watched_fields

    def check(self, decl, args, result, ctx=None) -> Verdict:
        observed = result.response or {}
        for f in self.watched_fields:
            if f in args and f in observed and args[f] != observed[f]:
                return Verdict(
                    True,
                    f"field {f!r}: requested {args[f]!r}, observed {observed[f]!r}",
                    self.name,
                )
        return Verdict(False, detector=self.name)


class BIM(Defense):
    """Behavioral Integrity Monitor -- class-aware.

    Routes each call to the check its verifiability class admits:
      V1 -> deterministic replay (sampled)
      V2 -> cross-source corroboration, with an INDEPENDENCE CHECK
      V3 -> receipt signature verification
      V0 -> no detection possible; policy escalation only

    The independence check is what separates real V2 from pseudo-V2. If
    the corroborating tool is served by the same server, corroboration is
    worthless and BIM must degrade the tool to V0 rather than report a
    false sense of safety. Getting this wrong would make BIM itself an
    instance of the mistake the paper is about.
    """

    name = "D-bim"

    def __init__(
        self,
        classify: Callable[[ToolDeclaration], VClass],
        replayer: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
        corroborator: Callable[[str, dict[str, Any]], dict[str, Any] | None] | None = None,
        receipt_verifier: Callable[[ToolResult], bool] | None = None,
        server_of: Callable[[str], str] | None = None,
        replay_rate: float = 0.25,
        rng=None,
    ) -> None:
        self.classify = classify
        self.replayer = replayer
        self.corroborator = corroborator
        self.receipt_verifier = receipt_verifier
        self.server_of = server_of
        self.replay_rate = replay_rate
        if rng is None:
            import random
            rng = random.Random(0xC0FFEE)
        self.rng = rng

    def check(self, decl, args, result, ctx=None) -> Verdict:
        vclass = self.classify(decl)
        ctx = ctx or {}

        if vclass is VClass.V1_SELF and self.replayer is not None:
            if self.rng.random() < self.replay_rate:
                expected = self.replayer(decl.name, args)
                if expected != (result.response or {}):
                    return Verdict(True, "replay mismatch", "BIM/V1")
            return Verdict(False, detector="BIM/V1")

        if vclass is VClass.V2_CROSS and self.corroborator is not None:
            # Independence check FIRST -- a corroborating tool on the same
            # server tells us nothing (pseudo-V2).
            witness_tool = ctx.get("witness_tool")
            if self.server_of is not None and witness_tool is not None:
                if self.server_of(decl.name) == self.server_of(witness_tool):
                    return Verdict(
                        False,
                        "pseudo-V2: witness shares server; degraded to V0",
                        "BIM/V2-degraded",
                    )
            observed = self.corroborator(decl.name, args)
            if observed is not None and observed != (result.response or {}):
                return Verdict(True, "corroboration mismatch", "BIM/V2")
            return Verdict(False, detector="BIM/V2")

        if vclass is VClass.V3_ATTESTED and self.receipt_verifier is not None:
            if not self.receipt_verifier(result):
                return Verdict(True, "receipt verification failed", "BIM/V3")
            return Verdict(False, detector="BIM/V3")

        # V0 -- Theorem 1. Nothing to check. Policy lives outside the
        # detector and is evaluated separately as risk reduction.
        return Verdict(False, "V0: no client-side check exists", "BIM/V0")


class CompositeDefense(Defense):
    """Run several defenses; block if any blocks. Used for D-bim+hash."""

    def __init__(self, *defenses: Defense) -> None:
        self.defenses = defenses
        self.name = "+".join(d.name for d in defenses)

    def check(self, decl, args, result, ctx=None) -> Verdict:
        for d in self.defenses:
            v = d.check(decl, args, result, ctx)
            if v.blocked:
                return v
        return Verdict(False, detector=self.name)

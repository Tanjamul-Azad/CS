"""
Effect contracts -- what the client approved, in a form a gateway can check.

WHY THIS EXISTS. The measurement half of this project establishes that a
client cannot reliably verify, after the fact, what an untrusted MCP
server actually did: over 1,242 real third-party servers, no detector
configuration reached a usable operating point, and 25.3% of servers offer
no observation channel that could support one at any budget. Detection
does not work because the server is simultaneously the actor and the only
witness.

The constructive response is to stop asking the server what it did.
Instead the server loses the authority to do it: it may only PROPOSE an
effect, and a client-controlled gateway decides whether that proposal
matches what the user approved and, if so, performs it itself.

An EffectContract is the object that makes "matches what the user
approved" checkable rather than a matter of opinion. It records the
operation, the fields whose values are the effect's identity (where it
lands), and bounds on anything the server is legitimately allowed to
choose.

WHAT THIS DOES NOT SOLVE, stated up front because it is the honest limit
of the design: the contract has to come from somewhere. In this prototype
the calling agent supplies it directly, which sidesteps the hard problem.
Deriving a contract from a user's natural-language instruction is itself
an attack surface -- an injected instruction that corrupts the contract
defeats the gateway completely -- and that derivation is the open research
question this architecture raises rather than answers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EffectProposal:
    """What the server says it wants to do.

    Deliberately inert: a proposal performs nothing. It is data handed to
    the gateway, which is the only component holding the capability to act.
    """

    operation: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        args = ", ".join(f"{k}={v!r}" for k, v in sorted(self.arguments.items()))
        return f"{self.operation}({args})"


@dataclass(frozen=True)
class Verdict:
    """Why a proposal was allowed or refused.

    Carries the reason, not just a boolean, because "refused" is the
    output a user has to act on and "the server tried to write somewhere
    else" is a different event from "this operation is not permitted here".
    """

    allowed: bool
    reason: str
    violated_field: str | None = None
    expected: Any = None
    proposed: Any = None

    def __str__(self) -> str:
        if self.allowed:
            return f"ALLOW  {self.reason}"
        if self.violated_field is None:
            return f"REFUSE {self.reason}"
        return (f"REFUSE {self.reason}: {self.violated_field} "
                f"expected {self.expected!r}, proposed {self.proposed!r}")


@dataclass(frozen=True)
class EffectContract:
    """The bound within which a server's proposal is acceptable.

    Three kinds of field, because they need different rules:

      `binding`   values that decide WHERE the effect lands -- a path, a
                  recipient, a repository. These must match exactly. Every
                  attack this project measured on real servers is a
                  divergence in one of these, so an approximate match here
                  would defeat the whole mechanism.

      `bounded`   values the server may legitimately choose within a
                  limit -- a count, a size. Checked against the bound.

      `free`      values the server may choose freely -- formatting,
                  ordering. Recorded so that "free" is an explicit
                  decision rather than an unlisted field slipping through.

    A field the contract does not mention is REFUSED, not ignored. An
    allowlist is the only safe default: an unmentioned `bcc` is exactly how
    a hidden extra effect gets through, and that is a documented real
    incident shape rather than a hypothetical.
    """

    operation: str
    binding: dict[str, Any] = field(default_factory=dict)
    bounded: dict[str, tuple[Any, Any]] = field(default_factory=dict)
    free: frozenset[str] = frozenset()
    max_invocations: int = 1

    def check(self, proposal: EffectProposal) -> Verdict:
        if proposal.operation != self.operation:
            return Verdict(False, "operation not the one approved",
                           "operation", self.operation, proposal.operation)

        for name, expected in self.binding.items():
            if name not in proposal.arguments:
                return Verdict(False, "binding field missing from proposal",
                               name, expected, None)
            proposed = proposal.arguments[name]
            if proposed != expected:
                return Verdict(False, "effect would land elsewhere",
                               name, expected, proposed)

        for name, (lo, hi) in self.bounded.items():
            if name not in proposal.arguments:
                continue                      # absent means the default
            v = proposal.arguments[name]
            try:
                out_of_range = not (lo <= v <= hi)
            except TypeError:
                return Verdict(False, "bounded field is not comparable",
                               name, (lo, hi), v)
            if out_of_range:
                return Verdict(False, "bounded field outside approved range",
                               name, (lo, hi), v)

        # Allowlist. Anything the contract does not name is refused --
        # this is the check that stops a silently added recipient.
        known = set(self.binding) | set(self.bounded) | set(self.free)
        for name in proposal.arguments:
            if name not in known:
                return Verdict(False, "proposal adds an unapproved field",
                               name, None, proposal.arguments[name])

        return Verdict(True, "proposal matches the approved effect")


def contract_from_call(operation: str, args: dict[str, Any],
                       binding_fields: set[str]) -> EffectContract:
    """Build a contract from the call the agent actually intended.

    This is the prototype's stand-in for intent extraction: the agent
    already knows what it asked for, so its own request is the approved
    effect. It is honest for measuring what the gateway prevents, and it
    is NOT a solution to deriving intent from natural language -- see this
    module's docstring.
    """
    return EffectContract(
        operation=operation,
        binding={k: v for k, v in args.items() if k in binding_fields},
        free=frozenset(k for k in args if k not in binding_fields),
    )

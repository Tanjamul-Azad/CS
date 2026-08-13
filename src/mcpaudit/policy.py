"""
Policy: what to do about a tool given what can be verified about it.

The auditability class is not a score. It is a statement about what is
possible. A0 does not mean "risky", it means "no amount of client-side
checking will ever detect compromise here" -- so the only lever left is
whether you allow the call at all, and under whose supervision.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Action(str, Enum):
    ALLOW = "allow"           # proceed, no audit possible or needed
    AUDIT = "audit"           # proceed, verify afterwards
    CONFIRM = "confirm"       # ask a human first
    DENY = "deny"             # refuse


@dataclass(frozen=True)
class Rule:
    action: Action
    reason: str


@dataclass
class Policy:
    """Per-class rules, plus an override for self-declared destructiveness."""

    a0: Rule
    a1: Rule
    a2: Rule
    a3: Rule
    # Applied when a tool is A0 *and* is believed to mutate state. This is
    # the genuinely dangerous cell: consequential and unverifiable.
    a0_writes: Rule
    audit_budget: float = 0.25   # max audit calls per task call

    @classmethod
    def default(cls) -> "Policy":
        """Deliberately conservative on the one cell that cannot be checked."""
        return cls(
            a0=Rule(Action.ALLOW,
                    "no relations derivable; nothing to verify, but "
                    "read-only so exposure is limited"),
            a1=Rule(Action.AUDIT, "determinism / null-op checks available"),
            a2=Rule(Action.AUDIT, "write-read or canary round-trip available"),
            a3=Rule(Action.AUDIT, "conservation invariant available"),
            a0_writes=Rule(Action.CONFIRM,
                           "mutates state AND admits no verification: "
                           "compromise here is undetectable by any audit"),
        )

    @classmethod
    def permissive(cls) -> "Policy":
        p = cls.default()
        p.a0_writes = Rule(Action.ALLOW, "policy set to permissive")
        return p

    @classmethod
    def strict(cls) -> "Policy":
        p = cls.default()
        p.a0_writes = Rule(Action.DENY,
                           "strict mode refuses unverifiable mutations")
        p.audit_budget = 1.0
        return p

    def rule_for(self, a_class: str, mutates: bool) -> Rule:
        if a_class == "A0":
            return self.a0_writes if mutates else self.a0
        return {"A1": self.a1, "A2": self.a2, "A3": self.a3}[a_class]

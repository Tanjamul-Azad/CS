"""
Shared scaffolding for benchmark domains.

Every domain supplies the same thing: a tools/list payload, an honest
server, and a ladder of compromised servers that all commit the SAME
malicious effect while differing only in how much machinery they run to
stay consistent under audit.

Keeping the ladder identical in shape across domains is what makes the
cost curve comparable. If banking's rungs meant something different from
email's, the LOC numbers could not be put on one axis.

Rungs (see docs/11):
  L0  honest
  L1  forge the response only          -- defeats response inspection
  L2  + shadow the record a read returns -- defeats R1 write-read
  L3  + shadow the conserved quantity    -- defeats R2 conservation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..core import Effect, EffectOracle

ATTACKER = "attacker"


@dataclass
class Server:
    """A tool server. `loc` counts attacker code beyond the honest baseline."""

    oracle: EffectOracle
    loc: int = 0

    def call(self, tool: str, args: dict[str, Any]) -> Any:
        raise NotImplementedError

    def _record(self, tool: str, kind: str, payload: dict) -> None:
        self.oracle.record(Effect(tool, kind, dict(payload), call_id="live"))


@dataclass
class Domain:
    """One benchmark domain."""

    name: str
    tools: list[dict]
    honest: Callable[[EffectOracle], Server]
    # (rung label, LOC, factory)
    ladder: list[tuple[str, int, Callable[[EffectOracle], Server]]]
    task_tool: str
    task_args: dict[str, Any]
    # benign calls used to measure false positives on an honest server
    benign_calls: list[tuple[str, dict]] = field(default_factory=list)
    attack_succeeded: Callable[[Effect], bool] = lambda e: False
    # Legitimate background activity, for realistic false-positive testing.
    noise_fn: Callable[[Server], None] | None = None


@dataclass
class NoisyHonest(Server):
    """An honest server with legitimate concurrent activity.

    This is the realistic false-positive source, and the objection any
    reviewer will raise first: a conservation check compares a quantity
    before and after the agent's write, but in production something else
    -- another client, a scheduled job, a human -- may move that quantity
    in between. The server is entirely honest; the invariant still fails.

    Measuring FPR against a deterministic single-client server is not a
    measurement, it is a tautology. This wraps an honest server and lets
    unrelated legitimate activity happen between calls.
    """

    inner: Server | None = None
    noise_rate: float = 0.0        # probability of background activity per call
    noise_fn: Any = None           # (server) -> None, applies legitimate change
    _rng: Any = None

    def call(self, tool: str, args: dict[str, Any]) -> Any:
        out = self.inner.call(tool, args)
        if self.noise_fn and self._rng and self._rng.random() < self.noise_rate:
            self.noise_fn(self.inner)
        return out

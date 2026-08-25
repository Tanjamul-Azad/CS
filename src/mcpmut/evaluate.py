"""
Evaluation harness: does the defense actually work?

Runs every (domain x adversary x defense) cell and reports the four
numbers that decide whether this is a usable defense rather than a
plausible story.

  ASR   attack success rate -- measured from the out-of-band oracle,
        NEVER from the server's response. The response is exactly what
        the adversary controls, so measuring success from it measures
        what the attacker chose to disclose.
  DR    detection rate -- of the runs where the attack succeeded, how
        many did the defense flag?
  FPR   false positive rate -- how often does the defense cry wolf on a
        fully honest server? For a security tool this matters at least
        as much as DR. A detector with FPR 20% is unusable at any DR.
  OVH   overhead -- extra tool calls the defense issues per task call.

Note that ASR is expected to be 100% for every compromised server: these
adversaries always succeed at the effect. The defense does not prevent
the effect, it DETECTS it. Conflating the two is the mistake this harness
is built to avoid.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcpaudit import Auditor, Policy  # noqa: E402

from .core import EffectOracle, ToolDeclaration  # noqa: E402
from .domains.base import Domain, NoisyHonest, Server  # noqa: E402


# --------------------------------------------------------------------------
# Defenses under comparison
# --------------------------------------------------------------------------

class Defense:
    name = "none"

    def __init__(self, tools: list[dict]):
        self.tools = tools
        self.calls = 0

    def before(self, tool: str, args: dict, call_fn) -> None:
        pass

    def after(self, tool: str, args: dict, result: Any, call_fn) -> bool:
        """True if this defense flags the call as suspicious."""
        return False


class NoDefense(Defense):
    name = "none"


class HashPin(Defense):
    """D-hash: the consensus MCP defense. Pins the declaration hash.

    Included to make its blind spot concrete rather than argued. Every
    adversary in this benchmark leaves the declaration untouched, so this
    defense cannot fire even in principle -- its detection rate is
    structurally zero, not merely low.
    """

    name = "hash-pin"

    def __init__(self, tools):
        super().__init__(tools)
        self.pinned = {t["name"]: self._hash(t) for t in tools}

    @staticmethod
    def _hash(t: dict) -> str:
        return ToolDeclaration(
            name=t["name"], description=t.get("description", ""),
            input_schema=t.get("inputSchema", {}),
        ).pin()

    def after(self, tool, args, result, call_fn) -> bool:
        cur = next((self._hash(t) for t in self.tools if t["name"] == tool), None)
        return cur is not None and cur != self.pinned.get(tool)


class ResponseValidator(Defense):
    """D-resp: check the response is consistent with the request.

    Catches a naive adversary that reports what it actually did. Theorem 1
    says it cannot catch one that reports what was asked -- which is every
    adversary from L1 up.
    """

    name = "response-val"

    def after(self, tool, args, result, call_fn) -> bool:
        if not isinstance(result, dict):
            return False
        for k, v in args.items():
            if k in result and str(result[k]) != str(v):
                return True
        return False


class MBADefense(Defense):
    """Ours."""

    name = "MBA"

    def __init__(self, tools, policy: Policy | None = None):
        super().__init__(tools)
        self.auditor = Auditor.from_mcp_tools(
            tools, server_id="srv", policy=policy or Policy.default())

    def _counting(self, call_fn):
        def wrapped(name, a):
            self.calls += 1
            return call_fn(name, a)
        return wrapped

    def before(self, tool, args, call_fn) -> None:
        self.auditor.before_call(tool, args, call_fn=self._counting(call_fn))

    def after(self, tool, args, result, call_fn) -> bool:
        alerts = self.auditor.after_call(
            tool, args, result, call_fn=self._counting(call_fn))
        return any(a.severity == "violation" for a in alerts)


DEFENSES: list[Callable[[list[dict]], Defense]] = [
    NoDefense, HashPin, ResponseValidator, MBADefense,
]


# --------------------------------------------------------------------------
# Trials
# --------------------------------------------------------------------------

@dataclass
class Cell:
    domain: str
    adversary: str
    loc: int
    defense: str
    trials: int
    attacks: int          # runs where the effect actually landed
    detections: int       # runs the defense flagged
    overhead: float       # extra calls per task call

    @property
    def asr(self) -> float:
        return self.attacks / max(self.trials, 1)

    @property
    def dr(self) -> float:
        return self.detections / max(self.attacks, 1)


def _run_once(domain: Domain, make_server, make_defense) -> tuple[bool, bool, int]:
    oracle = EffectOracle()
    server = make_server(oracle)
    defense = make_defense(domain.tools)

    def call_fn(name, a):
        return server.call(name, a)

    defense.before(domain.task_tool, domain.task_args, call_fn)
    result = server.call(domain.task_tool, domain.task_args)
    flagged = defense.after(domain.task_tool, domain.task_args, result, call_fn)

    attacked = any(domain.attack_succeeded(e) for e in oracle._effects)
    return attacked, flagged, defense.calls


def evaluate_cell(domain: Domain, adv_label: str, loc: int, make_server,
                  make_defense, trials: int = 30) -> Cell:
    attacks = dets = calls = 0
    for _ in range(trials):
        a, f, c = _run_once(domain, make_server, make_defense)
        attacks += a
        dets += f and a
        calls += c
    return Cell(domain.name, adv_label, loc, make_defense(domain.tools).name,
                trials, attacks, dets, calls / max(trials, 1))


def false_positive_rate(domain: Domain, make_defense, trials: int = 200,
                        noise_rate: float = 0.0, seed: int = 13) -> float:
    """How often does the defense flag a completely honest server?

    Any flag here is a false alarm by construction -- the server is honest.

    `noise_rate` injects LEGITIMATE concurrent activity between calls: a
    scheduled job, another client, a human. This is the realistic
    false-positive source and the first objection a reviewer raises,
    because a conservation check compares a quantity before and after the
    agent's write and cannot tell an attacker's skim from someone else's
    honest transaction. Measuring FPR at noise_rate=0 against a
    deterministic single-client server is a tautology, not a measurement.
    """
    import random
    rng = random.Random(seed)
    flags = 0
    for _ in range(trials):
        oracle = EffectOracle()
        server = domain.honest(oracle)
        if noise_rate and domain.noise_fn:
            server = NoisyHonest(oracle=oracle, inner=server,
                                 noise_rate=noise_rate,
                                 noise_fn=domain.noise_fn, _rng=rng)
        defense = make_defense(domain.tools)

        def call_fn(name, a):
            return server.call(name, a)

        defense.before(domain.task_tool, domain.task_args, call_fn)
        res = server.call(domain.task_tool, domain.task_args)
        if defense.after(domain.task_tool, domain.task_args, res, call_fn):
            flags += 1
            continue
        for name, a in domain.benign_calls:
            defense.before(name, a, call_fn)
            r = server.call(name, a)
            if defense.after(name, a, r, call_fn):
                flags += 1
                break
    return flags / max(trials, 1)

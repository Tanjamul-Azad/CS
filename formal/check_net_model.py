"""Explicit-state mirror of formal/EffectSealNet.tla.

Breadth-first search over the same actions, invariants, and state constraint,
for each ablation configuration, so the network model can be checked without
TLC and the two checkers can be compared. TLC remains the reference.

Usage: python formal/check_net_model.py
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, replace

CALLS = ("c1", "c2")
STREAMS = (0, 1)
ALLOWED = 1
NONE = "none"
MATCHES = {"good", "tokgood"}


@dataclass(frozen=True)
class Flags:
    pre_send: bool = True
    cred_injection: bool = True
    confined: bool = True
    atomic_count: bool = True
    replay_guard: bool = True
    slack: bool = True


CONFIGS = {
    "NetFull": Flags(),
    "NetNoPreSend": Flags(pre_send=False),
    "NetNoCredInjection": Flags(cred_injection=False),
    "NetNotConfined": Flags(confined=False),
    "NetNoAtomicCount": Flags(atomic_count=False),
    "NetNoReplayGuard": Flags(replay_guard=False),
}


@dataclass(frozen=True)
class S:
    phase: tuple
    runs: tuple
    count: tuple
    pending: tuple   # per call: tuple per stream
    checked: tuple
    sent: tuple
    bad: bool
    token: bool


def props(f: Flags) -> set:
    out = {"good", "bad"}
    if not f.cred_injection:
        out.add("tokbad")
        if f.slack:
            out.add("tokgood")
    return out


def setc(t: tuple, i: int, v):
    return t[:i] + (v,) + t[i + 1:]


def transmit(s: S, i: int, v: str) -> S:
    return replace(s, sent=setc(s.sent, i, s.sent[i] + 1), bad=s.bad or v not in MATCHES,
                   token=s.token or v in ("tokgood", "tokbad"))


def clear(s: S, i: int, k: int) -> S:
    return replace(s, pending=setc(s.pending, i, setc(s.pending[i], k, NONE)),
                   checked=setc(s.checked, i, setc(s.checked[i], k, False)))


def successors(s: S, f: Flags):
    for i, _ in enumerate(CALLS):
        if s.phase[i] == "idle":
            yield replace(s, phase=setc(s.phase, i, "running"), runs=setc(s.runs, i, s.runs[i] + 1))
        if not f.replay_guard and s.phase[i] == "done":
            yield replace(s, phase=setc(s.phase, i, "running"), runs=setc(s.runs, i, s.runs[i] + 1),
                          count=setc(s.count, i, 0))
        if s.phase[i] == "running" and all(p == NONE for p in s.pending[i]):
            yield replace(s, phase=setc(s.phase, i, "done"))
        if not f.confined and s.phase[i] == "running":
            for v in props(f):
                yield transmit(s, i, v)
        for k in STREAMS:
            p = s.pending[i][k]
            if s.phase[i] == "running" and p == NONE:
                for v in props(f):
                    yield replace(s, pending=setc(s.pending, i, setc(s.pending[i], k, v)))
            if p == NONE:
                continue
            if f.pre_send and f.atomic_count and p in MATCHES and s.count[i] < ALLOWED:
                yield clear(transmit(replace(s, count=setc(s.count, i, s.count[i] + 1)), i, p), i, k)
            if f.pre_send and not f.atomic_count and p in MATCHES and not s.checked[i][k] \
                    and s.count[i] < ALLOWED:
                yield replace(s, checked=setc(s.checked, i, setc(s.checked[i], k, True)))
            if s.checked[i][k]:
                yield clear(transmit(replace(s, count=setc(s.count, i, s.count[i] + 1)), i, p), i, k)
            if f.pre_send and not s.checked[i][k] and (p not in MATCHES or s.count[i] >= ALLOWED):
                yield clear(s, i, k)
            if not f.pre_send:
                yield clear(transmit(replace(s, count=setc(s.count, i, s.count[i] + 1)), i, p), i, k)


def violated(s: S) -> list[str]:
    out = []
    if s.bad:
        out.append("OnlyApprovedSent")
    if s.token:
        out.append("NoCredentialLeak")
    if any(n > ALLOWED for n in s.sent):
        out.append("SendBound")
    return out


def within(s: S) -> bool:
    return all(n <= ALLOWED + 1 for n in s.sent) and all(r <= 2 for r in s.runs)


def check(f: Flags) -> dict:
    n = len(CALLS)
    init = S(("idle",) * n, (0,) * n, (0,) * n, ((NONE, NONE),) * n,
             ((False, False),) * n, (0,) * n, False, False)
    seen, queue = {init}, deque([init])
    while queue:
        s = queue.popleft()
        broken = violated(s)
        if broken:
            return {"result": "violated", "invariants": broken, "distinct_states": len(seen)}
        if not within(s):
            continue
        for t in successors(s, f):
            if t not in seen:
                seen.add(t)
                queue.append(t)
    return {"result": "all invariants hold", "distinct_states": len(seen)}


if __name__ == "__main__":
    print(json.dumps({name: check(flags) for name, flags in CONFIGS.items()}, indent=2))

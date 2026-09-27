"""Explicit-state mirror of formal/EffectSeal.tla.

A breadth-first search over exactly the actions and invariants of the TLA+
specification, for each ablation configuration. It exists so the model can be
checked where TLC is not installed; TLC on EffectSeal.tla remains the
reference check, and the two must agree.

Usage: python formal/check_model.py
"""

from __future__ import annotations

import itertools
import json
import sys
from collections import deque
from dataclasses import dataclass, replace

REQ = ("r1", "r2", "r3")
MAX = 2
EXEC_BOUND = 2  # state constraint, as CONSTRAINT StateConstraint in the .cfg
VALS = ("good", "bad")
NONE = "none"


@dataclass(frozen=True)
class Flags:
    same_read: bool = True
    stop_writers: bool = True
    atomic_reserve: bool = True
    replay_guard: bool = True
    writer_may_escape: bool = True


CONFIGS = {
    "Full": Flags(),
    "NoSameRead": Flags(same_read=False),
    "NoAtomicReserve": Flags(atomic_reserve=False),
    "NoReplayGuard": Flags(replay_guard=False),
    "NoStopWriters": Flags(stop_writers=False),
}

# state: tuple of per-request records (slot, execs, phase, alive, staged, checked, trusted)
FIELDS = ("slot", "execs", "phase", "alive", "staged", "checked", "trusted")


def init():
    return tuple(("free", 0, "idle", False, NONE, NONE, NONE) for _ in REQ)


def setr(state, i, **changes):
    rec = dict(zip(FIELDS, state[i]))
    rec.update(changes)
    out = list(state)
    out[i] = tuple(rec[f] for f in FIELDS)
    return tuple(out)


def used(state):
    return sum(1 for rec in state if rec[0] != "free")


def launch(state, i, **extra):
    return setr(state, i, phase="running", alive=True, execs=state[i][1] + 1,
                staged=NONE, **extra)


def successors(state, f: Flags):
    for i in range(len(REQ)):
        slot, execs, phase, alive, staged, checked, trusted = state[i]
        if f.atomic_reserve and phase == "idle" and slot == "free" and used(state) < MAX:
            yield "Reserve", launch(state, i, slot="reserved")
        if not f.atomic_reserve and phase == "idle" and slot == "free" and used(state) < MAX:
            yield "CheckRoom", setr(state, i, phase="checked")
        if phase == "checked":
            yield "TakeSlot", launch(state, i, slot="reserved")
        if not f.replay_guard and phase == "done":
            yield "Replay", launch(state, i)
        if alive and phase in ("running", "stopped", "read", "done"):
            for v in VALS:
                yield "ServerWrite", setr(state, i, staged=v)
        if f.stop_writers and phase == "running":
            yield "Stop", setr(state, i, phase="stopped", alive=f.writer_may_escape)
        if phase == "stopped" or (not f.stop_writers and phase == "running"):
            yield "Read", setr(state, i, checked=staged, phase="read")
        if phase == "read" and checked == "good":
            yield "Commit", setr(state, i, trusted=checked if f.same_read else staged,
                                 slot="committed", phase="done")
        if phase == "read" and checked != "good":
            yield "Refuse", setr(state, i, slot="failed", phase="done")
        if phase in ("running", "stopped", "read"):
            yield "Crash", setr(state, i, phase="crashed", staged=NONE, checked=NONE)


INVARIANTS = {
    "AllowanceBound": lambda s: used(s) <= MAX,
    "ExecAtMostOnce": lambda s: all(r[1] <= 1 for r in s),
    "TrustedOnlyAccepted": lambda s: all(r[6] in (NONE, "good") for r in s),
    "CommittedIsChecked": lambda s: all(r[0] != "committed" or r[6] == r[5] for r in s),
    "CrashStaysSpent": lambda s: all(r[2] != "crashed" or r[0] == "reserved" for r in s),
}


def check(flags: Flags, depth_limit: int = 40):
    start = init()
    seen = {start: None}
    queue = deque([start])
    violations = {}
    while queue:
        state = queue.popleft()
        for name, inv in INVARIANTS.items():
            if name not in violations and not inv(state):
                violations[name] = trace(seen, state)
        if any(r[1] > EXEC_BOUND for r in state):
            continue  # outside the state constraint: checked, not expanded
        for action, nxt in successors(state, flags):
            if nxt not in seen:
                seen[nxt] = (state, action)
                queue.append(nxt)
    return len(seen), violations


def trace(seen, state):
    steps = []
    while seen[state] is not None:
        prev, action = seen[state]
        steps.append(action)
        state = prev
    return list(reversed(steps))


def main() -> int:
    report = {}
    for name, flags in CONFIGS.items():
        states, violations = check(flags)
        report[name] = {"distinct_states": states,
                        "violated": {k: v for k, v in violations.items()}}
        status = "all invariants hold" if not violations else \
            "violates " + ", ".join(sorted(violations))
        print(f"{name:16s} {states:8d} states  {status}")
        for inv, steps in sorted(violations.items()):
            print(f"    {inv}: shortest counterexample {len(steps)} steps: {' -> '.join(steps)}")
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

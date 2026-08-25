r"""
E5: can a probe-aware server evade MBA by noticing when it is watched?

This attacks our own defense. The auditor snapshots BEFORE the write, and
since the stable-window fix it reads the ledger twice to confirm the
window was quiet. From the server's side that is a distinctive prelude,
and it arrives while the server still gets to choose whether to cheat.

Sweeps the audit budget b (fraction of task calls audited) and compares:

  blind       attacks every call, ignores the traffic pattern
  probe-aware attacks only when the preceding traffic does NOT look like
              a pre-audit snapshot
  decoy       our mitigation: the auditor takes the snapshot on EVERY
              call and only sometimes completes the audit, so the prelude
              carries no information about which calls are checked

    python experiments/run_probe_aware.py
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcpaudit import Auditor, Policy  # noqa: E402
from mcpmut.core import EffectOracle  # noqa: E402
from mcpmut.probe_aware import ProbeAware  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_eval import BANKING  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
READS = {"check_balance", "list_transactions"}


def session(domain, adversary: str, budget: float, decoy: bool,
            n_calls: int, rng: random.Random) -> tuple[int, int]:
    """Run one session. Returns (thefts, detections)."""
    oracle = EffectOracle()
    cheat = domain.ladder[0][2](oracle)          # L1: forge response
    honest = domain.honest(oracle)

    if adversary.startswith("probe-aware"):
        server = ProbeAware(oracle=oracle, honest_inner=honest,
                            cheat_inner=cheat,
                            ignore_prelude=adversary.endswith("bold"))
        server._reads = READS
    else:
        server = cheat

    auditor = Auditor.from_mcp_tools(domain.tools, server_id="s",
                                     policy=Policy(**{
                                         **Policy.default().__dict__,
                                         # High, so the auditor's own probe-volume
                                         # cap does not confound the budget sweep
                                         # we are actually varying here.
                                         "audit_budget": 50.0}))
    call_fn = lambda n, a: server.call(n, a)      # noqa: E731

    thefts = dets = 0
    for _ in range(n_calls):
        audit_this = rng.random() < budget
        # Decoy: always snapshot, so the prelude cannot signal which calls
        # will actually be checked.
        if audit_this or decoy:
            auditor.before_call(domain.task_tool, domain.task_args,
                                call_fn=call_fn)

        before = len(oracle._effects)
        result = server.call(domain.task_tool, domain.task_args)
        stole = any(domain.attack_succeeded(e)
                    for e in oracle._effects[before:])
        thefts += stole

        if audit_this:
            alerts = auditor.after_call(domain.task_tool, domain.task_args,
                                        result, call_fn=call_fn)
            if stole and any(a.severity == "violation" for a in alerts):
                dets += 1
    return thefts, dets


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calls", type=int, default=40)
    ap.add_argument("--sessions", type=int, default=25)
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()

    budgets = [0.25, 0.5, 0.75, 1.0]
    arms = [("blind", False), ("probe-aware", False),
            ("probe-aware", True), ("probe-aware-bold", True)]
    labels = {("blind", False): "blind attacker",
              ("probe-aware", False): "probe-aware",
              ("probe-aware", True): "probe-aware vs decoy",
              ("probe-aware-bold", True): "bold (knows decoys)"}

    print(f"\n{'='*74}")
    print("E5  PROBE-AWARE ADVERSARY  --  attacking our own defense")
    print("=" * 74)
    print(f"  {args.sessions} sessions x {args.calls} calls, banking domain\n")
    print(f"  {'arm':24} {'budget':>7} {'thefts':>8} {'caught':>8} {'DR':>8}")

    out = []
    for adv, decoy in arms:
        for b in budgets:
            rng = random.Random(args.seed)
            T = D = 0
            for _ in range(args.sessions):
                t, d = session(BANKING, adv, b, decoy, args.calls, rng)
                T += t
                D += d
            dr = D / max(T, 1)
            out.append({"arm": labels[(adv, decoy)], "budget": b,
                        "thefts": T, "caught": D, "dr": dr})
            print(f"  {labels[(adv,decoy)]:24} {b:7.0%} {T:8} {D:8} {100*dr:7.1f}%")
        print()

    p = ROOT / "experiments" / "results" / "probe_aware.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {p.relative_to(ROOT)}\n")


if __name__ == "__main__":
    main()

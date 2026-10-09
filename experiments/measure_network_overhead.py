"""Network pre-send gate: per-request overhead and the 100-trial allowance race.

Two mechanism measurements for the network arm, the counterpart of the
file-side run_concurrency_100.py. Neither needs a live server: both exercise
the real gate machinery (request_templates + SQLiteAllowanceLedger).

  Overhead. The per-request cost the EffectSeal-N gate adds before a request
    leaves the broker, on the Postmark sendEmail request shape (the headline
    case), inferred through the same template code path as the evaluation:
      - admission: canonical_view + RequestContract.check (per request);
      - durable allowance: SQLiteAllowanceLedger reserve + commit (per approved
        request, WAL + synchronous=FULL, so this is the disk-bound component);
      - baseline: a host allow-list check (what ToolHive/AgentBound decide on).
    Reported as p50/p95/p99 over many iterations. Network round-trip is not
    included: the gate does not change it.

  Allowance race. For >=100 trials, several concurrent approved requests reserve
    the same single-slot contract. Exactly one must proceed and commit; the rest
    must be refused (N-A7 duplicate/replay). A repeated request id must return
    the recorded slot, never a second effect.

    python experiments/measure_network_overhead.py [--iters 2000] [--trials 100]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mcpgate.allowance import AllowanceError, SQLiteAllowanceLedger  # noqa: E402
from mcpgate.request_templates import (CapturedRequest, RequestObservation,  # noqa: E402
                                       canonical_view, infer_request_template)

OUT = ROOT / "artifact" / "results" / "network_overhead_races.json"
CRED = frozenset({"x-postmark-server-token"})
HOST = "api.postmarkapp.com"
URL = f"https://{HOST}/email"
CONTENDERS = 8


def _request(to: str, subject: str, body: str) -> CapturedRequest:
    payload = {"From": "agent@ours.test", "To": to, "Subject": subject, "HtmlBody": body}
    return CapturedRequest("POST", URL,
                           {"Content-Type": "application/json",
                            "X-Postmark-Server-Token": "DUMMYKEY"},
                           json.dumps(payload).encode())


def _args(to: str, subject: str, body: str) -> dict:
    return {"to": to, "subject": subject, "body": body}


def build_template():
    """Infer the real Postmark sendEmail request template from honest runs."""
    samples = [
        ("alice@example.org", "Q3 numbers", "The Q3 totals are attached."),
        ("bob@example.org", "Weekly sync", "Notes from the weekly sync are below."),
        ("carol@example.org", "Release 4.2", "Release 4.2 is live; changelog inside."),
    ]
    observations = [RequestObservation(_args(*s), (_request(*s),)) for s in samples]
    return infer_request_template("sendEmail", observations, fixed={})


def percentiles(samples_ns: list[int]) -> dict:
    micros = sorted(x / 1000 for x in samples_ns)
    n = len(micros)

    def pct(p):
        return round(micros[min(n - 1, int(p * n))], 2)

    return {"n": n, "p50_us": pct(0.50), "p95_us": pct(0.95), "p99_us": pct(0.99),
            "mean_us": round(statistics.fmean(micros), 2), "max_us": round(micros[-1], 2)}


def measure_overhead(iters: int) -> dict:
    template = build_template()
    test = _args("dave@example.org", "October report", "Here is the October report body.")
    request = _request(test["to"], test["subject"], test["body"])
    contract = template.instantiate(test)
    ok, reason = contract.check(request, 0)
    if not ok:
        raise SystemExit(f"honest request did not pass its own template: {reason}")

    admission, durable, baseline, instantiate = [], [], [], []
    with tempfile.TemporaryDirectory(prefix="es-netovh-", ignore_cleanup_errors=True) as tmp:
        ledger = SQLiteAllowanceLedger(Path(tmp) / "allowance.db")
        for i in range(iters):
            t0 = time.perf_counter_ns()
            view = canonical_view(request, credential_headers=CRED)  # noqa: F841
            contract.check(request, 0)
            admission.append(time.perf_counter_ns() - t0)

            t0 = time.perf_counter_ns()
            template.instantiate(test)
            instantiate.append(time.perf_counter_ns() - t0)

            cid = f"contract-{i}"  # a fresh single-slot contract each iteration
            t0 = time.perf_counter_ns()
            ledger.reserve(cid, "r0", 1)
            ledger.commit(cid, "r0", {"status": "sent"})
            durable.append(time.perf_counter_ns() - t0)

            t0 = time.perf_counter_ns()
            urlsplit(request.url).hostname == HOST
            baseline.append(time.perf_counter_ns() - t0)
    total = [a + d for a, d in zip(admission, durable)]
    return {"admission_check": percentiles(admission),
            "template_instantiate": percentiles(instantiate),
            "durable_allowance_reserve_commit": percentiles(durable),
            "gate_total_per_request": percentiles(total),
            "host_allowlist_baseline": percentiles(baseline)}


def _race_trial(db: Path) -> dict:
    ledger = SQLiteAllowanceLedger(db)
    cid = "shared-contract"
    barrier = threading.Barrier(CONTENDERS)
    outcomes: list[str] = []
    lock = threading.Lock()

    def contend(index: int) -> None:
        try:
            barrier.wait(timeout=10)
        except threading.BrokenBarrierError:
            pass
        try:
            existing = ledger.reserve(cid, f"req-{index}", 1)
            if existing is None:
                ledger.commit(cid, f"req-{index}", {"status": "sent"})
                outcome = "committed"
            else:
                outcome = "deduplicated"
        except AllowanceError:
            outcome = "allowance_refused"
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=contend, args=(i,)) for i in range(CONTENDERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    committed = outcomes.count("committed")
    return {"committed": committed, "refused": outcomes.count("allowance_refused"),
            "exactly_one_committed": committed == 1}


def _replay_trial(db: Path) -> bool:
    """A repeated request id must return the recorded slot, not a new effect."""
    ledger = SQLiteAllowanceLedger(db)
    cid = "replay-contract"
    first = ledger.reserve(cid, "same", 1)
    ledger.commit(cid, "same", {"status": "sent"})
    second = ledger.reserve(cid, "same", 1)  # replay of the same request id
    return first is None and second is not None and ledger.used(cid) == 1


def measure_races(trials: int) -> dict:
    race_rows, replay_ok = [], 0
    with tempfile.TemporaryDirectory(prefix="es-netrace-", ignore_cleanup_errors=True) as tmp:
        for i in range(trials):
            race_rows.append(_race_trial(Path(tmp) / f"race{i}.db"))
            replay_ok += _replay_trial(Path(tmp) / f"replay{i}.db")
    return {"trials": trials, "contenders_per_trial": CONTENDERS,
            "trials_exactly_one_committed": sum(r["exactly_one_committed"] for r in race_rows),
            "trials_with_more_than_one_commit": sum(r["committed"] > 1 for r in race_rows),
            "outcome_distribution": dict(Counter(
                f"{r['committed']}c/{r['refused']}r" for r in race_rows)),
            "replay_guard_trials_passed": replay_ok}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iters", type=int, default=2000)
    parser.add_argument("--trials", type=int, default=100)
    args = parser.parse_args()
    overhead = measure_overhead(args.iters)
    races = measure_races(args.trials)
    result = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
              "phase": "NETWORK_PRESEND_OVERHEAD_AND_ALLOWANCE_RACES",
              "request_shape": "Postmark sendEmail (POST /email, JSON body)",
              "iters": args.iters,
              "note": ("Overhead is the gate's added compute per request; network "
                       "round-trip is unchanged and excluded. The durable allowance "
                       "component uses SQLite WAL with synchronous=FULL, so it is "
                       "disk-bound and dominates."),
              "overhead": overhead, "allowance_race": races}
    races_ok = (races["trials_exactly_one_committed"] == args.trials
                and races["trials_with_more_than_one_commit"] == 0
                and races["replay_guard_trials_passed"] == args.trials)
    result["races_all_pass"] = races_ok
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"overhead": overhead, "allowance_race": races,
                      "races_all_pass": races_ok}, indent=2))
    return 0 if races_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

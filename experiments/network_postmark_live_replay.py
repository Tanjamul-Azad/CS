"""Live confirmation of the Postmark pilot against the real Postmark API.

The pilot ran behind a recording mock. This script takes the requests that
actually left the broker in that run, byte for byte, and sends them to the real
Postmark API, so the mock's acceptance can be checked against the provider's.
The broker's confinement is untouched: the pilot already decided what left; we
only ask the real API what it would have done with it.

Every request carries Postmark's documented test value POSTMARK_API_TEST in the
X-Postmark-Server-Token header ("send test emails that won't be delivered").
A guard refuses to send anything else, and nothing is sent to any host other
than api.postmarkapp.com. No email reaches anyone.

Selected requests (pre-registered, NETWORK_PREREG_V2 amendment 13):
  - every request that left the broker under EffectSeal-N (honest calls, and
    the approved first request of attack calls whose extra request was refused);
  - under no defense, the first trial of each diverted attack version.

    python experiments/network_postmark_live_replay.py
"""

from __future__ import annotations

import datetime as dt
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "artifact" / "results" / "network_postmark_20261008-223144"
STAMP = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
OUT = ROOT / "artifact" / "results" / f"network_postmark_live_{STAMP}.json"
HOST = "api.postmarkapp.com"
TEST_TOKEN = "POSTMARK_API_TEST"
DROP = {"host", "content-length", "accept-encoding", "connection"}


def selected(trials: list[dict]) -> list[dict]:
    picks, seen_variant = [], set()
    for trial in trials:
        cond, phase, variant = trial["condition"], trial.get("phase"), trial.get("variant")
        sent = [f for f in trial["far_side"]
                if f["call_id"].endswith("/call") and f["url"].split("/")[2].startswith(HOST)]
        if cond == "effectseal" and phase in ("honest", "attack"):
            picks += [{"condition": cond, "phase": phase, "variant": variant, "request": f}
                      for f in sent]
        elif cond == "none" and phase == "attack" and variant not in seen_variant and sent:
            seen_variant.add(variant)
            picks += [{"condition": cond, "phase": phase, "variant": variant, "request": f}
                      for f in sent]
    return picks


def send(record: dict) -> dict:
    headers = {k: v for k, v in record["headers"].items() if k.lower() not in DROP}
    token = headers.get("x-postmark-server-token")
    if token != TEST_TOKEN:
        return {"sent": False, "why": "guard: header is not the Postmark test token"}
    url = record["url"].replace(f"{HOST}:443", HOST)
    if not url.startswith(f"https://{HOST}/"):
        return {"sent": False, "why": "guard: not the Postmark API"}
    req = urllib.request.Request(url, data=record["body"].encode(), method=record["method"],
                                 headers=headers)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status, body = resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        status, body = error.code, error.read().decode("utf-8", "replace")
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        parsed = {"raw": body[:300]}
    return {"sent": True, "status": status, "error_code": parsed.get("ErrorCode"),
            "message": str(parsed.get("Message", ""))[:200],
            "ms": round(1000 * (time.perf_counter() - started), 1)}


def main() -> int:
    trials = [json.loads(line) for line in
              (PILOT / "trials.jsonl").read_text(encoding="utf-8").splitlines()]
    picks = selected(trials)
    rows = []
    for pick in picks:
        outcome = send(pick["request"])
        body = json.loads(pick["request"]["body"]) if pick["request"]["body"] else {}
        rows.append({"condition": pick["condition"], "phase": pick["phase"],
                     "variant": pick["variant"],
                     "request_fields": sorted(body) if isinstance(body, dict) else [],
                     "bcc": body.get("Bcc") if isinstance(body, dict) else None, **outcome})
        print(f"{pick['condition']:10s} {pick['phase']:6s} {str(pick['variant']):26s} "
              f"-> {outcome.get('status')} {outcome.get('error_code')} {outcome.get('message', '')[:60]}",
              flush=True)
        time.sleep(0.5)
    refused = sum(1 for t in trials if t["condition"] == "effectseal" and t.get("phase") == "attack"
                  and not any(f["url"].split("/")[2].startswith("attacker") for f in t["far_side"]))

    def accepted(rows_):
        return [sum(1 for r in rows_ if r.get("status") == 200 and r.get("error_code") == 0),
                len(rows_)]

    summary = {
        "effectseal_honest_accepted": accepted([r for r in rows if r["condition"] == "effectseal"
                                                and r["phase"] == "honest"]),
        "effectseal_attack_calls_first_request_accepted": accepted(
            [r for r in rows if r["condition"] == "effectseal" and r["phase"] == "attack"]),
        "no_defense_diverted_accepted": accepted([r for r in rows if r["condition"] == "none"]),
        "pilot_effectseal_attack_trials": refused,
        "note": ("Requests EffectSeal refused never left the broker, so there is nothing to "
                 "send for them; the real API saw only what the pilot admitted."),
    }
    OUT.write_text(json.dumps({"created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                               "source": str(PILOT.relative_to(ROOT)).replace("\\", "/"),
                               "endpoint": f"https://{HOST}", "token": "documented test token",
                               "summary": summary, "rows": rows}, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

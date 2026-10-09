"""Matched network-effect evaluation over selected registry servers (RQ-N).

Pre-registration: paper/NETWORK_PREREG_V2.md. For each qualified server:

  Pin.    Run the server behind the broker (record mode) on the exemplar call
          and perturbed variants, in private per-session containers with no
          internet. Infer one request template per write tool. Fields whose
          perturbation makes the honest server error are held fixed.
  Honest. Run K test calls with unseen arguments behind the EffectSeal-N gate.
          Completion and false blocks are read from the far-side oracle.
  Attack. For each honest test call's captured request R, construct the eight
          diverted variants (Table N-A1..N-A8) as transformations of R, and
          ask each defense whether it would admit the variant:
            - EffectSeal-N: the instantiated request template's check;
            - destination policy: the request's host is the approved host
              (this is what ToolHive, AgentBound, and a domain allow-list all
              decide on, confirmed on Postmark in the matched pilot).
          No server-side code is modified: the attack is a well-defined change
          to a request record, and the measurement is which check passes it.

    python experiments/network_matched_eval.py --selection <dir> [--calls 12]
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import hashlib
import shutil
import subprocess
import random
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

import network_postmark_pilot as P  # noqa: E402
import network_select_servers as SEL  # noqa: E402
from mcpgate.request_templates import (CapturedRequest, RequestObservation,  # noqa: E402
                                       canonical_view, infer_request_template)
from mcpgate.template_inference import TemplateError, perturb_value  # noqa: E402
from mcpmut.live import LiveSession  # noqa: E402

STAMP = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
OUT = ROOT / "artifact" / "results" / f"network_matched_{STAMP}"
ATTACK_HOST = "attacker.test"
MARK = "ATTACKERVALUE"
ATTACKS = ("A1_add_field", "A2_change_value", "A3_append_text", "A4_extra_same_host",
           "A5_extra_other_host", "A6_credential_channel", "A7_duplicate", "A8_silent_noop")


# -- perturbing structured arguments ------------------------------------------

def perturb_args(args: dict, rng: random.Random, fixed: set) -> dict:
    out = copy.deepcopy(args)

    def walk(node, path):
        if isinstance(node, dict):
            return {k: walk(v, f"{path}.{k}") for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v, f"{path}[{i}]") for i, v in enumerate(node)]
        if isinstance(node, str) and path not in fixed and len(node) >= 3:
            return perturb_value(node, rng)
        return node

    return {k: walk(v, k) for k, v in out.items()}


# -- running one call behind the broker ---------------------------------------

def run(broker: SEL.GenericBroker, image: str, env: dict, tool: str, args: dict,
        condition: str, templates: dict | None) -> dict:
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    call_id = uuid.uuid4().hex[:10]
    state = (lambda phase: {"mode": "record", "call_id": phase} if condition == "none"
             else {"mode": "gate", "call_id": phase, "template": templates["call"],
                   "arguments": args, "credential_headers": [], "inject": True})
    broker.write_state(state(f"{call_id}/startup"))
    trial = {"call_id": call_id, "args": args, "condition": condition, "started": started}
    try:
        cmd = broker.command_for(image, env)
        name = broker.last_server
        with LiveSession(cmd) as session:
            broker.write_state(state(f"{call_id}/call"))
            time.sleep(0.2)
            trial["response"] = str(session.call(tool, args))[:300]
            trial["error"] = session.last_was_error
    except Exception as exc:  # noqa: BLE001
        trial["response"], trial["error"] = f"{type(exc).__name__}: {exc}", True
    finally:
        broker.remove_server()
    broker.write_state({"mode": "deny", "call_id": ""})
    time.sleep(0.3)
    recs = [r for r in broker.lines("records.jsonl") if r["call_id"].startswith(call_id)]
    trial["requests"] = [r for r in recs if r["call_id"].endswith("/call")]
    trial["sends"] = [r for r in broker.lines("sends.jsonl") if r["call_id"].startswith(call_id)]
    trial["far_side"] = [r for r in broker.lines("far_side.jsonl") if r["call_id"].startswith(call_id)]
    return trial


def captured(req: dict) -> CapturedRequest:
    return CapturedRequest(req["method"], req["url"], req["headers"], req["body"].encode())


# -- attack transformations on one honest request -----------------------------

def mutate(reqs: list[CapturedRequest], attack: str) -> list[CapturedRequest] | None:
    """Return the request sequence a diverted server would emit, or None if the
    attack does not apply to this request shape."""
    if not reqs:
        return None
    first = reqs[0]
    host = urlsplit(first.url).hostname
    body = first.body.decode("utf-8", "replace")
    is_json = body.strip().startswith(("{", "["))
    if attack == "A1_add_field":
        if not is_json or not body.strip().startswith("{"):
            return None
        obj = json.loads(body); obj["bcc"] = f"{MARK}@{ATTACK_HOST}"
        return [CapturedRequest(first.method, first.url, first.headers, json.dumps(obj).encode())]
    if attack == "A2_change_value":
        if not is_json or not body.strip().startswith("{"):
            return None
        obj = json.loads(body); changed = False
        for k, v in obj.items():
            if isinstance(v, str) and len(v) >= 3:
                obj[k] = MARK; changed = True; break
        if not changed:
            return None
        return [CapturedRequest(first.method, first.url, first.headers, json.dumps(obj).encode())]
    if attack == "A3_append_text":
        if not is_json or not body.strip().startswith("{"):
            return None
        obj = json.loads(body); changed = False
        for k, v in obj.items():
            if isinstance(v, str) and len(v) >= 10:
                obj[k] = v + " " + MARK; changed = True; break
        if not changed:
            return None
        return [CapturedRequest(first.method, first.url, first.headers, json.dumps(obj).encode())]
    if attack == "A4_extra_same_host":
        return list(reqs) + [first]
    if attack == "A5_extra_other_host":
        url = first.url.replace(host, ATTACK_HOST, 1)
        return list(reqs) + [CapturedRequest("POST", url, first.headers, body.encode())]
    if attack == "A6_credential_channel":
        headers = dict(first.headers)
        target = next((h for h in headers if any(w in h.lower()
                      for w in ("key", "token", "auth", "secret"))), None)
        if target is None:
            return None
        headers[target] = MARK
        return [CapturedRequest(first.method, first.url, headers, first.body)]
    if attack == "A7_duplicate":
        return list(reqs) + list(reqs)
    if attack == "A8_silent_noop":
        return []
    return None


def effectseal_stops(template, args: dict, variant: list[CapturedRequest]) -> bool:
    try:
        contract = template.instantiate(args)
    except TemplateError:
        return True  # no contract for this call: refused
    if not variant:  # A8: nothing sent; the mediator reports INCOMPLETE, not committed
        return True
    admitted = 0
    for req in variant:
        ok, _ = contract.check(req, admitted)
        if not ok:
            return True
        admitted += 1
    return False


def destination_stops(approved_host: str, variant: list[CapturedRequest]) -> bool:
    if not variant:
        return False  # a silent no-op sends nothing to a disallowed host: not caught
    return any(urlsplit(r.url).hostname != approved_host for r in variant)


# -- per-server evaluation ----------------------------------------------------

def evaluate(broker: SEL.GenericBroker, entry: dict, calls: int, rng: random.Random) -> dict:
    image, tool, exemplar = entry["image"], entry["tool"], entry["args"]
    env = {e: "DUMMYKEY" + e.lower() for e in entry.get("env_names", [])}
    env.update(entry.get("extra_env", {}))
    result = {"name": entry["name"], "image": image, "tool": tool, "entry": entry,
              "evidence": {"pins": [], "honest": [], "cases": []}}
    evidence = result["evidence"]

    # Pin: exemplar + perturbations; hold fixed any field whose change errors.
    fixed: set = set()
    pins: list[dict] = []
    base = run(broker, image, env, tool, exemplar, "none", None)
    evidence["pins"].append(base)
    if base["error"] or not base["requests"]:
        return {**result, "qualified": False, "reason": "exemplar did not reproduce"}
    pins.append(base)
    approved_host = urlsplit(base["requests"][0]["url"]).hostname
    for _ in range(6):
        if len([p for p in pins if not p["error"]]) >= 5:
            break
        cand = perturb_args(exemplar, rng, fixed)
        t = run(broker, image, env, tool, cand, "none", None)
        evidence["pins"].append(t)
        if t["error"] or not t["requests"]:
            # find a field that differs and freeze it, then retry next loop
            for k, v in cand.items():
                if isinstance(v, str) and v != exemplar.get(k):
                    fixed.add(k)
            continue
        pins.append(t)
    good = [p for p in pins if not p["error"] and p["requests"]]
    if len(good) < 2:
        return {**result, "qualified": False, "reason": f"only {len(good)} honest pin runs", "fixed": sorted(fixed)}

    try:
        template = infer_request_template(
            tool, [RequestObservation(p["args"], tuple(captured(r) for r in p["requests"]),
                                     dt.datetime.fromisoformat(p["started"]))
                   for p in good], fixed={k: exemplar[k] for k in fixed if k in exemplar})
    except TemplateError as exc:
        return {**result, "qualified": False, "reason": f"template inference: {exc}", "fixed": sorted(fixed)}
    evidence["template"] = template.to_json()
    evidence["inference_pin_ids"] = [p["call_id"] for p in good]
    result["slack_bits"] = round(template.slack(), 3)
    result["fixed_fields"] = sorted(fixed)
    result["approved_host"] = approved_host

    # Honest test calls with unseen arguments, behind the EffectSeal-N gate.
    templates = {"call": template.to_json()}
    honest = []
    for _ in range(calls):
        args = perturb_args(exemplar, rng, fixed)
        t = run(broker, image, env, tool, args, "effectseal", templates)
        evidence["honest"].append(t)
        sent = [r for r in t["far_side"] if r["call_id"].endswith("/call")]
        admitted = all(d["admitted"] for d in t["requests"]) and bool(t["requests"])
        honest.append({"started": t["started"], "call_id": t["call_id"], "args": args, "error": t["error"], "sent": len(sent), "admitted": admitted,
                       "requests": t["requests"]})
    result["honest"] = {"calls": calls,
                        "completed": sum(h["admitted"] and not h["error"] and h["sent"] >= 1 for h in honest),
                        "blocked": sum(not h["admitted"] for h in honest)}

    # Attack analysis over captured honest requests.
    atk = {a: {"applicable": 0, "effectseal_stops": 0, "destination_stops": 0} for a in ATTACKS}
    for h in honest:
        reqs = [captured(r) for r in h["requests"] if urlsplit(r["url"]).hostname == approved_host]
        if not reqs:
            continue
        for a in ATTACKS:
            variant = mutate(reqs, a)
            if variant is None:
                continue
            verdict = sequence_verdict(template, h["args"], variant, dt.datetime.fromisoformat(h["started"]))
            evidence["cases"].append({"family": "fixed", "attack": a, "call_id": h["call_id"],
                                      "args": h["args"], "now": h["started"],
                                      "variant": [encode_request(r) for r in variant],
                                      "verdict": verdict, "destination_stops": destination_stops(approved_host, variant)})
            atk[a]["applicable"] += 1
            atk[a]["effectseal_stops"] += verdict["outcome"] != "ADMITTED"
            atk[a]["destination_stops"] += destination_stops(approved_host, variant)
        for label, variant in adaptive_variants(reqs):
            verdict = sequence_verdict(template, h["args"], variant, dt.datetime.fromisoformat(h["started"]))
            evidence["cases"].append({"family": "adaptive", "attack": label, "call_id": h["call_id"],
                                      "args": h["args"], "now": h["started"],
                                      "variant": [encode_request(r) for r in variant], "verdict": verdict,
                                      "destination_stops": destination_stops(approved_host, variant)})
    adaptive = [c for c in evidence["cases"] if c["family"] == "adaptive"]
    result["adaptive"] = {"applicable": len(adaptive), "stopped": sum(c["verdict"]["outcome"] != "ADMITTED" for c in adaptive),
                          "admitted": sum(c["verdict"]["outcome"] == "ADMITTED" for c in adaptive)}
    result["attacks"] = atk
    result["qualified"] = True
    return result


def encode_request(r):
    return {"method": r.method, "url": r.url, "headers": dict(r.headers), "body": r.body.decode("utf-8")}


def sequence_verdict(template, args, variant, now):
    contract = template.instantiate(args, now=now)
    admitted = 0
    checks = []
    for r in variant:
        ok, reason = contract.check(r, admitted)
        checks.append({"admitted": ok, "reason": reason})
        if not ok:
            return {"outcome": "PARTIAL" if admitted else "REFUSED", "admitted_prefix": admitted, "checks": checks}
        admitted += 1
    return {"outcome": "ADMITTED" if admitted == len(contract.patterns) else "INCOMPLETE",
            "admitted_prefix": admitted, "checks": checks}


def adaptive_variants(reqs):
    # Every JSON string leaf in every request; retain the rest of the sequence.
    def leaves(value, path=()):
        if isinstance(value, dict):
            for k, v in value.items():
                yield from leaves(v, path + (k,))
        elif isinstance(value, list):
            for i, v in enumerate(value):
                yield from leaves(v, path + (i,))
        elif isinstance(value, str):
            yield path, value
    for index, r in enumerate(reqs):
        try:
            obj = json.loads(r.body)
        except (ValueError, UnicodeError):
            continue
        for path, old in leaves(obj):
            for mode, value in [('replace', MARK), ('append', old + ' ' + MARK)]:
                altered = copy.deepcopy(obj)
                if path:
                    node = altered
                    for key in path[:-1]:
                        node = node[key]
                    node[path[-1]] = value
                else:
                    altered = value
                variant = list(reqs)
                variant[index] = CapturedRequest(r.method, r.url, r.headers, json.dumps(altered).encode())
                yield json.dumps([index, path, mode]), variant


def wilson(success, total):
    if not total:
        return None
    z = 1.959963984540054
    p = success / total
    d = 1 + z*z/total
    mid = (p + z*z/(2*total))/d
    half = z*((p*(1-p)/total + z*z/(4*total*total))**.5)/d
    return [max(0, mid-half), min(1, mid+half)]


def cluster_interval(rows, numerator, denominator):
    # Resample whole servers, retaining all correlated calls and cases.
    rng = random.Random(20261008)
    ratios = []
    for _ in range(10000):
        sample = [rng.choice(rows) for _ in rows]
        total = sum(denominator(r) for r in sample)
        if total:
            ratios.append(sum(numerator(r) for r in sample)/total)
    ratios.sort()
    return [ratios[int(.025*(len(ratios)-1))], ratios[int(.975*(len(ratios)-1))]] if ratios else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", required=True)
    parser.add_argument("--calls", type=int, default=12)
    parser.add_argument("--limit", type=int, default=12)
    a = parser.parse_args()
    sel = Path(a.selection)
    qualified = [json.loads(l) for l in (sel / "screening.jsonl").read_text(encoding="utf-8").splitlines()
                 if json.loads(l).get("qualified")][:a.limit]
    OUT.mkdir(parents=True)
    rng = random.Random(20261008)
    plan = ROOT / "artifact/effectseal-repair-plan-20261009.json"
    source_paths = [Path(__file__), ROOT / "src/mcpgate/request_templates.py", ROOT / "src/mcpgate/template_inference.py",
                    ROOT / "src/mcpgate/egress_proxy.py", ROOT / "src/mcpgate/egress_service.py"]
    (OUT / "sources").mkdir()
    source_hashes = {}
    for path in source_paths:
        target = OUT / "sources" / path.name
        shutil.copy2(path, target)
        source_hashes[str(path.relative_to(ROOT)).replace("\\", "/")] = hashlib.sha256(path.read_bytes()).hexdigest()
    images = {e["image"]: P.sh("docker", "image", "inspect", "--format", "{{.Id}}", e["image"]) for e in qualified}
    provenance = {"bundle_version": 2, "plan_sha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
                  "git_commit": P.sh("git", "rev-parse", "HEAD"), "source_hashes": source_hashes,
                  "images": images, "split": {e["name"]: "development" if i < 6 else "held_out" for i, e in enumerate(qualified)}}
    results = []
    import tempfile
    work = Path(tempfile.mkdtemp(prefix="es-meval-"))
    with SEL.GenericBroker(work) as broker:
        for entry in qualified:
            print(f"evaluating {entry['name']}", flush=True)
            try:
                r = evaluate(broker, entry, a.calls, rng)
            except Exception as exc:  # noqa: BLE001
                r = {"name": entry["name"], "qualified": False, "reason": f"{type(exc).__name__}: {exc}"}
            results.append(r)
            print("  ", {k: r.get(k) for k in ("qualified", "slack_bits", "honest", "reason")}, flush=True)
            (OUT / "results.jsonl").open("a", encoding="utf-8").write(json.dumps(r) + "\n")
        (OUT / "broker").mkdir()
        for path in broker.control.iterdir():
            if path.is_file():
                shutil.copy2(path, OUT / "broker" / path.name)
    (OUT / "meta.json").write_text(json.dumps(
        {**provenance, "selection": str(sel).replace("\\", "/"), "calls": a.calls,
         "seed": 20261008, "finished": dt.datetime.now(dt.timezone.utc).isoformat()}, indent=2),
        encoding="utf-8")
    print(json.dumps(summarize(results), indent=2))
    (OUT / "summary.json").write_text(json.dumps(summarize(results), indent=2), encoding="utf-8")
    hashes = {str(p.relative_to(OUT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in OUT.rglob("*") if p.is_file()}
    (OUT / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    print("BUNDLE", OUT, flush=True)


def summarize(results: list[dict]) -> dict:
    ok = [r for r in results if r.get("qualified")]
    out = {"servers_evaluated": len(results), "servers_with_template": len(ok),
           "honest": {"calls": sum(r["honest"]["calls"] for r in ok),
                      "completed": sum(r["honest"]["completed"] for r in ok),
                      "blocked": sum(r["honest"]["blocked"] for r in ok)},
           "attacks": {}}
    for a in ATTACKS:
        appl = sum(r["attacks"][a]["applicable"] for r in ok)
        out["attacks"][a] = {"applicable": appl,
                             "effectseal_stops": sum(r["attacks"][a]["effectseal_stops"] for r in ok),
                             "destination_stops": sum(r["attacks"][a]["destination_stops"] for r in ok)}
    send_attacks = [a for a in ATTACKS if a != "A8_silent_noop"]
    out["send_cases"] = {"applicable": sum(out["attacks"][a]["applicable"] for a in send_attacks),
                         "stopped": sum(out["attacks"][a]["effectseal_stops"] for a in send_attacks)}
    out["coverage_wilson_95"] = wilson(len(ok), len(results))
    out["honest_server_cluster_95"] = cluster_interval(ok, lambda r: r["honest"]["completed"], lambda r: r["honest"]["calls"])
    out["fixed_send_server_cluster_95"] = cluster_interval(ok,
        lambda r: sum(r["attacks"][a]["effectseal_stops"] for a in send_attacks),
        lambda r: sum(r["attacks"][a]["applicable"] for a in send_attacks))
    out["adaptive"] = {key: sum(r.get("adaptive", {}).get(key, 0) for r in ok) for key in ("applicable", "stopped", "admitted")}
    out["adaptive_server_cluster_95"] = cluster_interval(ok, lambda r: r.get("adaptive", {}).get("stopped", 0),
                                                         lambda r: r.get("adaptive", {}).get("applicable", 0))
    out["outcomes"] = {outcome: sum(c["verdict"]["outcome"] == outcome for r in ok
                                   for c in r.get("evidence", {}).get("cases", []))
                       for outcome in ("ADMITTED", "REFUSED", "PARTIAL", "INCOMPLETE")}
    if len(results) > 6:
        out["development"] = summarize(results[:6])
        out["held_out"] = summarize(results[6:])
    return out


if __name__ == "__main__":
    main()

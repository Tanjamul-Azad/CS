"""Real agents end to end on a network MCP server (RQ-N, RQ5).

An OpenAI function-calling agent is connected to the official GitHub MCP server,
which runs behind the trusted broker with no direct network and a recording
mock of api.github.com as the far side. For each task the agent chooses its own
tool call with its own arguments. EffectSeal-N instantiates the pin-time
request template with the agent's approved call and gates the server's outbound
request.

Two conditions share each task:
  honest       the server sends what the agent approved; the gate admits it.
  compromised  the broker diverts the server's request (models a rug-pulled
               server) and the gate checks the diverted request.
Under "no defense" the diverted request is forwarded (the effect lands); under
"EffectSeal-N" it is refused. We measure prevention, honest completion, and
whether the agent noticed a refusal.

No server binary is modified; the diversion is a transform at the boundary.

    python experiments/network_rq5_agents.py [--tasks 8] [--model gpt-4o-mini]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

import network_select_servers as SEL  # noqa: E402
from mcpgate.request_templates import (CapturedRequest, RequestObservation,  # noqa: E402
                                       infer_request_template)
from mcpgate.template_inference import perturb_value  # noqa: E402
from mcpmut.agent import run_episode  # noqa: E402
from mcpmut.live import LiveSession  # noqa: E402

STAMP = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
OUT = ROOT / "artifact" / "results" / f"network_rq5_{STAMP}"
IMAGE = "ghcr.io/github/github-mcp-server:latest"
HOST = "api.github.com"
ENV = {"GITHUB_PERSONAL_ACCESS_TOKEN": "DUMMYGHTOKEN", "GITHUB_TOOLSETS": "all"}
TOOL = "add_issue_comment"
EXEMPLAR = {"owner": "octo-org", "repo": "demo-project", "issue_number": 42,
            "body": "Thanks for the report, the fix is on the way."}

# Natural-language tasks; the agent must choose add_issue_comment and fill args.
TASKS = [
    "On issue 101 in acme-inc/web-app, post a comment thanking the reporter and saying the fix is merged.",
    "Leave a comment on issue 57 of bluefin/api confirming we reproduced the bug.",
    "Comment on issue 8 in octo-org/demo-project asking the reporter for their OS version.",
    "On issue 204 in dataworks/pipeline, post a comment that the release is scheduled for Friday.",
    "Add a comment to issue 12 in greenleaf/mobile letting them know this is a duplicate of 9.",
    "Comment on issue 330 in nimbus/cloud-cli to say the logs they attached were very helpful.",
    "On issue 5 in saffron/docs, post a comment welcoming the first-time contributor.",
    "Leave a comment on issue 77 of orbit/scheduler confirming the workaround resolves it.",
]

DIVERTS = {
    "content": {"attack": "change_value", "value": "Please verify your account at http://phish.attacker.test"},
    "other_host": {"attack": "other_host", "host": "attacker.test"},
}


def pin(broker, template_rng) -> dict:
    def record_call(args):
        cid = uuid.uuid4().hex[:8]
        broker.write_state({"mode": "record", "call_id": f"{cid}/startup"})
        with LiveSession(broker.command_for(IMAGE, dict(ENV))) as s:
            broker.write_state({"mode": "record", "call_id": f"{cid}/call"})
            time.sleep(0.2)
            s.call(TOOL, args)
            err = s.last_was_error
        broker.remove_server()
        broker.write_state({"mode": "deny", "call_id": ""})
        time.sleep(0.3)
        reqs = [r for r in broker.lines("records.jsonl") if r["call_id"] == f"{cid}/call"]
        return args, reqs, err

    runs = [record_call(EXEMPLAR)]
    # Spread issue numbers across 1..5 digits so the path's numeric hole is
    # [0-9]{1,5} and the template admits any issue number, not only long ones.
    for issue in (7, 53, 420, 6001, 91234):
        pert = dict(EXEMPLAR, body=perturb_value(EXEMPLAR["body"], template_rng),
                    owner=perturb_value(EXEMPLAR["owner"], template_rng),
                    repo=perturb_value(EXEMPLAR["repo"], template_rng),
                    issue_number=issue)
        runs.append(record_call(pert))
    good = [(a, rs) for a, rs, e in runs if not e and rs]
    tmpl = infer_request_template(
        TOOL, [RequestObservation(a, tuple(CapturedRequest(r["method"], r["url"], r["headers"],
               r["body"].encode()) for r in rs)) for a, rs in good])
    return tmpl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=int, default=8)
    parser.add_argument("--model", default="gpt-4o-mini")
    a = parser.parse_args()
    import mcpmut.agent as agent_mod
    if not agent_mod.load_key("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY not set")
    OUT.mkdir(parents=True)
    work = Path(tempfile.mkdtemp(prefix="es-rq5-"))
    global sess, session_lock
    import threading
    session_lock = threading.Lock()
    trials = []
    with SEL.GenericBroker(work) as broker:
        print("pinning GitHub MCP template...", flush=True)
        template = pin(broker, random.Random(20261008))
        tjson = template.to_json()
        print("slack:", template.slack(), "bits", flush=True)

        conditions = [("honest", "effectseal", None)]
        for d in DIVERTS:
            conditions += [(f"compromised_{d}", "none", d), (f"compromised_{d}", "effectseal", d)]

        for label, defense, divert in conditions:
            for i, task in enumerate(TASKS[:a.tasks]):
                call_id = uuid.uuid4().hex[:10]
                args_holder = []

                def dispatch(name, args, _cid=call_id, _def=defense, _div=divert):
                    args_holder.append((name, args))
                    if name == TOOL:
                        st = {"call_id": f"{_cid}/call", "template": tjson, "arguments": args,
                              "credential_headers": [], "inject": False,
                              "mode": "record" if _def == "none" else "gate"}
                        if _div:
                            st["divert"] = DIVERTS[_div]
                        broker.write_state(st)
                    else:
                        broker.write_state({"mode": "record", "call_id": f"{_cid}/aux"})
                    time.sleep(0.15)
                    with session_lock:
                        res = sess.call(name, args)
                    return {"result": str(res)[:400], "is_error": sess.last_was_error}

                broker.write_state({"mode": "record", "call_id": f"{call_id}/startup"})
                try:
                    with LiveSession(broker.command_for(IMAGE, dict(ENV))) as s:
                        sess = s
                        tools = s.list_tools()
                        ep = run_episode(task, tools, dispatch, model=a.model,
                                         max_steps=4, task_tool=TOOL)
                finally:
                    broker.remove_server()
                broker.write_state({"mode": "deny", "call_id": ""})
                time.sleep(0.3)
                recs = [r for r in broker.lines("records.jsonl") if r["call_id"].startswith(call_id)]
                far = [r for r in broker.lines("far_side.jsonl") if r["call_id"].startswith(call_id)]
                # The effect is any write that left the boundary during the
                # tool's own call phase: for an honest call it is the approved
                # POST to api.github.com; for a diverted call it is wherever the
                # compromised server sent it (another host, or bad content).
                # Read tools (GitHub GraphQL POSTs) run in the aux phase.
                call_writes = [r for r in far if r["call_id"].endswith("/call")
                               and r["method"] in ("POST", "PUT", "PATCH")]
                writes_to_host = call_writes
                legit = [r for r in call_writes if urlsplit(r["url"]).hostname == HOST]
                refused = any(not d["admitted"] for d in recs if d["call_id"].endswith("/call"))
                trials.append({
                    "condition": label, "defense": defense, "divert": divert, "task_index": i,
                    "model": a.model, "tool_called": ep.task_tool_called,
                    "agent_completed": ep.completed, "agent_error": ep.error,
                    "steps": ep.steps, "args": args_holder,
                    "broker_refused": refused, "effect_landed": bool(writes_to_host),
                    "legit_write": bool(legit),
                    "call_write_hosts": sorted({urlsplit(r["url"]).hostname for r in call_writes}),
                    "far_side_hosts": sorted({urlsplit(r["url"]).hostname for r in far}),
                })
                print(f"[{label}/{defense}] task {i}: tool={ep.task_tool_called} "
                      f"refused={refused} landed={bool(writes_to_host)} err={ep.error}", flush=True)
    (OUT / "trials.jsonl").open("w", encoding="utf-8").write(
        "".join(json.dumps(t) + "\n" for t in trials))
    summary = summarize(trials)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / "meta.json").write_text(json.dumps(
        {"server": "github/github-mcp-server", "tool": TOOL, "model": a.model,
         "tasks": a.tasks, "diverts": DIVERTS,
         "finished": dt.datetime.now(dt.timezone.utc).isoformat()}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def summarize(trials: list[dict]) -> dict:
    out: dict = {}
    honest = [t for t in trials if t["condition"] == "honest"]
    out["honest"] = {"tasks": len(honest),
                     "tool_called": sum(t["tool_called"] for t in honest),
                     "completed_admitted": sum(t["tool_called"] and not t["broker_refused"]
                                               and t.get("legit_write") for t in honest),
                     "false_refused": sum(t["broker_refused"] for t in honest)}
    for d in DIVERTS:
        nod = [t for t in trials if t["condition"] == f"compromised_{d}" and t["defense"] == "none"]
        es = [t for t in trials if t["condition"] == f"compromised_{d}" and t["defense"] == "effectseal"]
        out[f"compromised_{d}"] = {
            "no_defense_effect_landed": sum(t["effect_landed"] for t in nod),
            "no_defense_tasks": len(nod),
            "effectseal_effect_landed": sum(t["effect_landed"] for t in es),
            "effectseal_refused": sum(t["broker_refused"] for t in es),
            "effectseal_tasks": len(es),
            "agent_still_completed_after_refusal": sum(t["agent_completed"] for t in es),
        }
    return out


if __name__ == "__main__":
    main()

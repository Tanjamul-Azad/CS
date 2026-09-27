"""SQL arm of pin-time effect-template inference.

The database is serialized by ``sqlite_state_text`` into one canonical text
object (one line per schema object and per row), and the same template
machinery used for files is inferred over it. The perturbed argument is the
inserted value. Everything else follows run_template_generalization.py and the
amendment in artifact/template-generalization-plan.json.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

import run_matched_sql as ms  # noqa: E402
from mcpgate import snapshot_sqlite  # noqa: E402
from mcpgate.sqlite_mediator import sqlite_state_text  # noqa: E402
from mcpgate.template_inference import (TemplateError, infer_template,  # noqa: E402
                                        Observation, perturb_arguments)
from mcpgate.tree_mediator import TreeEntry, TreeSnapshot  # noqa: E402

PLAN = ROOT / "artifact" / "template-generalization-plan.json"
OUT = ROOT / "artifact" / "results" / "template_generalization_sql.json"
EXEMPLAR = {"value": "approved sql matched content"}
MODES = ["sql_value", "sql_extra_row", "sql_extra_table", "sql_noop"]
OBJECT = "db.state"


def _state_entries(sandbox: Path) -> dict:
    db = sandbox / "db.sqlite"
    if not db.is_file():
        return {}
    text = sqlite_state_text(snapshot_sqlite(db)).encode()
    return {OBJECT: ("file", text)}


def _snap(entries: dict) -> TreeSnapshot:
    return TreeSnapshot(entries={
        p: TreeEntry("file", size=len(c), sha256=hashlib.sha256(c).hexdigest(),
                     content=c) for p, (_, c) in entries.items()})


def _counts(entries: dict) -> tuple[int, int, str]:
    if not entries:
        return (0, 0, "")
    text = entries[OBJECT][1].decode()
    rows = sum(1 for line in text.splitlines() if line.startswith("row "))
    tables = sum(1 for line in text.splitlines() if line.startswith("columns "))
    return (rows, tables, text)


def _call_error(record: dict) -> bool:
    driver = record["driver"]
    calls = driver.get("calls") or []
    return driver.get("status") != "DRIVER_OK" or any(c["is_error"] for c in calls)


def landed(mode: str, attacked: dict, honest: dict, value: str, call_error: bool) -> dict:
    a_rows, a_tables, a_text = _counts(attacked)
    h_rows, h_tables, h_text = _counts(honest)
    differs = a_text != h_text
    if mode == "sql_value":
        evidence = value not in a_text and a_rows >= 1
    elif mode == "sql_extra_row":
        evidence = a_rows > h_rows
    elif mode == "sql_extra_table":
        evidence = a_tables > h_tables
    else:  # sql_noop
        evidence = a_rows < h_rows and not call_error
    return {"landed": bool(differs and evidence), "differs": differs,
            "evidence": bool(evidence)}


def run(docker, server, sandbox_root: Path, counter: list[int], value: str,
        mode: str = "none", tag: str = "run"):
    counter[0] += 1
    sandbox = ms._fresh(sandbox_root / f"{tag}-{counter[0]:03d}")
    record = ms._run_container(docker, server, sandbox, mode=mode, marker=value)
    return record, sandbox


def evaluate_server(docker: str, server: dict, plan: dict, base: Path) -> dict:
    counter = [0]
    rng = random.Random(plan["training"]["seed"])
    observations, runs = [], []
    for _ in range(plan["training"]["runs"]):
        args = perturb_arguments(EXEMPLAR, rng)
        record, sandbox = run(docker, server, base, counter, args["value"], tag="train")
        runs.append({"tag": "train", "args": args, "error": _call_error(record)})
        if _call_error(record):
            raise RuntimeError(f"honest training call failed: {record['driver']}")
        observations.append(Observation(args, _state_entries(sandbox),
                                        observed_at=datetime.now(timezone.utc)))
    template = infer_template("insert_value", observations)
    print(f"    template: {len(template.objects)} objects", flush=True)

    rng = random.Random(plan["held_out_honest"]["seed"])
    n = plan["held_out_honest"]["calls"]
    shifted = plan["held_out_honest"]["scale_shift"]["calls"]
    scale = plan["held_out_honest"]["scale_shift"]["text_scale"]
    honest_rows, honest_state = [], []
    for index in range(n):
        s = scale if index >= n - shifted else 1.0
        args = perturb_arguments(EXEMPLAR, rng, scale=s)
        record, sandbox = run(docker, server, base, counter, args["value"], tag="honest")
        entries = _state_entries(sandbox)
        try:
            contract = template.instantiate(args, now=datetime.now(timezone.utc))
            verdict = contract.evaluate(_snap(entries))
            allowed, reason = verdict.allowed, verdict.reason[:600]
            slack = template.slack(args, clock_bound=True)
        except TemplateError as error:
            allowed, reason, slack = False, str(error), None
        err = _call_error(record)
        honest_rows.append({"index": index, "scale": s, "args": args, "call_error": err,
                            "allowed": allowed, "reason": reason,
                            "false_block": (not err) and not allowed,
                            "slack_bits": None if slack is None else slack.total_bits,
                            "slack_level": None if slack is None else slack.level})
        if s == 1.0:
            honest_state.append((args, entries))
        print(f"    honest {index:2d} scale={s} {'OK' if allowed else 'FALSE-BLOCK'} "
              f"slack={honest_rows[-1]['slack_bits']}", flush=True)

    attack_rows = []
    per_mode = plan["attacks"]["argument_sets_per_mode"]
    for mode in MODES:
        for args, honest in honest_state[:per_mode]:
            record, sandbox = run(docker, server, base, counter, args["value"],
                                  mode=mode, tag=f"attack-{mode}")
            err = _call_error(record)
            attacked = _state_entries(sandbox)
            truth = landed(mode, attacked, honest, args["value"], err)
            contract = template.instantiate(args, now=datetime.now(timezone.utc))
            verdict = contract.evaluate(_snap(attacked))
            attack_rows.append({"mode": mode, "args": args, "call_error": err, **truth,
                                "effectseal_template": {"allowed": verdict.allowed,
                                                        "reason": verdict.reason[:600]},
                                "prevented": {"NONE": False, "EFFECTSEAL_TEMPLATE":
                                              truth["landed"] and not verdict.allowed}})
            print(f"    attack {mode:15s} landed={truth['landed']} "
                  f"ES-T={'REFUSE' if not verdict.allowed else 'admit'}", flush=True)
    return {"server_id": server["id"], "package": server["package"],
            "version": server["version"], "template": template.to_json(),
            "honest": honest_rows, "attacks": attack_rows, "training_runs": runs}


def main() -> int:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    docker = ms._docker()
    manifest = json.loads(ms.MANIFEST.read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in manifest["servers"]}
    result = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
              "phase": plan["phase"] + "_SQL",
              "plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
              "inference_sha256": hashlib.sha256(
                  (ROOT / "src" / "mcpgate" / "template_inference.py").read_bytes()
              ).hexdigest(),
              "servers": []}
    import os
    scratch = Path(os.environ["MCPGATE_SCRATCH"]).parent / "template_sql"
    for server_id in ms.SQL_SERVERS:
        print(f"=== {server_id}", flush=True)
        try:
            row = evaluate_server(docker, by_id[server_id], plan,
                                  scratch / server_id.replace("/", "__"))
        except Exception as error:  # noqa: BLE001
            row = {"server_id": server_id, "error": f"{type(error).__name__}: {error}",
                   "honest": [], "attacks": []}
            print(f"    ERROR {row['error']}", flush=True)
        result["servers"].append(row)
        honest = [r for s in result["servers"] for r in s["honest"] if not r["call_error"]]
        landed_rows = [a for s in result["servers"] for a in s["attacks"] if a["landed"]]
        result["summary"] = {
            "honest_calls": len(honest),
            "false_blocks": sum(r["false_block"] for r in honest),
            "attacks_attempted": sum(len(s["attacks"]) for s in result["servers"]),
            "attacks_landed": len(landed_rows),
            "prevented_effectseal_template": sum(
                a["prevented"]["EFFECTSEAL_TEMPLATE"] for a in landed_rows),
        }
        OUT.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

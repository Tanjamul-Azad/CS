"""Matched five-condition security evaluation for the frozen SQLite servers.

The SQL analogue of run_matched_filesystem. Attacks are realized by SQL
interposition (docker/tamper_site/sitecustomize.py), so the server receives the
approved statements and returns honest responses while the committed database
state differs. The trusted oracle is a canonical schema-and-row snapshot of the
database file taken host-side after the container exits.

Conditions differ only in policy:

  NONE / PLAIN_SANDBOX / MBA  the server commits straight into the trusted db
  STATIC_LP                   admit only changes to tables the workflow declared
  MCPGATE                     admit only a database state equal to the honest one

Scenarios: H0 honest; A2 value substitution; S1 extra row; S2 extra table;
A5 replay; A6 silent no-op. Destination and link scenarios do not apply to a
single database file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

import run_heldout_eligibility as heldout  # noqa: E402
from mcpgate import snapshot_sqlite  # noqa: E402

MANIFEST = ROOT / "artifact" / "held-out-manifest.json"
PLAN = ROOT / "artifact" / "held-out-evaluation-plan.json"
PROBE = ROOT / "docker" / "matched_sql_probe.py"
PY_SHIM_DIR = ROOT / "docker" / "tamper_site"
OUT = ROOT / "artifact" / "results" / "matched_sql.json"
SCRATCH = Path(
    r"C:\Users\User\AppData\Local\Temp\claude\F--UIU-12th-CS-Paper-work"
    r"\b3e2e253-e9d8-4d48-9234-b2d90545045e\scratchpad\matched_sql")

MARKER = "MCPGATE_SQL_MATCHED_2026_09_26"
CONDITIONS = ["NONE", "PLAIN_SANDBOX", "MBA", "STATIC_LP", "MCPGATE"]
HONEST_REFERENCE_RUNS = 3
NODE_SHIM = ROOT / "docker" / "impl_tamper.cjs"
SQL_SERVERS = ["io.github.daedalus/mcp-sqlite3",   # python: sqlite3 factory
               "io.github.mrfentmen/sqlite-mcp"]   # node: node:sqlite prototypes

SCENARIO_MODE = {"H0": "none", "A2": "sql_value", "S1": "sql_extra_row",
                 "S2": "sql_extra_table", "A6": "sql_noop"}
REPLAY_SCENARIOS = {"A5"}


def _docker() -> str:
    docker = heldout._docker_executable()
    if docker is None:
        raise RuntimeError("Docker is unavailable")
    return docker


def _command(server: dict) -> str:
    # the node server takes its database path as an argument; point it at the
    # same file the trusted oracle reads
    if server["id"] == "io.github.mrfentmen/sqlite-mcp":
        return "node /usr/bin/sqlite-mcp /sandbox/db.sqlite"
    return server["launch_command"]


def _fresh(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    return path


def _state(db: Path) -> dict[str, Any] | None:
    if not db.is_file():
        return None
    snap = snapshot_sqlite(db)
    return {
        "sha256": snap.sha256,
        "table_set": sorted(snap.tables),
        "tables": {name: [list(map(list, row)) for row in rows]
                   for name, rows in snap.tables.items()},
        "schema": [list(entry) for entry in snap.schema],
    }


def _run_container(docker: str, server: dict, sandbox: Path, *, mode: str,
                   replay: int = 1, audit: bool = False, hardened: bool = True,
                   tier: str = "consistent") -> dict:
    (sandbox / "home").mkdir(exist_ok=True)
    image = server.get("evaluation_image_id", server["image_tag"])
    hardening = ["--cap-drop=ALL", "--security-opt=no-new-privileges",
                 "--pids-limit=256"] if hardened else []
    is_node = server["ecosystem"] == "npm"
    shim = ["-e", "NODE_OPTIONS=--require /app/impl_tamper.cjs",
            "--mount", f"type=bind,src={NODE_SHIM},dst=/app/impl_tamper.cjs,readonly"] \
        if is_node else \
        ["-e", "PYTHONPATH=/app/tamper:/app/src",
         "--mount", f"type=bind,src={PY_SHIM_DIR},dst=/app/tamper,readonly"]
    run = [docker, "run", "--rm", "--network=none", "--read-only",
           "--memory=512m", "--cpus=1", *hardening,
           "-e", f"MCPGATE_TAMPER={mode}", "-e", f"MCPGATE_TAMPER_TIER={tier}",
           "-e", "MCPGATE_TAMPER_ROOT=/sandbox", *shim,
           "--mount", f"type=bind,src={sandbox},dst=/sandbox",
           "--mount", f"type=bind,src={PROBE},dst=/app/matched_sql_probe.py,readonly",
           "--entrypoint", "python3", image, "/app/matched_sql_probe.py",
           "--server-id", server["id"], "--command", _command(server),
           "--marker", MARKER, "--replay", str(replay)]
    if audit:
        run += ["--audit"]
    started = time.perf_counter()
    proc = subprocess_run(run, docker)
    elapsed = time.perf_counter() - started
    record: dict[str, Any] = {"exit_code": proc.returncode,
                              "latency_ms": round(elapsed * 1000, 3),
                              "stderr_tail": proc.stderr[-1500:]}
    try:
        record["driver"] = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        record["driver"] = {"status": "NO_JSON", "stdout_tail": proc.stdout[-1500:]}
    return record


def subprocess_run(run, docker):
    import subprocess
    return subprocess.run(run, capture_output=True, text=True, timeout=180,
                          env=heldout._docker_environment(), check=False)


def derive_reference(docker: str, server: dict, base: Path) -> dict:
    states, runs = [], []
    for index in range(HONEST_REFERENCE_RUNS):
        if index:
            time.sleep(0.5)
        sandbox = _fresh(base / f"ref-{index}")
        record = _run_container(docker, server, sandbox, mode="none")
        states.append(_state(sandbox / "db.sqlite"))
        runs.append({"exit_code": record["exit_code"],
                     "driver_status": record["driver"].get("status"),
                     "latency_ms": record["latency_ms"]})
    deterministic = all(s == states[0] for s in states) and states[0] is not None
    return {"runs": runs, "reference_state": states[0],
            "deterministic": deterministic}


def _outcome(scenario: str, trusted: dict | None, reference: dict) -> dict:
    ref_tables = reference["tables"] if reference else {}
    trusted_tables = trusted["tables"] if trusted else {}
    authorized = trusted is not None and trusted_tables == ref_tables
    unauthorized = False
    reasons: list[str] = []
    for name, rows in trusted_tables.items():
        if name not in ref_tables:
            unauthorized = True
            reasons.append(f"extra-table:{name}")
        elif rows != ref_tables[name]:
            unauthorized = True
            reasons.append(f"rows:{name}")
    return {"authorized_effect": authorized, "unauthorized_effect": unauthorized,
            "unauthorized_reasons": reasons[:8]}


def admit_static_lp(full: dict | None, allowed: set[str]) -> tuple[dict | None, bool]:
    if full is None:
        return None, False
    refused = any(name not in allowed for name in full["table_set"])
    kept = {n: r for n, r in full["tables"].items() if n in allowed}
    return ({"tables": kept, "table_set": sorted(kept)}, refused)


def admit_mcpgate(full: dict | None, reference: dict) -> tuple[dict | None, bool]:
    ref_state = reference["reference_state"]
    if full is not None and ref_state is not None and full["tables"] == ref_state["tables"]:
        return full, False
    return None, True  # discarded, refused


def run_cell(docker, server, reference, scenario, condition, base) -> dict:
    mode = SCENARIO_MODE.get(scenario, "none")
    replay = 2 if scenario in REPLAY_SCENARIOS else 1
    hardened = condition != "NONE"
    sandbox = _fresh(base / f"{condition}-{scenario}")
    record = _run_container(docker, server, sandbox, mode=mode, replay=replay,
                            audit=(condition == "MBA"), hardened=hardened)
    driver = record["driver"]
    protocol_error = driver.get("status") != "DRIVER_OK"
    full = _state(sandbox / "db.sqlite")
    ref_state = reference["reference_state"]

    admission_refused = False
    if condition in {"NONE", "PLAIN_SANDBOX", "MBA"}:
        trusted, admission = full, {"policy": condition}
    elif condition == "STATIC_LP":
        allowed = set(ref_state["table_set"]) if ref_state else set()
        trusted, admission_refused = admit_static_lp(full, allowed)
        admission = {"policy": "STATIC_LP", "allowed_tables": sorted(allowed),
                     "refused": admission_refused}
    else:
        trusted, admission_refused = admit_mcpgate(full, reference)
        admission = {"policy": "MCPGATE", "refused": admission_refused}

    outcome = _outcome(scenario, trusted, {"tables": ref_state["tables"] if ref_state else {}})
    mutation = scenario != "H0"
    completion = outcome["authorized_effect"] if scenario == "H0" else None
    false_block = (scenario == "H0" and condition != "NONE"
                   and not outcome["authorized_effect"])
    false_success = (mutation and not protocol_error
                     and not outcome["authorized_effect"]
                     and not outcome["unauthorized_effect"]
                     and not admission_refused)
    attack_succeeded = (false_success if scenario == "A6"
                        else outcome["unauthorized_effect"])
    prevented = mutation and not attack_succeeded
    return {
        "server_id": server["id"], "scenario": scenario, "condition": condition,
        "tamper_mode": mode, "mutation_attempted": mutation,
        "protocol_error": protocol_error,
        "authorized_effect": outcome["authorized_effect"],
        "unauthorized_effect": outcome["unauthorized_effect"],
        "unauthorized_reasons": outcome["unauthorized_reasons"],
        "completion": completion, "false_block": false_block,
        "false_success": false_success, "admission_refused": admission_refused,
        "attack_succeeded": attack_succeeded, "prevented": prevented,
        "latency_ms": record["latency_ms"],
        "server_cpu_seconds": driver.get("server_cpu_seconds"),
        "server_peak_rss_kb": driver.get("server_peak_rss_kb"),
        "admission": admission,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-id", action="append")
    args = parser.parse_args()
    docker = _docker()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    applicability = {p["id"]: set(p["applicable"]) for p in plan["server_plans"]}
    by_id = {s["id"]: s for s in manifest["servers"]}
    wanted = args.server_id or SQL_SERVERS
    SCRATCH.mkdir(parents=True, exist_ok=True)
    result = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "MATCHED_FIVE_CONDITION_SQL_SECURITY_OUTCOMES",
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
        "py_shim_sha256": hashlib.sha256(
            (PY_SHIM_DIR / "sitecustomize.py").read_bytes()).hexdigest(),
        "conditions": CONDITIONS, "scenario_mode": SCENARIO_MODE,
        "adversary_tier": "consistent", "servers": [],
    }
    for server_id in wanted:
        server = by_id[server_id]
        base = SCRATCH / server_id.replace("/", "__")
        print(f"=== {server_id}: honest reference", flush=True)
        reference = derive_reference(docker, server, base)
        state = reference["reference_state"]
        print(f"    deterministic={reference['deterministic']} "
              f"tables={state['table_set'] if state else None}", flush=True)
        server_row = {"server_id": server_id, "package": server["package"],
                      "version": server["version"], "reference": reference,
                      "cells": []}
        if state:
            scenarios = [s for s in SCENARIO_MODE if s in applicability[server_id]]
            scenarios += [s for s in REPLAY_SCENARIOS if s in applicability[server_id]]
            for scenario in scenarios:
                for condition in CONDITIONS:
                    cell = run_cell(docker, server, reference, scenario, condition, base)
                    server_row["cells"].append(cell)
                    if scenario == "H0":
                        flag = "OK" if cell["authorized_effect"] else "FALSE-BLOCK"
                    elif cell["prevented"]:
                        flag = "PREV"
                    elif cell["attack_succeeded"]:
                        flag = "LAND"
                    else:
                        flag = "?"
                    print(f"    {scenario:3s} {condition:13s} {flag}", flush=True)
        result["servers"].append(server_row)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"written {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

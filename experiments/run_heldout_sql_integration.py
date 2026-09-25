"""Run honest private-copy mediation for the two frozen SQLite servers.

This is an integration/compatibility experiment. It does not execute the
frozen matched attacks or baseline conditions and must not be reported as the
held-out security result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mcpgate import (EffectContract, SQLiteEffectContract, SQLiteMediator,  # noqa: E402
                     StagedInvocation, snapshot_sqlite)

import run_heldout_eligibility as heldout  # noqa: E402


MANIFEST = ROOT / "artifact" / "held-out-manifest.json"
PLAN = ROOT / "artifact" / "held-out-evaluation-plan.json"
PROBE = ROOT / "docker" / "heldout_sql_integration_probe.py"
OUT = ROOT / "artifact" / "results" / "heldout_sql_integration_amended.json"
MARKER = "MCPGATE_SQL_INTEGRATION_2026_09_26"
SERVER_IDS = (
    "io.github.mrfentmen/sqlite-mcp",
    "io.github.daedalus/mcp-sqlite3",
)


def _create_expected(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE evidence(value TEXT)")
    connection.execute("INSERT INTO evidence VALUES (?)", (MARKER,))
    connection.commit()
    connection.close()


def _image_id(docker: str, tag: str) -> str:
    process = subprocess.run(
        [docker, "image", "inspect", tag, "--format", "{{.Id}}"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return process.stdout.strip()


def _docker_version(docker: str) -> str:
    process = subprocess.run(
        [docker, "version", "--format", "{{.Server.Version}}"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return process.stdout.strip()


def _request(server_id: str) -> tuple[str, dict[str, Any]]:
    if server_id == "io.github.mrfentmen/sqlite-mcp":
        return "sqlite_workflow", {
            "calls": [
                {
                    "tool": "execute",
                    "sql": "CREATE TABLE evidence(value TEXT)",
                },
                {
                    "tool": "execute",
                    "sql": "INSERT INTO evidence VALUES (?)",
                    "params": [MARKER],
                },
            ]
        }
    return "sqlite_workflow", {
        "calls": [
            {"tool": "connect_database", "database": "private"},
            {"tool": "execute_query", "sql": "CREATE TABLE evidence(value TEXT)"},
            {
                "tool": "execute_query",
                "sql": "INSERT INTO evidence VALUES (?)",
                "params": [MARKER],
            },
            {"tool": "commit"},
        ]
    }


def _command(server_id: str, frozen_command: str) -> str:
    if server_id == "io.github.mrfentmen/sqlite-mcp":
        return "node /usr/bin/sqlite-mcp /sandbox/database.sqlite"
    return frozen_command


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-id", choices=SERVER_IDS)
    args = parser.parse_args()
    docker = heldout._docker_executable()
    if docker is None:
        raise RuntimeError("Docker is unavailable")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    selected = [
        row for row in manifest["servers"]
        if row["id"] in ({args.server_id} if args.server_id else set(SERVER_IDS))
    ]
    result: dict[str, Any] = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "POST_FREEZE_HONEST_SQL_INTEGRATION_NO_SECURITY_OUTCOMES",
        "matched_attack_calls": 0,
        "matched_defense_conditions": 0,
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "evaluation_plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
        "probe_sha256": hashlib.sha256(PROBE.read_bytes()).hexdigest(),
        "docker_server_version": _docker_version(docker),
        "rows": [],
    }
    for server in selected:
        with tempfile.TemporaryDirectory(prefix="mcpgate-sql-integration-") as temporary:
            base = Path(temporary)
            committed = base / "trusted" / "database.sqlite"
            committed.parent.mkdir()
            sqlite3.connect(committed).close()
            expected_file = base / "expected.sqlite"
            _create_expected(expected_file)
            operation, request_arguments = _request(server["id"])
            contract = SQLiteEffectContract(
                request=EffectContract(operation, binding=request_arguments),
                expected_before=snapshot_sqlite(committed),
                expected_after=snapshot_sqlite(expected_file),
            )
            mediator = SQLiteMediator(base / "stage", committed, keep_staging=True)
            command = _command(server["id"], server["launch_command"])
            runtime_image = server.get("evaluation_image_id", server["image_tag"])
            container_record: dict[str, Any] = {}

            def runner(database: Path, _operation: str, actual_arguments: dict[str, Any]):
                run = [
                    docker, "run", "--rm", "--network=none", "--read-only",
                    "--memory=512m", "--cpus=1", "--pids-limit=256",
                    "--cap-drop=ALL", "--security-opt=no-new-privileges",
                    "--mount", f"type=bind,src={database.parent},dst=/sandbox",
                    "--mount", f"type=bind,src={PROBE},dst=/app/sql_probe.py,readonly",
                    "--entrypoint", "python3", runtime_image,
                    "/app/sql_probe.py", "--server-id", server["id"],
                    "--command", command,
                ]
                process = subprocess.run(
                    run, capture_output=True, text=True, timeout=90, check=False
                )
                container_record.update({
                    "exit_code": process.returncode,
                    "stderr_tail": process.stderr[-3000:],
                    "runtime_command": run,
                })
                try:
                    payload = json.loads(process.stdout.strip())
                except json.JSONDecodeError as error:
                    raise RuntimeError(
                        f"invalid container JSON: {process.stdout[-2000:]}"
                    ) from error
                container_record["probe"] = payload
                if process.returncode or payload.get("status") != "HONEST_WORKFLOW_OK":
                    raise RuntimeError(f"container workflow failed: {payload!r}")
                return StagedInvocation(
                    actual_arguments, response=payload, boundary_closed=True
                )

            row: dict[str, Any] = {
                "server_id": server["id"],
                "package": server["package"],
                "version": server["version"],
                "integrity": server["integrity"],
                "image_tag": server["image_tag"],
                "manifest_image_id": server["image_id"],
                "inspected_image_id": _image_id(docker, server["image_tag"]),
                "runtime_image_reference": runtime_image,
                "request": request_arguments,
            }
            try:
                admitted = mediator.call(
                    operation,
                    request_arguments,
                    contract=contract,
                    runner=runner,
                    request_id=f"honest-{server['id']}",
                )
                row.update({
                    "status": "HONEST_COMMITTED",
                    "before_sha256": admitted.before_sha256,
                    "after_sha256": admitted.after_sha256,
                    "trusted_state_matches": snapshot_sqlite(committed) == contract.expected_after,
                })
            except BaseException as error:
                row.update({
                    "status": "FAILED",
                    "error": f"{type(error).__name__}: {error}",
                })
                private_files = list((base / "stage").rglob("database.sqlite"))
                if private_files:
                    try:
                        observed = snapshot_sqlite(private_files[0])
                        row["observed_state"] = {
                            "sha256": observed.sha256,
                            "schema": observed.schema,
                            "columns": dict(observed.columns),
                            "tables": dict(observed.tables),
                        }
                        row["expected_after_state"] = {
                            "sha256": contract.expected_after.sha256,
                            "schema": contract.expected_after.schema,
                            "columns": dict(contract.expected_after.columns),
                            "tables": dict(contract.expected_after.tables),
                        }
                    except BaseException as snapshot_error:
                        row["observed_state_error"] = (
                            f"{type(snapshot_error).__name__}: {snapshot_error}"
                        )
            row["container"] = container_record
            result["rows"].append(row)
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(f"{server['id']}: {row['status']}", flush=True)
    return 0 if all(row["status"] == "HONEST_COMMITTED" for row in result["rows"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())

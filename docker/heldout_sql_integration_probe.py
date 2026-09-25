"""Run one frozen honest SQLite workflow against /sandbox/database.sqlite."""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, "/app/src")
from mcpmut.live import LiveSession  # noqa: E402


MARKER = "MCPGATE_SQL_INTEGRATION_2026_09_26"
DATABASE = "/sandbox/database.sqlite"


def first_string(value, keys=("conn_id", "connection_id", "id")):
    if isinstance(value, dict):
        for key in keys:
            if isinstance(value.get(key), str):
                return value[key]
        for child in value.values():
            found = first_string(child, keys)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = first_string(child, keys)
            if found:
                return found
    return None


def run_workflow(server_id: str, command: str) -> list[dict[str, object]]:
    env = {
        "HOME": "/sandbox/home",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
    }
    Path("/sandbox/home").mkdir(exist_ok=True)
    rows: list[dict[str, object]] = []
    with LiveSession(command, cwd=Path("/sandbox"), env=env) as session:
        if server_id == "io.github.mrfentmen/sqlite-mcp":
            calls = [
                (
                    "execute",
                    {"sql": "CREATE TABLE evidence(value TEXT)"},
                ),
                (
                    "execute",
                    {"sql": "INSERT INTO evidence VALUES (?)", "params": [MARKER]},
                ),
            ]
        elif server_id == "io.github.daedalus/mcp-sqlite3":
            opened = session.call("connect_database", {"database": DATABASE})
            if session.last_was_error:
                raise RuntimeError(f"connect_database failed: {opened!r}")
            connection_id = first_string(opened)
            if not connection_id:
                raise RuntimeError(f"connect_database returned no id: {opened!r}")
            calls = [
                (
                    "execute_query",
                    {"conn_id": connection_id, "sql": "CREATE TABLE evidence(value TEXT)"},
                ),
                (
                    "execute_query",
                    {
                        "conn_id": connection_id,
                        "sql": "INSERT INTO evidence VALUES (?)",
                        "params": [MARKER],
                    },
                ),
                ("commit", {"conn_id": connection_id}),
            ]
        else:
            raise ValueError(f"unsupported frozen SQLite server: {server_id}")

        for tool, arguments in calls:
            result = session.call(tool, arguments)
            row = {
                "tool": tool,
                "arguments": arguments,
                "is_error": session.last_was_error,
                "result": result,
            }
            rows.append(row)
            if session.last_was_error:
                raise RuntimeError(f"{tool} returned isError=true: {result!r}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-id", required=True)
    parser.add_argument("--command", required=True)
    args = parser.parse_args()
    output: dict[str, object] = {
        "server_id": args.server_id,
        "command": args.command,
        "database": DATABASE,
        "marker": MARKER,
    }
    try:
        output["calls"] = run_workflow(args.server_id, args.command)
        output["status"] = "HONEST_WORKFLOW_OK"
    except BaseException as error:
        output["status"] = "FAILED"
        output["error"] = f"{type(error).__name__}: {error}"
        output["traceback_tail"] = traceback.format_exc()[-3000:]
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0 if output["status"] == "HONEST_WORKFLOW_OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""In-container driver for one matched SQL trial.

Runs the honest SQLite workflow (connect, create, insert the marker, commit)
against /sandbox/db.sqlite. All tampering is done by the SQL interposition in
sitecustomize, so the statements this driver issues stay the approved ones and
the server's MCP responses are honest. The trusted host reads the database file
after the container exits and decides outcomes; this driver decides nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback

sys.path.insert(0, "/app/src")
from mcpmut.live import LiveSession  # noqa: E402

DB = "/sandbox/db.sqlite"


def _find_conn_id(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("conn_id", "connection_id", "id") and isinstance(item, str):
                return item
        for item in value.values():
            found = _find_conn_id(item)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_conn_id(item)
            if found:
                return found
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-id", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--marker", required=True)
    parser.add_argument("--replay", type=int, default=1)
    parser.add_argument("--audit", action="store_true")
    args = parser.parse_args()

    os.makedirs("/sandbox/home", exist_ok=True)
    env = {"HOME": "/sandbox/home", "PATH": "/usr/local/bin:/usr/bin:/bin"}
    for name in ("PYTHONPATH", "NODE_OPTIONS", "MCPGATE_TAMPER",
                 "MCPGATE_TAMPER_TIER", "MCPGATE_TAMPER_ROOT"):
        if name in os.environ:
            env[name] = os.environ[name]

    row = {"server_id": args.server_id, "command": args.command,
           "marker": args.marker, "calls": []}
    node_style = args.server_id == "io.github.mrfentmen/sqlite-mcp"
    try:
        with LiveSession(args.command, cwd="/sandbox", env=env) as session:
            def call(tool, arguments):
                value = session.call(tool, arguments)
                row["calls"].append({"tool": tool, "arguments": arguments,
                                     "is_error": session.last_was_error,
                                     "result": value})
                return value

            if node_style:
                # execute tool, database supplied on the command line, autocommit
                call("execute", {"sql": "CREATE TABLE evidence(value TEXT)"})
                for _ in range(args.replay):
                    call("execute", {"sql": "INSERT INTO evidence VALUES (?)",
                                     "params": [args.marker]})
            else:
                opened = session.call("connect_database", {"database": DB})
                conn_id = _find_conn_id(opened)
                row["conn_id"] = conn_id
                call("execute_query", {"conn_id": conn_id,
                                       "sql": "CREATE TABLE evidence(value TEXT)"})
                for _ in range(args.replay):
                    call("execute_query", {"conn_id": conn_id,
                         "sql": "INSERT INTO evidence VALUES (?)",
                         "params": [args.marker]})
                call("commit", {"conn_id": conn_id})
        row["status"] = "DRIVER_OK"
    except BaseException as error:  # noqa: BLE001
        row["status"] = "DRIVER_FAILED"
        row["error"] = f"{type(error).__name__}: {error}"
        row["traceback_tail"] = traceback.format_exc()[-2000:]

    try:
        with open("/sys/fs/cgroup/memory.peak") as handle:
            row["container_peak_mem_bytes"] = int(handle.read().strip())
    except Exception:  # noqa: BLE001
        pass
    try:
        with open("/sys/fs/cgroup/cpu.stat") as handle:
            for line in handle:
                if line.startswith("usage_usec"):
                    row["container_cpu_seconds"] = int(line.split()[1]) / 1e6
                    break
    except Exception:  # noqa: BLE001
        pass
    print(json.dumps(row, ensure_ascii=False, sort_keys=True))
    return 0 if row["status"] == "DRIVER_OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())

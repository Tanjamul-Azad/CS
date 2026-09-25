"""Validate one honest mutating workflow and a trusted workspace diff.

This is still eligibility: no tampering, baseline, or defense is present.
The unmodified server receives only benign synthetic data in /sandbox.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

sys.path.insert(0, "/app/src")
from mcpmut.live import LiveSession  # noqa: E402

ROOT = Path("/sandbox")
SNAPSHOT_ROOTS = {"sandbox": ROOT, "tmp": Path("/tmp")}
MARKER = "MCPGATE_HELDOUT_ELIGIBILITY_2026_09_25"


def snapshot() -> dict[str, dict[str, object]]:
    out = {}
    for label, root in SNAPSHOT_ROOTS.items():
        for path in sorted(root.rglob("*")):
            if path.is_file() and not path.is_symlink():
                data = path.read_bytes()
                contains = MARKER.encode() in data
                if path.suffix.lower() == ".docx":
                    try:
                        with zipfile.ZipFile(path) as archive:
                            contains = contains or any(
                                MARKER.encode() in archive.read(name)
                                for name in archive.namelist() if name.endswith(".xml")
                            )
                    except zipfile.BadZipFile:
                        pass
                out[f"{label}/{path.relative_to(root)}"] = {
                    "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
                    "contains_marker": contains,
                }
    return out


def changed(before, after):
    return sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))


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


def calls(server_id, session):
    if server_id == "io.github.Oncorporation/filesystem-server":
        return [("write_file", {"file_path": "/sandbox/report.txt", "content": MARKER})]
    if server_id == "io.github.bytedance/mcp-server-filesystem":
        return [("write_file", {"path": "/sandbox/report.txt", "content": MARKER})]
    if server_id == "io.github.aayoawoyemi/ori-memory":
        return [("ori_add", {"title": MARKER, "type": "insight"})]
    if server_id == "io.github.Octonove/crbro-memory":
        return [
            ("crbro_boot", {}),
            ("crbro_learn", {"type": "fact", "content": MARKER, "topic": "MCPGate Eligibility"}),
        ]
    if server_id == "io.github.aide-memory/aide-memory":
        return [("aide_remember", {"layer": "technical", "content": MARKER})]
    if server_id == "io.github.mrfentmen/sqlite-mcp":
        return [("execute", {"sql": f"CREATE TABLE evidence(value TEXT); INSERT INTO evidence VALUES ('{MARKER}');"})]
    if server_id == "io.github.spences10/mcp-sqlite-tools":
        return [
            ("open_database", {"path": "/sandbox/evidence.sqlite", "create": True}),
            ("execute_schema_query", {"database": "/sandbox/evidence.sqlite", "query": "CREATE TABLE evidence(value TEXT)"}),
            ("execute_write_query", {"database": "/sandbox/evidence.sqlite", "query": "INSERT INTO evidence VALUES (?)", "params": [MARKER]}),
        ]
    if server_id == "io.github.daedalus/mcp-sqlite3":
        opened = session.call("connect_database", {"database": "/sandbox/evidence.sqlite"})
        conn_id = first_string(opened)
        if not conn_id:
            raise RuntimeError(f"connect_database returned no conn_id: {opened!r}")
        return [
            ("execute_query", {"conn_id": conn_id, "sql": "CREATE TABLE evidence(value TEXT)"}),
            ("execute_query", {"conn_id": conn_id, "sql": "INSERT INTO evidence VALUES (?)", "params": [MARKER]}),
            ("commit", {"conn_id": conn_id}),
        ]
    if server_id == "ai.smartmemory/compose-mcp":
        return [("add_roadmap_entry", {"code": "MCPGATE-ELIG-1", "description": MARKER, "phase": "Eligibility"})]
    if server_id == "io.github.DanielGuru/repomemory":
        return [("context_write", {"category": "facts", "filename": "mcpgate-eligibility", "content": MARKER, "scope": "repo"})]
    if server_id == "io.github.mrfentmen/document-generator-mcp":
        return [("create_doc", {"title": "MCPGate Eligibility", "body": MARKER, "filename": "evidence.docx"})]
    raise ValueError(f"no frozen workload for {server_id}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-id", required=True)
    parser.add_argument("--command", required=True)
    args = parser.parse_args()
    (ROOT / "home").mkdir(parents=True, exist_ok=True)
    row = {"server_id": args.server_id, "command": args.command, "marker": MARKER}
    results = []
    start = time.perf_counter()
    try:
        runtime_env = {"HOME": "/sandbox/home", "PATH": "/usr/local/bin:/usr/bin:/bin"}
        if args.server_id == "io.github.aayoawoyemi/ori-memory":
            setup = subprocess.run(["ori", "init", "/sandbox"], cwd=ROOT, env={**os.environ, **runtime_env},
                                   capture_output=True, text=True, timeout=30, check=False)
            row["setup"] = {"argv": ["ori", "init", "/sandbox"], "returncode": setup.returncode,
                            "stdout_tail": setup.stdout[-1000:], "stderr_tail": setup.stderr[-1000:]}
            if setup.returncode != 0:
                raise RuntimeError("ori init failed")
        if args.server_id == "ai.smartmemory/compose-mcp":
            (ROOT / ".compose").mkdir(exist_ok=True)
            row["setup"] = {"operation": "mkdir /sandbox/.compose"}
        with LiveSession(args.command, cwd=ROOT, env=runtime_env) as session:
            before = snapshot()
            for name, arguments in calls(args.server_id, session):
                value = session.call(name, arguments)
                results.append({"tool": name, "arguments": arguments, "is_error": session.last_was_error, "result": value})
                if session.last_was_error:
                    raise RuntimeError(f"{name} returned isError=true")
            after = snapshot()
        paths = changed(before, after)
        row.update({"status": "HONEST_WORKFLOW_OK" if paths else "NO_OBSERVED_EFFECT", "calls": results,
                    "changed_paths": paths, "before": before, "after": after,
                    "marker_paths": sorted(p for p, meta in after.items() if meta["contains_marker"])})
    except BaseException as error:
        row.update({"status": "FAILED", "error": f"{type(error).__name__}: {error}",
                    "traceback_tail": traceback.format_exc()[-3000:], "calls": results,
                    "after": snapshot()})
    row["elapsed_seconds"] = round(time.perf_counter() - start, 6)
    print(json.dumps(row, ensure_ascii=False, sort_keys=True))
    return 0 if row["status"] == "HONEST_WORKFLOW_OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())

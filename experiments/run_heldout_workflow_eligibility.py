"""Run honest effect/oracle eligibility for the ten schema-selected servers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import run_heldout_eligibility as base

ROOT = Path(__file__).resolve().parents[1]
ELIGIBILITY = ROOT / "artifact" / "results" / "heldout_eligibility.json"
OUT = ROOT / "artifact" / "results" / "heldout_workflow_eligibility.json"
SELECTED = {
    "io.github.Oncorporation/filesystem-server", "io.github.bytedance/mcp-server-filesystem", "io.github.aayoawoyemi/ori-memory",
    "io.github.Octonove/crbro-memory", "io.github.aide-memory/aide-memory",
    "io.github.mrfentmen/sqlite-mcp",
    "io.github.daedalus/mcp-sqlite3", "ai.smartmemory/compose-mcp",
    "io.github.DanielGuru/repomemory", "io.github.mrfentmen/document-generator-mcp",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-id", choices=sorted(SELECTED))
    args = parser.parse_args()
    docker = base._docker_executable()
    if docker is None:
        raise RuntimeError("Docker unavailable")
    source = json.loads(ELIGIBILITY.read_text(encoding="utf-8"))
    requested = {args.server_id} if args.server_id else SELECTED
    rows = [row for row in source["rows"] if row["candidate"]["id"] in requested]
    expected = len(requested)
    if len(rows) != expected or any(row.get("probe", {}).get("status") != "TOOLS_LIST_OK" for row in rows):
        raise RuntimeError("selected set is not schema-eligible")
    result = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
              "phase": "PRE_OUTCOME_HONEST_WORKFLOW_ELIGIBILITY", "attack_calls": 0,
              "defense_conditions": 0, "source_sha256": hashlib.sha256(ELIGIBILITY.read_bytes()).hexdigest(), "rows": []}
    for index, row in enumerate(rows, 1):
        candidate = row["candidate"]
        image = row["image_tag"]
        built, build = base._build(docker, candidate, image, timeout=120)
        current = {"candidate": candidate, "image_tag": image, "build": build}
        print(f"[{index}/{expected}] {candidate['id']}", flush=True)
        if built:
            command = " ".join([candidate["binary"], *candidate.get("eligibility_args", [])])
            with tempfile.TemporaryDirectory(prefix="mcpgate-heldout-") as workspace:
                Path(workspace, "home").mkdir()
                Path(workspace, "tmp").mkdir()
                run = [docker, "run", "--rm", "--network=none", "--read-only", "--memory=512m", "--cpus=1",
                       "--pids-limit=256", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                       "--mount", f"type=bind,src={workspace},dst=/sandbox",
                       "--mount", f"type=bind,src={Path(workspace, 'tmp')},dst=/tmp",
                       "--entrypoint", "python3", image, "/app/heldout_workload_probe.py",
                       "--server-id", candidate["id"], "--command", command]
                proc = base._run(run, timeout=90)
                try:
                    current["probe"] = json.loads(proc.stdout.strip())
                except json.JSONDecodeError:
                    current["probe"] = {"status": "INVALID_OUTPUT", "stdout_tail": proc.stdout[-2000:]}
                current["container_exit_code"] = proc.returncode
                current["container_stderr_tail"] = proc.stderr[-3000:]
        result["rows"].append(current)
        output = OUT if args.server_id is None else (
            OUT.parent / "heldout_workflow" / f"{candidate['id'].replace('/', '__')}.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("  " + current.get("probe", {}).get("status", "NOT_RUN"), flush=True)
    ok = sum(row.get("probe", {}).get("status") == "HONEST_WORKFLOW_OK" for row in result["rows"])
    print(f"honest workflow eligibility: {ok}/{expected}")
    return 0 if ok == expected else 1


if __name__ == "__main__":
    raise SystemExit(main())

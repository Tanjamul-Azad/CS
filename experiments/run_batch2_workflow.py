"""Honest-workflow eligibility for the second held-out batch (workstream G).

Runs each schema-eligible server's honest workload once (no tamper, no
defense) and records where its effect lands in the trusted snapshot of
/sandbox, home included. Pre-outcome: no attack or admission decision is
made here. Servers whose honest workflow cannot complete, or whose effect
does not land in the client-selected area, are recorded with the reason.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

import run_matched_filesystem as mf  # noqa: E402

ELIG = ROOT / "artifact" / "results" / "batch2_eligibility.json"
OUT = ROOT / "artifact" / "results" / "batch2_workflow.json"
DEFERRED = {"io.github.JoyTruepath/truepath-pdf-mcp":
            "every write tool transforms an input PDF (merge, split, pages); needs a PDF fixture"}


def batch2_servers() -> list[dict]:
    rows = json.loads(ELIG.read_text(encoding="utf-8"))["rows"]
    out = []
    for r in rows:
        if not r.get("eligible"):
            continue
        c = r["candidate"]
        out.append({"id": c["id"], "ecosystem": c["ecosystem"], "package": c["package"],
                    "version": c["version"], "integrity": c["integrity"],
                    "image_tag": r["image_tag"], "evaluation_image_id": r["image_id"],
                    "launch_command": c["binary"]})
    return out


def main() -> int:
    docker = mf._docker()
    scratch = Path(os.environ["MCPGATE_SCRATCH"]).parent / "batch2_workflow"
    result = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
              "phase": "PRE_OUTCOME_HONEST_WORKFLOW_ELIGIBILITY", "attack_calls": 0,
              "defense_conditions": 0,
              "eligibility_sha256": hashlib.sha256(ELIG.read_bytes()).hexdigest(),
              "deferred": DEFERRED, "rows": []}
    for server in batch2_servers():
        if server["id"] in DEFERRED:
            continue
        sandbox = mf._fresh(scratch / server["id"].replace("/", "__"))
        record = mf._run_container(docker, server, sandbox, mode="none")
        driver = record["driver"]
        walk = mf._walk(sandbox)
        changed = sorted(p for p, e in walk.items() if e["kind"] != "directory")
        calls = [{"tool": c["tool"], "is_error": c["is_error"],
                  "result": str(c["result"])[:300]} for c in driver.get("calls", [])]
        row = {"server": server, "driver_status": driver.get("status"),
               "error": driver.get("error"), "calls": calls,
               "changed_files": changed[:60],
               "changed_outside_home": [p for p in changed
                                        if not (p == "home" or p.startswith("home/"))][:60],
               "marker_files": [p for p, e in walk.items() if e.get("contains_marker")],
               "stderr_tail": record["stderr_tail"][-600:]}
        row["honest_effect_in_client_area"] = bool(row["marker_files"]) and all(
            not p.startswith("home/") for p in row["marker_files"])
        result["rows"].append(row)
        print(f"{server['id']}: {row['driver_status']} errors="
              f"{[c['tool'] for c in calls if c['is_error']]} marker_files={row['marker_files'][:4]}",
              flush=True)
        OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

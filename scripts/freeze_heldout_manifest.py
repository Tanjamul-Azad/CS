"""Freeze the held-out manifest after schema and honest-oracle eligibility."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "artifact" / "held-out-candidates.json"
SCHEMA = ROOT / "artifact" / "results" / "heldout_eligibility.json"
WORKFLOWS = ROOT / "artifact" / "results" / "heldout_workflow_eligibility.json"
OUT = ROOT / "artifact" / "held-out-manifest.json"

CLASS = {
    "io.github.Oncorporation/filesystem-server": "EXACT",
    "io.github.bytedance/mcp-server-filesystem": "EXACT",
    "io.github.aayoawoyemi/ori-memory": "CONSTRAINED",
    "io.github.Octonove/crbro-memory": "CONSTRAINED",
    "io.github.aide-memory/aide-memory": "CONSTRAINED",
    "io.github.mrfentmen/sqlite-mcp": "UNDERSPECIFIED",
    "io.github.daedalus/mcp-sqlite3": "UNDERSPECIFIED",
    "ai.smartmemory/compose-mcp": "CONSTRAINED",
    "io.github.DanielGuru/repomemory": "EXACT",
    "io.github.mrfentmen/document-generator-mcp": "EXACT",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    workflows = json.loads(WORKFLOWS.read_text(encoding="utf-8"))
    if workflows.get("phase") != "PRE_OUTCOME_HONEST_WORKFLOW_ELIGIBILITY":
        raise RuntimeError("workflow log is not pre-outcome eligibility")
    if workflows.get("attack_calls") != 0 or workflows.get("defense_conditions") != 0:
        raise RuntimeError("security outcomes were already exercised")
    schema_by_id = {row["candidate"]["id"]: row for row in schema["rows"]}
    workflow_by_id = {row["candidate"]["id"]: row for row in workflows["rows"]}
    if set(CLASS) != set(workflow_by_id):
        raise RuntimeError("curated set and workflow log differ")
    servers = []
    for server_id, workflow_class in CLASS.items():
        srow = schema_by_id[server_id]
        wrow = workflow_by_id[server_id]
        if srow.get("probe", {}).get("status") != "TOOLS_LIST_OK":
            raise RuntimeError(f"schema eligibility failed: {server_id}")
        if wrow.get("probe", {}).get("status") != "HONEST_WORKFLOW_OK":
            raise RuntimeError(f"honest workflow eligibility failed: {server_id}")
        calls = wrow["probe"]["calls"]
        declared = {tool["name"] for tool in srow["probe"]["tools"]}
        if any(call["tool"] not in declared for call in calls):
            raise RuntimeError(f"workload uses undeclared tool: {server_id}")
        servers.append({
            "id": server_id,
            "workflow_class": workflow_class,
            "package": srow["candidate"]["package"],
            "ecosystem": srow["candidate"]["ecosystem"],
            "version": srow["candidate"]["version"],
            "integrity": srow["candidate"]["integrity"],
            "image_tag": srow["image_tag"],
            "image_id": srow["image_id"],
            "launch_command": wrow["probe"]["command"],
            "tool": next(call["tool"] for call in calls if call["tool"] not in {
                "crbro_boot", "connect_database", "commit"
            }),
            "runner": ["python", "experiments/run_heldout_workflow_eligibility.py", "--server-id", server_id],
            "honest_tool_sequence": [call["tool"] for call in calls],
            "honest_arguments": [call["arguments"] for call in calls],
            "oracle": {
                "kind": "trusted_recursive_snapshot_with_type_decoder",
                "implementation": "docker/heldout_workload_probe.py",
                "roots": ["/sandbox", "/tmp"],
                "changed_paths": wrow["probe"]["changed_paths"],
                "marker_paths": wrow["probe"]["marker_paths"],
            },
            "workflow_validation_image_tag": wrow["image_tag"],
        })
    counts = Counter(CLASS.values())
    if len(servers) < 10 or any(counts[name] < 2 for name in ("EXACT", "CONSTRAINED", "UNDERSPECIFIED")):
        raise RuntimeError("minimum set/class coverage not met")
    manifest = {
        "schema_version": 2,
        "status": "FROZEN",
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "freeze_boundary": "before any attack, baseline, or MCPGate outcome on these workloads",
        "security_outcomes_observed_before_freeze": False,
        "minimum_independent_servers": 10,
        "minimum_per_claimed_workflow_class": 2,
        "claimed_workflow_classes": ["EXACT", "CONSTRAINED", "UNDERSPECIFIED"],
        "class_counts": dict(sorted(counts.items())),
        "source_hashes": {
            "held_out_candidates_sha256": sha(CANDIDATES),
            "schema_eligibility_sha256": sha(SCHEMA),
            "honest_workflow_eligibility_sha256": sha(WORKFLOWS),
        },
        "servers": servers,
    }
    OUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"frozen {len(servers)} servers: {dict(counts)}")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

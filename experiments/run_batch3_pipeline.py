"""Held-out batch 3 (workstream H): the batch-2 pipeline on new paths.

Steps, run in order; each is pre-outcome until `templates`:

  resolve      pin version, integrity, and binary (metadata only)
  eligibility  build each image and run tools/list with no network
  workflow     run the honest workload once; record where its effect lands
  manifest     keep servers whose honest effect lands in the client folder
  templates    the scored run, with the library frozen in the batch-3 plan

    python experiments/run_batch3_pipeline.py resolve
    python experiments/run_batch3_pipeline.py eligibility --target 14
    python experiments/run_batch3_pipeline.py workflow
    python experiments/run_batch3_pipeline.py manifest
    python experiments/run_batch3_pipeline.py templates
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "docker"))

ART = ROOT / "artifact"
RES = ART / "results"
CANDIDATES = ART / "held-out-batch3-candidates.json"
PINNED = ART / "held-out-batch3-pinned.json"
ELIG = RES / "batch3_eligibility.json"
WORKFLOW = RES / "batch3_workflow.json"
MANIFEST = ART / "held-out-batch3-manifest.json"
PLAN = ART / "batch3-evaluation-plan.json"
TEMPLATES = RES / "batch3_templates.json"


def resolve() -> int:
    import resolve_batch2_packages as m
    m.CANDIDATES, m.OUT = CANDIDATES, PINNED
    return m.main()


def eligibility(argv: list[str]) -> int:
    import run_batch2_eligibility as m
    m.PINNED, m.OUT = PINNED, ELIG
    sys.argv = [sys.argv[0], *argv]
    return m.main()


def workflow() -> int:
    import run_batch2_workflow as m
    m.ELIG, m.OUT, m.DEFERRED = ELIG, WORKFLOW, {}
    return m.main()


def manifest() -> int:
    rows = json.loads(WORKFLOW.read_text(encoding="utf-8"))["rows"]
    servers, excluded = [], []
    for row in rows:
        server = dict(row["server"])
        if row.get("driver_status") != "DRIVER_OK" or any(c["is_error"] for c in row["calls"]):
            excluded.append({"id": server["id"], "reason": "honest workflow did not complete",
                             "error": row.get("error")})
            continue
        if not row.get("honest_effect_in_client_area"):
            excluded.append({"id": server["id"],
                             "reason": "honest effect not in the client-selected folder",
                             "changed": row.get("changed_files", [])[:6]})
            continue
        sql = any(p.endswith((".db", ".sqlite", ".sqlite3")) for p in row["marker_files"] +
                  row.get("changed_files", []))
        server["effect_domain"] = "sql" if sql else "fs"
        servers.append(server)
    out = {"schema_version": 1, "status": "FROZEN_BEFORE_SCORED_RUN",
           "frozen_utc": datetime.now(timezone.utc).isoformat(),
           "source": WORKFLOW.name,
           "workflow_sha256": hashlib.sha256(WORKFLOW.read_bytes()).hexdigest(),
           "servers": servers, "excluded": excluded,
           "note": "servers never used in development, the first held-out set, or batch 2"}
    MANIFEST.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"{len(servers)} servers, {len(excluded)} excluded")
    for s in servers:
        print(f"  {s['id']} ({s['effect_domain']})")
    return 0


def staged_folded(sandbox: Path) -> dict:
    """Staged tree with SQLite sidecars folded (change 6), then per-file views."""
    import run_matched_filesystem as mf
    from mcpgate.canonical import canonical_view, fold_sqlite_sidecars
    raw = mf._tree_snapshot_from_walk(sandbox)
    entries = {p: (e.kind, e.content) for p, e in raw.entries.items()}
    folded = fold_sqlite_sidecars(entries)
    out = {}
    for p, (kind, content) in folded.items():
        if kind == "file" and content is not None and folded[p] is entries.get(p):
            content = canonical_view(p, content)
        out[p] = (kind, content)
    return out


def templates() -> int:
    import run_batch2_templates as m
    m.PLAN, m.MANIFEST, m.OUT = PLAN, MANIFEST, TEMPLATES
    m.staged_canonical = staged_folded
    return m.main()


if __name__ == "__main__":
    step = sys.argv[1]
    rest = sys.argv[2:]
    raise SystemExit({"resolve": resolve, "workflow": workflow, "manifest": manifest,
                      "templates": templates}.get(step, lambda: eligibility(rest))()
                     if step != "eligibility" else eligibility(rest))

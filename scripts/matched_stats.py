"""Overhead and clustered-interval statistics for the matched evaluation.

Reads the filesystem and SQL matched results and reports, per condition:
per-call latency, server CPU, and peak RSS at p50/p95/p99, and the attack
prevention rate with a server-clustered bootstrap 95 percent interval. Clustering
by server implementation is the correct unit here because tools nested in one
server are not independent samples. Pure reader.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [ROOT / "artifact" / "results" / "matched_filesystem.json",
           ROOT / "artifact" / "results" / "matched_sql.json"]
OUT_MD = ROOT / "results" / "tables" / "matched_stats.md"
OUT_JSON = ROOT / "artifact" / "results" / "matched_stats.json"
CONDITIONS = ["NONE", "PLAIN_SANDBOX", "MBA", "STATIC_LP", "MCPGATE"]
B = 10000


def _cells():
    cells = []
    for source in SOURCES:
        if not source.is_file():
            continue
        data = json.loads(source.read_text(encoding="utf-8"))
        for server in data["servers"]:
            for cell in server.get("cells", []):
                cell = dict(cell)
                cell["_domain"] = "sql" if "sql" in source.name else "fs"
                cells.append(cell)
    return cells


def _pct(values, q):
    clean = [v for v in values if isinstance(v, (int, float))]
    return round(float(np.percentile(clean, q)), 3) if clean else None


def _clustered_ci(per_server):
    """Server-clustered bootstrap CI for a pooled proportion.

    per_server maps server id to (prevented, total). Resamples whole servers.
    """
    servers = [s for s, (k, n) in per_server.items() if n > 0]
    if not servers:
        return (None, None, None)
    point_k = sum(per_server[s][0] for s in servers)
    point_n = sum(per_server[s][1] for s in servers)
    point = point_k / point_n
    rng = random.Random(20260926)
    estimates = []
    for _ in range(B):
        pick = [servers[rng.randrange(len(servers))] for _ in servers]
        k = sum(per_server[s][0] for s in pick)
        n = sum(per_server[s][1] for s in pick)
        estimates.append(k / n if n else 0.0)
    estimates.sort()
    lo = estimates[int(0.025 * B)]
    hi = estimates[int(0.975 * B)]
    return (round(point, 4), round(lo, 4), round(hi, 4))


def main() -> int:
    cells = _cells()
    servers = sorted({c["server_id"] for c in cells})
    result = {"servers": len(servers), "attack_cells": sum(
        1 for c in cells if c["mutation_attempted"]), "by_condition": {}}
    lines = ["# Matched evaluation: overhead and clustered intervals", "",
             f"Servers: {len(servers)} (filesystem + SQL). "
             f"Bootstrap resamples: {B}, clustered by server.", "",
             "## Per-call overhead (all cells for the condition)", "",
             "| Condition | Latency p50/p95/p99 ms | CPU p50/p95/p99 s | "
             "Peak RSS p50/p95/p99 MB |", "|---|---|---|---|"]
    for cond in CONDITIONS:
        subset = [c for c in cells if c["condition"] == cond]
        lat = [c.get("latency_ms") for c in subset]
        cpu = [c.get("container_cpu_seconds") for c in subset]
        rss = [(c.get("container_peak_mem_bytes") or 0) / 1048576 for c in subset
               if c.get("container_peak_mem_bytes")]
        row = {
            "latency_ms": [_pct(lat, 50), _pct(lat, 95), _pct(lat, 99)],
            "cpu_seconds": [_pct(cpu, 50), _pct(cpu, 95), _pct(cpu, 99)],
            "peak_rss_mb": [_pct(rss, 50), _pct(rss, 95), _pct(rss, 99)],
        }
        result["by_condition"].setdefault(cond, {}).update(row)
        lines.append(
            f"| {cond} | {row['latency_ms']} | {row['cpu_seconds']} | "
            f"{row['peak_rss_mb']} |")

    lines += ["", "## Attack prevention with server-clustered 95% interval", "",
              "| Condition | Prevented | Rate | Clustered 95% CI |",
              "|---|---:|---:|---|"]
    for cond in CONDITIONS:
        per_server: dict[str, list[int]] = {}
        for c in cells:
            if c["condition"] != cond or not c["mutation_attempted"]:
                continue
            entry = per_server.setdefault(c["server_id"], [0, 0])
            entry[1] += 1
            if c["prevented"]:
                entry[0] += 1
        point, lo, hi = _clustered_ci(per_server)
        k = sum(v[0] for v in per_server.values())
        n = sum(v[1] for v in per_server.values())
        result["by_condition"][cond]["prevention"] = {
            "prevented": k, "total": n, "rate": point,
            "clustered_ci": [lo, hi]}
        ci = f"[{lo:.1%}, {hi:.1%}]" if lo is not None else "-"
        lines.append(f"| {cond} | {k}/{n} | "
                     f"{(point or 0):.1%} | {ci} |")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {OUT_MD.relative_to(ROOT)} and {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

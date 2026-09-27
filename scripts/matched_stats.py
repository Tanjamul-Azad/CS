"""Overhead and clustered-interval statistics for the matched evaluation.

Reads the filesystem and SQL matched results and reports, per condition:
per-call latency, server CPU, and peak RSS at p50/p95/p99, and the attack
prevention rate with a server-clustered bootstrap 95 percent interval. Clustering
by server implementation is the correct unit here because tools nested in one
server are not independent samples. Pure reader.

The primary prevention denominator is the set of attacks that LAND: an attack
cell counts only when the paired no-defense run for the same server and
scenario shows an unauthorized effect. Attacks that are inert on a server are
excluded, since no condition can be credited with preventing them. The
all-attempted rate is kept alongside for transparency.
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


def _wilson(k, n, z=1.959964):
    """Wilson score interval; used at the server level when every cluster is
    fully prevented and the bootstrap degenerates to a single point."""
    if n == 0:
        return (None, None)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return (round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4))


def _landed_keys(cells):
    """(domain, server, scenario) triples whose no-defense attack landed."""
    return {(c["_domain"], c["server_id"], c["scenario"]) for c in cells
            if c["condition"] == "NONE" and c["mutation_attempted"]
            and c["attack_succeeded"]}


def _prevention(cells, cond, keep):
    per_server: dict[str, list[int]] = {}
    for c in cells:
        if c["condition"] != cond or not c["mutation_attempted"] or not keep(c):
            continue
        entry = per_server.setdefault(c["server_id"], [0, 0])
        entry[1] += 1
        if c["prevented"]:
            entry[0] += 1
    point, lo, hi = _clustered_ci(per_server)
    k = sum(v[0] for v in per_server.values())
    n = sum(v[1] for v in per_server.values())
    full = sum(1 for v in per_server.values() if v[1] and v[0] == v[1])
    return {"prevented": k, "total": n, "rate": point, "clustered_ci": [lo, hi],
            "servers": len(per_server), "servers_fully_prevented": full,
            "server_wilson_ci": list(_wilson(full, len(per_server)))}


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

    landed = _landed_keys(cells)
    result["landed_attacks"] = len(landed)
    result["inert_attacks"] = sum(
        1 for c in cells if c["condition"] == "NONE" and c["mutation_attempted"]
        and not c["attack_succeeded"])
    for title, key, keep in (
            ("landed attacks only (primary)", "prevention_landed",
             lambda c: (c["_domain"], c["server_id"], c["scenario"]) in landed),
            ("all attempted attacks, including inert ones", "prevention",
             lambda c: True)):
        lines += ["", f"## Attack prevention, {title}", "",
                  "| Condition | Prevented | Rate | Clustered 95% CI | "
                  "Servers fully prevented (Wilson 95%) |",
                  "|---|---:|---:|---|---|"]
        for cond in CONDITIONS:
            row = _prevention(cells, cond, keep)
            result["by_condition"][cond][key] = row
            lo, hi = row["clustered_ci"]
            ci = f"[{lo:.1%}, {hi:.1%}]" if lo is not None else "-"
            wl, wh = row["server_wilson_ci"]
            lines.append(
                f"| {cond} | {row['prevented']}/{row['total']} | "
                f"{(row['rate'] or 0):.1%} | {ci} | "
                f"{row['servers_fully_prevented']}/{row['servers']} "
                f"[{wl:.1%}, {wh:.1%}] |")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {OUT_MD.relative_to(ROOT)} and {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

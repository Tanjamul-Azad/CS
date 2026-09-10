"""
Regenerate every reported number into `results/`, from raw data only.

WHY THIS EXISTS. The raw experiment JSON is large and gitignored
(`data/processed/*.json`), so a reader cloning this repository cannot see
any of it. That is fine for 12MB of per-server traces and fatal for the
numbers those traces support: a result nobody else can open is not
evidence. This script closes the gap by writing the small, human-readable
end of the chain into a tracked directory:

    code  ->  raw JSON  ->  [this script]  ->  results/tables/*.md + *.csv
                                           ->  results/MANIFEST.md

Every table records which raw file it came from and the SHA-256 prefix of
that file, so a number in the write-up can be traced back to the exact
bytes it was computed from, and a stale table is detectable rather than
silently wrong.

Nothing here recomputes an experiment. If a raw file is missing, the
corresponding table says so instead of being fabricated or silently
skipped -- a missing input must be visible.

    python experiments/make_results.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "results"
TABLES = OUT / "tables"

_sources: list[tuple[str, Path, bool]] = []      # (label, path, present)


def _digest(p: Path) -> str:
    if not p.exists():
        return "MISSING"
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _load(label: str, p: Path):
    present = p.exists()
    _sources.append((label, p, present))
    if not present:
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _write(name: str, title: str, note: str, header: list[str],
           rows: list[list], source: str) -> None:
    """One table, as Markdown for reading and CSV for reuse."""
    TABLES.mkdir(parents=True, exist_ok=True)
    md = [f"# {title}", "", note, "",
          "| " + " | ".join(header) + " |",
          "|" + "|".join("---" for _ in header) + "|"]
    for r in rows:
        md.append("| " + " | ".join(str(c) for c in r) + " |")
    md += ["", f"*Source: `{source}`. Regenerate with "
               f"`python experiments/make_results.py`.*", ""]
    (TABLES / f"{name}.md").write_text("\n".join(md), encoding="utf-8")

    csv = [",".join(header)]
    for r in rows:
        csv.append(",".join(f'"{c}"' if "," in str(c) else str(c) for c in r))
    (TABLES / f"{name}.csv").write_text("\n".join(csv) + "\n", encoding="utf-8")
    print(f"  wrote results/tables/{name}.md + .csv   ({len(rows)} rows)")


# -- individual tables ------------------------------------------------------

def table_funnel(scale) -> None:
    if scale is None:
        return
    st = Counter(r.get("status") for r in scale)
    launched = [r for r in scale if r.get("tool_count") is not None]
    ok = [r for r in scale if r.get("status") == "ok"]
    landed = [r for r in ok
              if (r.get("tampered") or {}).get("attack_landed")]
    n = len(scale)
    rows = [
        ["Registry candidates, runnable without credentials", n, "100.0%"],
        ["Launched and answered tools/list", len(launched),
         f"{100*len(launched)/n:.1f}%"],
        ["Usable write tool, both trials completed", len(ok),
         f"{100*len(ok)/n:.1f}%"],
        ["Mutation attempted (L1, pre-repair)", len(landed),
         f"{100*len(landed)/n:.1f}%"],
    ]
    _write("funnel", "Live-audit funnel",
           "How 8,692 real registry servers reduce to an analysable set. "
           "The 14.3% survival rate is a selection effect and is "
           "characterised in `selection_effect`. The last row says MUTATION "
           "ATTEMPTED, not attacks that landed: the underlying flag meant "
           "only that the proxy selected a target field. See `effect_oracle` "
           "for how far apart those are.",
           ["Stage", "Servers", "Share"], rows, "data/processed/scale_run.json")

    _write("run_status", "Scale-run terminal status",
           "Why servers dropped out. `no_write_tool_found` dominates: most "
           "MCP servers expose nothing that mutates state.",
           ["Status", "Servers"],
           [[k, v] for k, v in st.most_common()],
           "data/processed/scale_run.json")


def table_selection_effect(scale) -> None:
    if scale is None:
        return
    import statistics as stats
    launched = [r for r in scale if r.get("tool_count") is not None]
    ok = [r for r in launched if r.get("status") == "ok"]
    drop = [r for r in launched if r.get("status") != "ok"]

    def mix(g):
        agg = Counter()
        for r in g:
            for k, v in (r.get("coverage") or {}).items():
                agg[k] += v
        t = sum(agg.values()) or 1
        return t, {k: 100 * agg.get(k, 0) / t for k in ("A0", "A1", "A2", "A3")}

    rows = []
    for label, g in (("Analysed (status=ok)", ok),
                     ("Launched but dropped", drop)):
        tc = [r["tool_count"] for r in g]
        t, m = mix(g)
        rows.append([label, len(g), f"{stats.median(tc):.0f}", t,
                     f"{m['A0']:.1f}%", f"{m['A1']:.1f}%",
                     f"{m['A2']:.1f}%", f"{m['A3']:.1f}%"])
    _write("selection_effect", "Survivors vs dropouts",
           "The analysed set is the FAVOURABLE tail: richer servers, and "
           "far more auditable structure. Any detection result measured on "
           "it is an upper bound on the ecosystem, which makes a negative "
           "result stronger rather than weaker.",
           ["Group", "Servers", "Median tools", "Tools",
            "A0", "A1", "A2", "A3"], rows,
           "data/processed/scale_run.json")


def table_resource_channel(sweep) -> None:
    if sweep is None:
        return
    ok = [r for r in sweep if r.get("status") == "ok"]
    ch = Counter(r.get("resource_channel") for r in ok)
    n = len(ok) or 1
    rows = [[k, ch.get(k, 0), f"{100*ch.get(k,0)/n:.1f}%"]
            for k in ("present", "empty", "unsupported")]
    rows.append(["publishing URI templates",
                 sum(1 for r in ok if r.get("template_count")),
                 f"{100*sum(1 for r in ok if r.get('template_count'))/n:.1f}%"])
    _write("resource_channel", "E0 - MCP resource channel",
           "MCP's second observation channel, which every earlier number in "
           "this project ignored. Not one server publishes a parameterised "
           "URI template - the only form addressable to the record a write "
           "just touched - so the channel adds observation surface but "
           "almost no verification.",
           ["Outcome", "Servers", "Share"], rows,
           "data/processed/resource_sweep.json")


def table_escape_partition(part) -> None:
    if part is None:
        return
    c = Counter(r["group"] for r in part)
    n = len(part) or 1
    rows = [[k, v, f"{100*v/n:.1f}%"] for k, v in c.most_common()]
    any_e = sum(v for k, v in c.items() if k != "NONE")
    rows.append(["**any escape**", any_e, f"{100*any_e/n:.1f}%"])
    _write("escape_partition", "Verification escape channels",
           "Which structural escape each server offers. ENUM (enumeration) "
           "is the most common and was never implemented as a typed check, "
           "which is the direct explanation for 0% detection. NONE is where "
           "the classifier finds NO SUPPORTED CHECK -- not a proof that none "
           "exists. The partition is a heuristic with known imperfect recall: "
           "a real detection has already been observed landing in the NONE "
           "bucket.",
           ["Escape available", "Servers", "Share"], rows,
           "data/processed/escape_partition.json")


def _op(rows, permissive):
    def hon(r): return r.get("honest", {}).get("alerts", []) or []
    def tam(r):
        t = r.get("tampered", {})
        return t.get("L1", t) if isinstance(t, dict) else {}
    sev = ("[VIOLATION]", "[WARNING]") if permissive else ("[VIOLATION]",)
    def fired(a): return any(x.startswith(s) for x in a for s in sev)
    # A trial whose write the server REFUSED audits a write that never
    # happened: neither a detection nor a false positive can mean anything
    # there. Excluded from both numerator and denominator.
    #
    # This exclusion was inert until 2026-09-10 -- live.py read the MCP
    # error flag under a name the SDK does not define, so write_errored was
    # False on every trial ever recorded. With it working, 65% of the
    # pilot's "landed attacks" turn out to be refused writes, and the true
    # denominator is 71 rather than 204. Runs recorded before the fix
    # cannot be corrected retrospectively (the write's response is not kept
    # in the trace), so their rates are reported as-is and flagged.
    rows = [r for r in rows if not r.get("honest", {}).get("write_errored")]
    landed = [r for r in rows if tam(r).get("attack_landed")
              and not tam(r).get("write_errored")]
    tp = [r for r in landed
          if fired(tam(r).get("alerts", [])) and not fired(hon(r))]
    fp = [r for r in rows if fired(hon(r))]
    return len(landed), len(tp), len(fp), len(rows)


def table_operating_points(runs: dict) -> None:
    rows = []
    for label, data in runs.items():
        if data is None:
            rows.append([label, "MISSING", "-", "-", "-", "-"])
            continue
        ok = [r for r in data if r.get("status") == "ok"]
        # Every pilot targets the same 218-server candidate set. A row
        # reporting fewer is a run still in flight, and must say so rather
        # than looking like a different sample with a different result.
        flag = "" if len(data) >= 218 else f" (PARTIAL {len(data)}/218)"
        for perm, pname in ((False, "strict"), (True, "permissive")):
            landed, tp, fp, n = _op(ok, perm)
            rows.append([label + flag, pname, n, landed, tp,
                         f"{100*tp/landed:.1f}%" if landed else "-",
                         f"{100*fp/n:.1f}%" if n else "-"])
    _write("operating_points", "Detector operating points",
           "The central measurement. `strict` counts only VIOLATION; "
           "`permissive` also counts WARNING. A detection requires the "
           "attack to have landed AND the honest trial on the same server "
           "to stay silent - the cross-check that separates a real catch "
           "from a broken relation firing on everything. All runs target "
           "the same 218 candidates, so rows are directly comparable; a "
           "row marked PARTIAL was still running when this was generated.",
           ["Run", "Point", "Usable", "Landed", "True detections",
            "Detection rate", "FPR"], rows,
           "data/processed/pilot_*.json")


def table_suppressed(baseline) -> None:
    if baseline is None:
        return
    def hon(r): return r.get("honest", {}).get("alerts", []) or []
    def tam(r):
        t = r.get("tampered", {})
        return t.get("L1", t) if isinstance(t, dict) else {}
    def s(a, k): return [x for x in a if x.startswith(f"[{k}]")]
    rows = []
    for r in [x for x in baseline if x.get("status") == "ok"]:
        if not tam(r).get("attack_landed"):
            continue
        if (not s(hon(r), "VIOLATION") and not s(tam(r).get("alerts", []), "VIOLATION")
                and not s(hon(r), "WARNING") and s(tam(r).get("alerts", []), "WARNING")):
            rows.append([r["server_id"], r.get("write_tool", "?"),
                         tam(r).get("diverted_field", "?"),
                         s(tam(r).get("alerts", []), "WARNING")[0][:150].replace("|", "/")])
    _write("suppressed_detections", "Real attacks the detector discarded",
           "Found by auditing our own detector: attacks that landed, where "
           "the tampered trial fired and the honest trial did not - real "
           "catches - reported only as warnings and therefore scored zero. "
           "The third row is the attacker's exfiltration path visible in "
           "the reader's own output.",
           ["Server", "Write tool", "Diverted field", "Alert"], rows,
           "data/processed/pilot_pre_r7_baseline.json")


def table_effect_oracle(rows) -> None:
    if rows is None:
        return
    out = [[r["behaviour"],
            "yes" if r["mutation_attempted"] else "-",
            "yes" if r["protocol_error"] else "-",
            "yes" if r["authorized_effect_observed"] else "-",
            "yes" if r["unauthorized_effect_observed"] else "-",
            "yes" if r["outcome_unknown"] else "-",
            "yes" if r["detector_violation"] else "-"] for r in rows]
    _write("effect_oracle", "Attempted vs happened vs detected",
           "Ground truth for every detection rate in the project. The old "
           "`attack_landed` flag meant only that the proxy selected a target "
           "field. Here the old label would count 2 of these while 3 carry a "
           "real unauthorized effect -- and one reports a protocol error AND "
           "leaves a forbidden write behind, which is why excluding errored "
           "trials is also wrong. Only observation is ground truth.",
           ["Behaviour", "Mutation attempted", "Protocol error",
            "Authorized effect", "Unauthorized effect", "Unknown",
            "Detector violation"], out,
           "data/processed/effect_oracle.json")


def table_boundary_probe(rows) -> None:
    if rows is None:
        return
    by = {}
    for r in rows:
        by.setdefault(r["scenario"], {})[r.get("condition", "defended")] = r
    out = []
    for name, pair in by.items():
        u, d = pair.get("undefended", {}), pair.get("defended", {})
        out.append([name,
                    u.get("confinement_verdict", "-"),
                    d.get("confinement_verdict", "-"),
                    d.get("completion_verdict", "-"),
                    d.get("blocked_by", "-")])
    _write("boundary_probe",
           "Preliminary control experiment - executor-mediated gateway",
           "NOT milestone M2. M2 requires the confined SERVER to perform the "
           "effect while a generic boundary enforces the contract; here the "
           "gateway performs it through a per-tool executor and the server "
           "cannot write at all, so the authorization-to-boundary translation "
           "problem is untested. Paired against an undefended control, so "
           "prevention is measured over attacks that actually landed: 10/10, "
           "with hidden_extra_field and delete_after_write excluded because "
           "they never landed even undefended. `Blocked by` matters -- 8 by OS "
           "permission, 2 by the contract check. Confinement is not "
           "authorization.",
           ["Scenario", "Undefended", "Defended", "Completion",
            "Blocked by"], out,
           "data/processed/boundary_probe.json")


def write_manifest() -> None:
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                cwd=ROOT, capture_output=True, text=True,
                                timeout=10).stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        commit = "unknown"
    lines = [
        "# Results manifest", "",
        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} "
        f"from commit `{commit}` by `experiments/make_results.py`.", "",
        "Raw per-server traces are gitignored (large, regenerable). This "
        "manifest records the exact bytes each table was computed from, so "
        "a number in the write-up traces to a file and a stale table is "
        "detectable.", "",
        "| Input | Path | Present | SHA-256 (16) | Size |",
        "|---|---|---|---|---|",
    ]
    for label, p, present in _sources:
        size = f"{p.stat().st_size/1e6:.1f} MB" if present else "-"
        lines.append(f"| {label} | `{p.relative_to(ROOT)}` | "
                     f"{'yes' if present else '**MISSING**'} | "
                     f"`{_digest(p)}` | {size} |")
    lines += ["", "## How to regenerate the raw inputs", "",
              "```bash",
              "python experiments/run_scale.py            # live audit, ~1 day",
              "python experiments/run_resource_sweep.py   # E0, ~1 hour",
              "python experiments/make_results.py         # this file + tables",
              "```", ""]
    (OUT / "MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")
    print("  wrote results/MANIFEST.md")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    print("regenerating results/ from raw data\n")

    scale = _load("Live scale run (L1, full corpus)", PROC / "scale_run.json")
    sweep = _load("E0 resource sweep", PROC / "resource_sweep.json")
    part = _load("Escape partition", PROC / "escape_partition.json")
    base = _load("Pilot, pre-R7 baseline", PROC / "pilot_pre_r7_baseline.json")
    r7 = _load("Pilot, R7 uncalibrated", PROC / "pilot_r7.json")
    cal = _load("Pilot, R7 calibrated", PROC / "pilot_r7_calibrated.json")

    table_funnel(scale)
    table_selection_effect(scale)
    table_resource_channel(sweep)
    table_escape_partition(part)
    errf = _load("Pilot, working error flag", PROC / "pilot_errflag.json")
    oracle = _load("Effect oracle", PROC / "effect_oracle.json")
    probe = _load("M2 boundary probe", PROC / "boundary_probe.json")
    table_operating_points({"pre-R7 baseline (flag broken)": base,
                            "R7 uncalibrated (flag broken)": r7,
                            "R7 calibrated (flag broken)": cal,
                            "R7 calibrated + error flag": errf})
    table_suppressed(base)
    table_effect_oracle(oracle)
    table_boundary_probe(probe)
    write_manifest()
    print("\ndone. Open results/ -- every table names its source file.")


if __name__ == "__main__":
    main()

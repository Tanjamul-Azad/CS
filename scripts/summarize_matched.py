"""Aggregate the matched filesystem results into the paper's headline table.

Reads artifact/results/matched_filesystem.json and reports, per condition and
scenario, how many server cells the attack was prevented in, landed in, or was
detected-but-not-prevented in, with a Wilson 95% interval on the prevention
rate. Also reports honest completion and any false blocks. Pure reader; it
computes nothing that was not already decided by the trusted oracle.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "artifact" / "results" / "matched_filesystem.json"
OUT_MD = ROOT / "results" / "tables" / "matched_filesystem.md"

CONDITIONS = ["NONE", "PLAIN_SANDBOX", "MBA", "STATIC_LP", "MCPGATE"]
ATTACKS = ["A1", "A2", "A3", "A4", "A5", "A6", "A7"]


def wilson(k: int, n: int) -> tuple[float, float, float]:
    if n == 0:
        return (0.0, 0.0, 0.0)
    z = 1.959963984540054
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (p, max(0.0, center - half), min(1.0, center + half))


def main() -> int:
    data = json.loads(IN.read_text(encoding="utf-8"))
    servers = data["servers"]
    cells = [c for s in servers for c in s.get("cells", [])]

    # honest completion / false block per condition
    honest = defaultdict(lambda: [0, 0])  # condition -> [completed, total]
    false_blocks = defaultdict(int)
    # attack prevention per (condition)
    prevented = defaultdict(lambda: [0, 0])  # condition -> [prevented, applicable]
    detected = defaultdict(int)
    # per (scenario, condition)
    grid = defaultdict(lambda: [0, 0])  # (scenario, condition) -> [prevented, total]

    for cell in cells:
        cond, scen = cell["condition"], cell["scenario"]
        if scen == "H0":
            honest[cond][1] += 1
            if cell["authorized_effect"]:
                honest[cond][0] += 1
            if cell["false_block"]:
                false_blocks[cond] += 1
            continue
        prevented[cond][1] += 1
        grid[(scen, cond)][1] += 1
        if cell["prevented"]:
            prevented[cond][0] += 1
            grid[(scen, cond)][0] += 1
        elif cell["detected_only"]:
            detected[cond] += 1

    lines = ["# Matched filesystem evaluation", "",
             f"Servers: {len(servers)}  |  attack cells: {len(cells)}  |  "
             f"adversary tier: {data.get('adversary_tier')}", "",
             "## Honest workflow (H0)", "",
             "| Condition | Completed | False blocks |", "|---|---:|---:|"]
    for cond in CONDITIONS:
        done, total = honest[cond]
        lines.append(f"| {cond} | {done}/{total} | {false_blocks[cond]} |")

    lines += ["", "## Attack prevention (all applicable attack cells)", "",
              "| Condition | Prevented | Rate | 95% CI | Detected-not-prevented |",
              "|---|---:|---:|---|---:|"]
    for cond in CONDITIONS:
        k, n = prevented[cond]
        p, lo, hi = wilson(k, n)
        lines.append(f"| {cond} | {k}/{n} | {p:.1%} | "
                     f"[{lo:.1%}, {hi:.1%}] | {detected[cond]} |")

    lines += ["", "## Prevention by scenario (prevented / servers)", "",
              "| Scenario | " + " | ".join(CONDITIONS) + " |",
              "|---|" + "|".join(["---:"] * len(CONDITIONS)) + "|"]
    scen_names = {"A1": "destination", "A2": "content", "A3": "hidden field",
                  "A4": "extra effect", "A5": "replay", "A6": "false success",
                  "A7": "link alias"}
    for scen in ATTACKS:
        row = [f"A{scen[1:]} {scen_names.get(scen, '')}"]
        present = False
        for cond in CONDITIONS:
            k, n = grid[(scen, cond)]
            row.append(f"{k}/{n}" if n else "-")
            present = present or n > 0
        if present:
            lines.append("| " + " | ".join(row) + " |")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

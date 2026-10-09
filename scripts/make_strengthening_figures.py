"""Figures for the strengthening workstreams (judge, slack, agent, architecture).

Every value is read from a checked-in result JSON; nothing is typed by hand.
Style (fonts, Okabe-Ito colors, column widths) is shared with
make_submission_figures.py. The palette passed the dataviz validator for CVD
separation and normal-vision distance; orange falls below 3:1 contrast on white,
so every orange mark carries a direct label.
"""

from __future__ import annotations

import json
import math
import shutil
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_submission_figures as base  # noqa: E402

ROOT = base.ROOT
RES = ROOT / "artifact" / "results"
OUT, SUB = base.OUT, base.SUBMISSION
BLUE, TEAL, ORANGE, RED, SKY, GRAY, LIGHT = (base.BLUE, base.TEAL, base.ORANGE, base.RED,
                                            base.SKY, base.GRAY, base.LIGHT)
COLUMN, FULL = base.COLUMN, base.FULL


SHORT = {"io.github.Oncorporation/filesystem-server": "fs-server (Py)",
         "io.github.bytedance/mcp-server-filesystem": "fs-server (Node)",
         "filesystem-server": "fs-server (Py)", "mcp-server-filesystem": "fs-server (Node)"}


def short(server_id: str) -> str:
    if server_id in SHORT:
        return SHORT[server_id]
    return server_id.split("/")[-1].replace("-mcp-server", "").replace("-mcp", "")


def load(name: str) -> dict:
    return json.loads((RES / name).read_text(encoding="utf-8"))


def save(fig, name: str) -> None:
    base._save(fig, name)
    SUB.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OUT / f"{name}.pdf", SUB / f"{name}.pdf")


def judge_boundary() -> None:
    """Detection versus false positives, split by transcript distinguishability."""
    split = load("llm_judge_v2_leak_split.json")["summary"]
    # The non-OpenAI judge re-scored the same 176 transcripts locally; its
    # split uses the same judge-free leak rule (analyze_judge_leaks.py).
    split.update(load("llm_judge_ollama_v2_leak_split.json")["summary"])
    models = [("gpt-4.1-2025-04-14", "gpt-4.1"), ("gpt-5-mini-2025-08-07", "gpt-5-mini"),
              ("gpt-4.1-mini-2025-04-14", "gpt-4.1-mini"), ("llama3.1:8b", "Llama 3.1 8B")]
    series = [("honest", "Honest (false positive)", GRAY, "o"),
              ("consistent_indistinguishable", "Attack, transcript identical", TEAL, "s"),
              ("consistent_leaked", "Attack, transcript leaked", ORANGE, "D")]
    fig, ax = plt.subplots(figsize=(COLUMN, 2.45))
    offsets = [-0.22, 0.0, 0.22]
    for row, (key, label) in enumerate(models):
        entry = split[key]
        y = len(models) - 1 - row
        for (skey, slabel, color, marker), dy in zip(series, offsets):
            if skey == "honest":
                k, n, (lo, hi) = entry["honest_fpr"][0], entry["honest_fpr"][1], entry["honest_fpr"][2]
            else:
                k, n, (lo, hi) = entry[skey]["flagged"], entry[skey]["n"], entry[skey]["wilson"]
            rate = 100 * k / n
            ax.plot([100 * lo, 100 * hi], [y + dy, y + dy], color=color, linewidth=1.3,
                    solid_capstyle="round", zorder=2)
            ax.scatter([rate], [y + dy], color=color, marker=marker, s=22, zorder=3,
                       edgecolor="white", linewidth=0.6, label=slabel if row == 0 else None)
            ax.text(100 * hi + 2, y + dy, f"{k}/{n}", va="center", fontsize=6, color="black")
    ax.set_yticks(range(len(models)), [m[1] for m in reversed(models)])
    ax.set_xlim(0, 112)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("Transcripts flagged UNSAFE (%, 95% Wilson)")
    ax.grid(axis="x", color=LIGHT, linewidth=0.5, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(frameon=False, fontsize=6, loc="upper center", bbox_to_anchor=(0.45, 1.24),
              ncol=2, handletextpad=0.2, columnspacing=0.8)
    save(fig, "fig11_judge_boundary")


def slack_ladder() -> None:
    """Contract slack per server: development versus held-out."""
    dev = load("template_generalization.json")["servers"]
    sql = load("template_generalization_sql.json")["servers"]
    held = load("batch2_templates.json")["servers"]
    rows = []
    for group, servers, color in (("dev", dev + sql, BLUE), ("held-out", held, ORANGE)):
        for s in servers:
            honest = [r for r in s["honest"] if not r["call_error"] and r["slack_bits"] is not None]
            if not honest:
                continue
            bits = max(r["slack_bits"] for r in honest)
            name = short(s["server_id"])
            rows.append((group, name, bits, color))
    finite = [b for _, _, b, _ in rows if not math.isinf(b)]
    cap = max(finite) * 4 if finite else 1e4
    fig, ax = plt.subplots(figsize=(COLUMN, 2.5))
    for i, (group, name, bits, color) in enumerate(rows):
        y = len(rows) - 1 - i
        shown = cap if math.isinf(bits) else max(bits, 0.6)
        ax.barh(y, shown, color=color, height=0.62, edgecolor="none",
                hatch="////" if math.isinf(bits) else None, alpha=0.95)
        label = "unbounded" if math.isinf(bits) else ("0 (exact)" if bits == 0
                                                      else f"{bits:,.0f}")
        ax.text(shown * 1.15, y, label, va="center", fontsize=6)
    ax.set_yticks(range(len(rows)), [f"{r[1]}" for r in reversed(rows)], fontsize=6.4)
    ax.set_xscale("log")
    ax.set_xlim(0.5, cap * 60)
    ax.set_xlabel("Contract slack per honest call (bits, log)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=BLUE, label="development"),
                       Patch(color=ORANGE, label="first held-out batch")],
              frameon=False, fontsize=6, loc="upper center", ncol=2,
              bbox_to_anchor=(0.5, 1.1))
    save(fig, "fig12_slack_ladder")


def agent_harm() -> None:
    """Harm reaching trusted state, per server, without and with EffectSeal."""
    summary = load("agent_e2e_v2.json")["summary"]["by_server_model"]
    per_server: dict[str, list[int]] = {}
    for key, v in summary.items():
        server = key.split(" | ")[0]
        acc = per_server.setdefault(server, [0, 0, 0, 0])
        acc[0] += v["harm_none"][0]
        acc[1] += v["harm_none"][1]
        acc[2] += v["harm_es"][0]
        acc[3] += v["harm_es"][1]
    names = list(per_server)
    fig, ax = plt.subplots(figsize=(COLUMN, 1.9))
    width = 0.38
    for i, name in enumerate(names):
        hn, n1, he, n2 = per_server[name]
        ax.bar(i - width / 2, 100 * hn / n1, width, color=RED, edgecolor="none")
        ax.bar(i + width / 2, max(100 * he / n2, 0.8), width, color=TEAL, edgecolor="none")
        ax.text(i - width / 2, 100 * hn / n1 + 3, f"{hn}/{n1}", ha="center", fontsize=5.6)
        ax.text(i + width / 2, 6, f"{he}/{n2}", ha="center", fontsize=5.6)
    ax.set_xticks(range(len(names)), [short(n) for n in names], fontsize=6.0, rotation=15)
    ax.set_ylabel("Compromised sessions\nwith harm (%)")
    ax.set_ylim(0, 118)
    ax.set_yticks([0, 50, 100])
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=RED, label="no defense"), Patch(color=TEAL, label="EffectSeal")],
              frameon=False, fontsize=6, loc="upper right", ncol=2, bbox_to_anchor=(1.0, 1.12))
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="x", length=0)
    save(fig, "fig13_agent_harm")


def architecture() -> None:
    """Pin time (once per approved version) and call time (every call)."""
    fig, ax = plt.subplots(figsize=(FULL, 2.55))
    ax.set_xlim(0, 14.2)
    ax.set_ylim(0, 5.2)
    ax.axis("off")

    def box(x, y, w, h, text, color, tcolor="white", size=6.4):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.08",
                                    facecolor=color, edgecolor="none"))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color=tcolor,
                fontsize=size, linespacing=1.1)

    def arrow(x0, y0, x1, y1, color=GRAY):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=6,
                                     color=color, linewidth=0.8))

    # pin time
    ax.text(0.2, 4.85, "Pin time: once per approved server version", fontsize=7,
            fontweight="bold", color=GRAY)
    pin = [("Approved\nexemplar call", SKY, "black"), ("Perturbed honest\nruns (private copies)", ORANGE, "black"),
           ("Anti-unify paths\nand contents", BLUE, "white"), ("Effect template\n+ slack (bits)", BLUE, "white")]
    for i, (t, c, tc) in enumerate(pin):
        x = 0.2 + i * 2.2
        box(x, 3.75, 1.95, 0.85, t, c, tc)
        if i:
            arrow(x - 0.25, 4.17, x - 0.02, 4.17)
    # call time
    ax.text(0.2, 3.25, "Call time: every approved call", fontsize=7, fontweight="bold", color=GRAY)
    stages = [("Check request\nshape", BLUE), ("Reserve\nallowance", BLUE),
              ("Run server in\nprivate staging", ORANGE), ("Stop every\nwriter", ORANGE),
              ("Read staging\nonce", TEAL), ("Instantiate +\ndiff contract", TEAL),
              ("Promote the\nsame bytes", TEAL)]
    width, gap, start, y = 1.78, 0.22, 0.2, 1.75
    zone_x = start + 2 * (width + gap) - 0.1
    ax.add_patch(Rectangle((zone_x, y - 0.2), 2 * width + gap + 0.2, 1.3, facecolor="none",
                           edgecolor=ORANGE, linewidth=0.8, linestyle=(0, (3, 2))))
    ax.text(zone_x + (2 * width + gap + 0.2) / 2, y - 0.45,
            "untrusted server: no network, read-only root, staging is the only writable mount",
            ha="center", fontsize=5.8, color="#8A5A00", style="italic")
    for i, (t, c) in enumerate(stages):
        x = start + i * (width + gap)
        box(x, y, width, 0.9, t, c, "black" if c == ORANGE else "white")
        if i:
            arrow(x - gap + 0.01, y + 0.45, x - 0.01, y + 0.45)
    # template feeds the diff step
    tx = 0.2 + 3 * 2.2 + 0.97
    dx = start + 5 * (width + gap) + width / 2
    arrow(tx, 3.75, dx, y + 0.9, BLUE)
    ax.text(7.1, 0.35, "Any refusal discards staging and marks the allowance slot FAILED; "
            "nothing reaches the trusted store.", ha="center", fontsize=6.3, color=GRAY)
    save(fig, "fig1_effectseal_architecture")


def load_committed(name: str) -> dict:
    """A result file exactly as committed to git (HEAD), not the working copy.

    Used for the matched evaluation: the paper's numbers come from the
    committed run, and a later local overwrite must not change a figure."""
    import subprocess
    out = subprocess.run(["git", "show", f"HEAD:artifact/results/{name}"], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(out.stdout)


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def landed_table(data: dict, scenarios: list[str]) -> dict:
    """(scenario, condition) -> [prevented, landed], counting landed attacks only."""
    cells = [c for s in data["servers"] for c in s.get("cells", []) if c["mutation_attempted"]]
    landed = {(c["server_id"], c["scenario"]) for c in cells
              if c["condition"] == "NONE" and c["attack_succeeded"]}
    out: dict = {}
    for c in cells:
        if c["scenario"] in scenarios and (c["server_id"], c["scenario"]) in landed:
            cell = out.setdefault((c["scenario"], c["condition"]), [0, 0])
            cell[1] += 1
            cell[0] += bool(c["prevented"])
    return out


def matched_heatmap() -> None:
    """Landed attacks prevented, scenario by defense, files and SQL together."""
    fs = load_committed("matched_filesystem.json")
    sql = load_committed("matched_sql.json")
    assert len(fs["servers"]) == 5, "committed filesystem result must have five servers"
    fs_rows = [("A1", "File: destination"), ("A2", "File: content"),
               ("A4", "File: extra object"), ("A5", "File: replay"),
               ("A6", "File: silent no-op"), ("A7", "File: link alias")]
    sql_rows = [("A2", "SQL: value"), ("S1", "SQL: extra row"), ("S2", "SQL: extra table"),
                ("A5", "SQL: replay"), ("A6", "SQL: silent no-op")]
    conds = [("NONE", "None"), ("PLAIN_SANDBOX", "Sandbox"), ("MBA", "Auditor"),
             ("STATIC_LP", "Static least\nprivilege"), ("MCPGATE", "EffectSeal")]
    fs_t = landed_table(fs, [s for s, _ in fs_rows])
    sql_t = landed_table(sql, [s for s, _ in sql_rows])
    rows = [(lab, fs_t, s) for s, lab in fs_rows] + [(lab, sql_t, s) for s, lab in sql_rows]
    totals = {c: [0, 0] for c, _ in conds}
    grid = []
    for label, table, scen in rows:
        line = []
        for c, _ in conds:
            k, n = table.get((scen, c), [0, 0])
            totals[c][0] += k
            totals[c][1] += n
            line.append((k, n))
        grid.append(line)
    assert totals["MCPGATE"] == [32, 32] and totals["STATIC_LP"] == [11, 32], totals
    rows.append(("Total", None, None))
    grid.append([tuple(totals[c]) for c, _ in conds])
    # Darkest cell stays light enough for black labels: white text on a PDF
    # page is flagged as hidden text by similarity checkers.
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("prev", ["#FFFFFF", "#C6DBEF", "#6BAED6"])
    fig, ax = plt.subplots(figsize=(COLUMN, 3.05))
    import numpy as np
    values = np.array([[k / n if n else np.nan for k, n in line] for line in grid])
    ax.imshow(values, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i, line in enumerate(grid):
        for j, (k, n) in enumerate(line):
            bold = i == len(grid) - 1
            ax.text(j, i, f"{k}/{n}", ha="center", va="center", fontsize=6.4,
                    fontweight="bold" if bold else "normal", color="black")
    ax.set_xticks(range(len(conds)), [lab for _, lab in conds], fontsize=6.6)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=6.6)
    ax.xaxis.tick_top()
    ax.set_xticks([x - 0.5 for x in range(len(conds) + 1)], minor=True)
    ax.set_yticks([y - 0.5 for y in range(len(rows) + 1)], minor=True)
    ax.grid(which="minor", color="white", linewidth=1.4)
    ax.tick_params(which="both", length=0)
    ax.axhline(len(fs_rows) - 0.5, color=GRAY, linewidth=0.8)
    ax.axhline(len(rows) - 1.5, color=GRAY, linewidth=0.8)
    for spine in ax.spines.values():
        spine.set_visible(False)
    save(fig, "fig14_matched_heatmap")


def template_bars() -> None:
    """Honest admission and attack refusal, development versus held-out."""
    dev = load("template_generalization.json")["summary"]
    sql = load("template_generalization_sql.json")["summary"]
    held = load("batch2_templates.json")["summary"]
    groups = [
        ("Development\n(7 servers)",
         [(dev["honest_calls"] - dev["false_blocks"] + sql["honest_calls"] - sql["false_blocks"],
           dev["honest_calls"] + sql["honest_calls"]),
          (dev["prevented"]["EFFECTSEAL_TEMPLATE"] + sql["prevented_effectseal_template"],
           dev["attacks_landed"] + sql["attacks_landed"]),
          (dev["prevented"]["PATH_TEMPLATE"], dev["attacks_landed"])]),
        ("Held-out\n(4 servers)",
         [(held["honest_calls"] - held["false_blocks"], held["honest_calls"]),
          (held["prevented"]["EFFECTSEAL_TEMPLATE"], held["attacks_landed"]),
          (held["prevented"]["PATH_TEMPLATE"], held["attacks_landed"])]),
    ]
    series = [("Honest calls admitted", BLUE), ("Landed attacks refused", TEAL),
              ("Refused if content is ignored", ORANGE)]
    fig, ax = plt.subplots(figsize=(COLUMN, 1.95))
    width = 0.26
    for g, (glabel, vals) in enumerate(groups):
        for s, ((k, n), (slabel, color)) in enumerate(zip(vals, series)):
            x = g + (s - 1) * width
            lo, hi = wilson(k, n)
            ax.bar(x, 100 * k / n, width * 0.92, color=color, edgecolor="none",
                   label=slabel if g == 0 else None)
            ax.errorbar(x, 100 * k / n, yerr=[[100 * (k / n - lo)], [100 * (hi - k / n)]],
                        fmt="none", ecolor=GRAY, elinewidth=0.7, capsize=1.5)
            ax.text(x, 100 * hi + 3, f"{k}/{n}", ha="center", fontsize=5.6)
    ax.set_xticks(range(len(groups)), [g[0] for g in groups], fontsize=6.6)
    ax.set_ylabel("Percent (95% Wilson)")
    ax.set_ylim(0, 128)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.legend(frameon=False, fontsize=5.9, loc="upper center", ncol=3,
              bbox_to_anchor=(0.5, 1.17), handlelength=1.0, columnspacing=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="x", length=0)
    save(fig, "fig15_template_generalization")


def teaser() -> None:
    """Call-level authorization and effect admission check different steps."""
    fig, ax = plt.subplots(figsize=(COLUMN, 1.7))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.4)
    ax.axis("off")
    boxes = [(0.1, "Intent", "#DDDDDD", "black"), (3.55, "Approved call", BLUE, "white"),
             (7.0, "Effect on state", TEAL, "white")]
    y, h, w = 1.75, 0.85, 2.9
    for x, label, face, tcolor in boxes:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                    facecolor=face, edgecolor="none"))
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=7,
                color=tcolor, fontweight="bold")
    for x0, x1 in ((3.0, 3.52), (6.45, 6.97)):
        ax.add_patch(FancyArrowPatch((x0, y + h / 2), (x1, y + h / 2), arrowstyle="-|>",
                                     mutation_scale=7, color=GRAY, linewidth=0.9))

    def bracket(x0, x1, text):
        top = y + h + 0.2
        ax.plot([x0, x0, x1, x1], [top, top + 0.22, top + 0.22, top], color=GRAY, lw=0.7)
        ax.text((x0 + x1) / 2, top + 0.35, text, ha="center", va="bottom", fontsize=6.0,
                color="black", linespacing=1.05)

    bracket(1.55, 4.85, "Call-level authorization\n(Progent, CaMeL)\nchecks this step")
    bracket(5.15, 8.45, "EffectSeal\nchecks this step")
    ax.add_patch(FancyArrowPatch((6.71, 0.75), (6.71, y - 0.05), arrowstyle="-|>",
                                 mutation_scale=7, color=RED, linewidth=1.0))
    ax.text(6.71, 0.62, "a server changed after approval\nalters only this step",
            ha="center", va="top", fontsize=6.0, color="black", linespacing=1.05)
    save(fig, "fig0_teaser")


def confinement_bars() -> None:
    """A silent escape outside staging, with and without the boundary."""
    s = load("confinement.json")["summary"]
    groups = [("No boundary", s["escape_world_effect_unconfined"], s["honest_completion_unconfined"]),
              ("EffectSeal boundary", s["escape_world_effect_confined"], s["honest_completion_confined"])]
    fig, ax = plt.subplots(figsize=(COLUMN, 1.6))
    width = 0.34
    for g, (label, esc, hon) in enumerate(groups):
        for s_i, ((k, n), color, name) in enumerate(
                [((esc["k"], esc["n"]), RED, "Escape reached outside staging"),
                 ((hon["k"], hon["n"]), BLUE, "Honest workflow completed")]):
            x = g + (s_i - 0.5) * width
            ax.bar(x, max(100 * k / n, 0.8), width * 0.92, color=color, edgecolor="none",
                   label=name if g == 0 else None)
            ax.text(x, 100 * k / n + 4, f"{k}/{n}", ha="center", fontsize=5.8)
    ax.set_xticks(range(2), [g[0] for g in groups], fontsize=6.6)
    ax.set_ylabel("Runs (%)")
    ax.set_ylim(0, 128)
    ax.set_yticks([0, 50, 100])
    ax.legend(frameon=False, fontsize=5.9, loc="upper center", ncol=2,
              bbox_to_anchor=(0.5, 1.2), handlelength=1.0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="x", length=0)
    save(fig, "fig16_confinement")


def main() -> None:
    judge_boundary()
    slack_ladder()
    agent_harm()
    architecture()
    matched_heatmap()
    template_bars()
    confinement_bars()
    print("generated strengthening figures")


if __name__ == "__main__":
    main()

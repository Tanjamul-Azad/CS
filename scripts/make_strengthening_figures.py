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
    models = [("gpt-4.1-2025-04-14", "gpt-4.1"), ("gpt-5-mini-2025-08-07", "gpt-5-mini"),
              ("gpt-4.1-mini-2025-04-14", "gpt-4.1-mini")]
    series = [("honest", "Honest (false positive)", GRAY, "o"),
              ("consistent_indistinguishable", "Attack, transcript identical", TEAL, "s"),
              ("consistent_leaked", "Attack, transcript leaked", ORANGE, "D")]
    fig, ax = plt.subplots(figsize=(COLUMN, 2.05))
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
    ax.legend(frameon=False, fontsize=6, loc="upper center", bbox_to_anchor=(0.45, 1.3),
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
        label = "unbounded (L1)" if math.isinf(bits) else ("0 (L3, exact)" if bits == 0
                                                           else f"{bits:,.0f} (L2)")
        ax.text(shown * 1.15, y, label, va="center", fontsize=6)
    ax.set_yticks(range(len(rows)), [f"{r[1]}" for r in reversed(rows)], fontsize=6.4)
    ax.set_xscale("log")
    ax.set_xlim(0.5, cap * 60)
    ax.set_xlabel("Contract slack per honest call (bits, log)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=BLUE, label="development"),
                       Patch(color=ORANGE, label="held-out batch")],
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


def main() -> None:
    judge_boundary()
    slack_ladder()
    agent_harm()
    architecture()
    print("generated strengthening figures")


if __name__ == "__main__":
    main()

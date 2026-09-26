"""Generate the working manuscript's consolidated SVG/PNG figures."""

from __future__ import annotations

import json
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper" / "figures"
BLUE = "#2563EB"
TEAL = "#0F766E"
ORANGE = "#EA580C"
RED = "#B91C1C"
GRAY = "#475569"
LIGHT = "#E2E8F0"


def _save(fig: plt.Figure, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.svg", bbox_inches="tight", facecolor="white")
    fig.savefig(OUT / f"{name}.png", dpi=180, bbox_inches="tight", facecolor="white")
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def architecture() -> None:
    fig, ax = plt.subplots(figsize=(14.2, 4.5))
    ax.set_xlim(0, 14.2)
    ax.set_ylim(0, 4.2)
    ax.axis("off")
    stages = [
        ("1", "Preflight\nrequest shape", BLUE),
        ("2", "Atomic\nallowance", BLUE),
        ("3", "Private staging +\nuntrusted server", ORANGE),
        ("4", "Close all\nwriters", ORANGE),
        ("5", "Transport\nshape recheck", BLUE),
        ("6", "Bounded\nsingle read", TEAL),
        ("7", "Complete-tree\neffect diff", TEAL),
        ("8", "Same-read atomic\npromotion", TEAL),
    ]
    width, gap, start = 1.48, 0.24, 0.23
    y = 1.65
    for index, (number, label, color) in enumerate(stages):
        x = start + index * (width + gap)
        box = FancyBboxPatch(
            (x, y), width, 1.18,
            boxstyle="round,pad=0.04,rounding_size=0.08",
            facecolor=color, edgecolor="none", alpha=0.95,
        )
        ax.add_patch(box)
        ax.text(x + 0.12, y + 0.92, number, color="white", fontsize=10,
                fontweight="bold", ha="left")
        ax.text(x + width / 2, y + 0.50, label, color="white", fontsize=8.2,
                fontweight="bold", ha="center", va="center")
        if index < len(stages) - 1:
            ax.add_patch(FancyArrowPatch(
                (x + width + 0.02, y + 0.59),
                (x + width + gap - 0.02, y + 0.59),
                arrowstyle="-|>", mutation_scale=10, color=GRAY, linewidth=1.2,
            ))
    ax.text(0.25, 3.58, "Approved call", fontsize=12, fontweight="bold", color=GRAY)
    ax.text(13.95, 3.58, "Trusted store", fontsize=12, fontweight="bold",
            color=GRAY, ha="right")
    ax.add_patch(FancyArrowPatch((0.95, 3.48), (13.15, 3.48), arrowstyle="-|>",
                                 mutation_scale=12, color=LIGHT, linewidth=5))
    ax.text(
        7.1, 0.62,
        "Guarantee: contract-matching snapshot admission to trusted state",
        ha="center", fontsize=11, fontweight="bold", color=TEAL,
    )
    ax.text(
        7.1, 0.25,
        "Non-claim: rollback or prevention of effects outside the mediated boundary",
        ha="center", fontsize=10, color=RED,
    )
    _save(fig, "fig1_mcpgate_architecture")


def study_flow() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.5), gridspec_kw={"width_ratios": [1, 1.4]})
    ax = axes[0]
    counts = [8692, 4121, 1242]
    labels = ["Credential-free\ncandidates", "Answered\ntools/list", "Usable paired\nwrite trials"]
    widths = [1.0, 0.72, 0.52]
    colors = [BLUE, TEAL, ORANGE]
    y_positions = [2.8, 1.65, 0.5]
    shares = [100.0, 47.4, 14.3]
    for count, label, width, color, y, share in zip(
        counts, labels, widths, colors, y_positions, shares
    ):
        left = 0.5 - width / 2
        ax.add_patch(FancyBboxPatch(
            (left, y), width, 0.72, boxstyle="round,pad=0.02",
            facecolor=color, edgecolor="none",
        ))
        ax.text(0.5, y + 0.36, f"{count:,} ({share:.1f}%)\n{label}", color="white",
                ha="center", va="center", fontsize=9, fontweight="bold")
    ax.set_xlim(-0.1, 1.1)
    ax.set_ylim(0.1, 3.9)
    ax.set_title("Measurement funnel", fontsize=13, fontweight="bold")
    ax.axis("off")

    ax = axes[1]
    nodes = [
        (0.13, 0.72, "Observation\nboundary", BLUE),
        (0.40, 0.72, "Response-auditor\nmeasurement", ORANGE),
        (0.72, 0.72, "Contract\nexpressibility", TEAL),
        (0.24, 0.25, "Integrated\nadmission", TEAL),
        (0.56, 0.25, "Adaptive +\nablation", RED),
        (0.84, 0.25, "Held-out +\nperformance", GRAY),
    ]
    for x, y, label, color in nodes:
        ax.add_patch(FancyBboxPatch(
            (x - 0.11, y - 0.10), 0.22, 0.20,
            boxstyle="round,pad=0.02", facecolor=color, edgecolor="none",
        ))
        ax.text(x, y, label, color="white", ha="center", va="center",
                fontsize=8.5, fontweight="bold")
    arrows = [(0.24, 0.72, 0.29, 0.72), (0.51, 0.72, 0.61, 0.72),
              (0.72, 0.61, 0.30, 0.36), (0.35, 0.25, 0.45, 0.25),
              (0.67, 0.25, 0.73, 0.25)]
    for x1, y1, x2, y2 in arrows:
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                     mutation_scale=10, color=GRAY))
    ax.text(0.84, 0.06, "OPEN", color=RED, ha="center", fontweight="bold")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title("Evidence flow and remaining external-validity gate",
                 fontsize=13, fontweight="bold")
    ax.axis("off")
    fig.suptitle("From ecosystem measurement to effect admission", fontsize=14,
                 fontweight="bold")
    _save(fig, "fig2_study_flow")


def baseline_matrix() -> None:
    rows = json.loads((ROOT / "artifact" / "results" / "controlled_baselines.json").read_text(encoding="utf-8"))
    attacks = ["path_diversion", "content_substitution"]
    conditions = ["undefended", "plain_sandbox", "response_auditor",
                  "path_policy", "trusted_executor_gateway"]
    matrix = np.zeros((len(attacks), len(conditions)))
    surfaced = np.zeros_like(matrix)
    for row in rows:
        if row["attack"] in attacks and row["defense"] in conditions:
            i, j = attacks.index(row["attack"]), conditions.index(row["defense"])
            matrix[i, j] = 1 if row["attack_prevented"] else 0
            surfaced[i, j] = 1 if row.get("alerted") else 0
    fig, ax = plt.subplots(figsize=(10.7, 4.3))
    ax.imshow(matrix, cmap=plt.matplotlib.colors.ListedColormap(["#FEE2E2", "#DCFCE7"]),
              vmin=0, vmax=1, aspect="auto")
    for i in range(len(attacks)):
        for j in range(len(conditions)):
            label = "prevented" if matrix[i, j] else "landed"
            if surfaced[i, j] and not matrix[i, j]:
                label += "\nalerted"
            ax.text(j, i, label, ha="center", va="center", fontsize=8,
                    color=TEAL if matrix[i, j] else RED, fontweight="bold")
    ax.set_xticks(range(len(conditions)), [name.replace("_", "\n") for name in conditions])
    ax.set_yticks(range(len(attacks)), [name.replace("_", " ") for name in attacks])
    ax.set_title("Controlled baselines: prevention is not post-hoc detection",
                 fontsize=13, fontweight="bold")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    _save(fig, "fig3_controlled_baselines")


def ablation_matrix() -> None:
    rows = json.loads((ROOT / "artifact" / "results" / "controlled_ablations.json").read_text(encoding="utf-8"))
    labels = [row["variant"].replace("_", " ") for row in rows]
    values = [1 if row["failure_exposed"] else 0 for row in rows]
    colors = [TEAL if value == 0 else RED for value in values]
    fig, ax = plt.subplots(figsize=(10.4, 4.8))
    y = np.arange(len(rows))
    ax.barh(y, [1] * len(rows), color=colors, height=0.58)
    for index, row in enumerate(rows):
        ax.text(0.02, index, "no registered failure" if not values[index]
                else f"exposed: {row['attack']}", va="center", ha="left",
                color="white", fontsize=9, fontweight="bold")
    ax.set_yticks(y, labels)
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    ax.invert_yaxis()
    ax.set_title("Controlled ablations: removing each property restores its failure",
                 fontsize=13, fontweight="bold")
    ax.tick_params(axis="y", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    _save(fig, "fig4_controlled_ablations")


def latency_baseline() -> None:
    result = json.loads((ROOT / "artifact" / "results" / "exact_write_baseline.json").read_text(encoding="utf-8"))
    performance = result["performance"]
    percentiles = ["p50_ms", "p95_ms", "p99_ms"]
    direct = [performance["trusted_direct_writer"][key] for key in percentiles]
    mediated = [performance["mcpgate_exact_write"][key] for key in percentiles]
    x = np.arange(len(percentiles))
    fig, ax = plt.subplots(figsize=(7.7, 4.6))
    ax.bar(
        x - 0.18, direct, 0.36, label="Trusted direct writer", color=BLUE,
        edgecolor="black", linewidth=0.45,
    )
    ax.bar(
        x + 0.18, mediated, 0.36, label="MCPGate exact write",
        color=ORANGE, edgecolor="black", linewidth=0.45, hatch="///",
    )
    ax.set_xticks(x, [key[:3].upper() for key in percentiles])
    ax.set_ylabel("Latency (ms)")
    ax.set_title("Exact-write baseline (100 repetitions, development host)",
                 fontsize=13, fontweight="bold")
    ax.legend(frameon=False, loc="upper left")
    ax.grid(axis="y", color=LIGHT, linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.text(0.98, 0.97, "Development host only",
            transform=ax.transAxes, ha="right", va="top", color=RED, fontsize=9,
            fontweight="bold")
    _save(fig, "fig5_exact_write_latency")


def operating_points() -> None:
    rows = []
    with (ROOT / "results" / "tables" / "operating_points.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        for row in csv.DictReader(handle):
            rows.append({
                **row,
                "tpr": float(row["Detection rate"].rstrip("%")),
                "fpr": float(row["FPR"].rstrip("%")),
            })
    fig, ax = plt.subplots(figsize=(7.8, 5.0))
    for row in rows:
        is_final = row["Run"] == "R7 calibrated + error flag"
        color = TEAL if is_final else (BLUE if row["Point"] == "strict" else ORANGE)
        marker = "*" if is_final else ("o" if row["Point"] == "strict" else "s")
        size = 170 if is_final else 70
        ax.scatter(row["fpr"], row["tpr"], color=color, marker=marker, s=size,
                   edgecolor="white", linewidth=0.8, zorder=3)
        if is_final:
            ax.annotate(
                f"repaired {row['Point']}\n({row['fpr']:.1f}% FPR, {row['tpr']:.1f}% TPR)",
                (row["fpr"], row["tpr"]), xytext=(8, 5),
                textcoords="offset points", fontsize=8, color=TEAL,
            )
    ax.axvspan(0, 10, color="#DCFCE7", alpha=0.55, label="low-FPR region")
    ax.set_xlim(-2, 84)
    ax.set_ylim(-0.5, 8.5)
    ax.set_xlabel("Honest false-positive rate (%)")
    ax.set_ylabel("Attack detection rate (%)")
    ax.set_title("No tested response-auditor point combined low FPR with useful detection",
                 fontsize=12, fontweight="bold")
    ax.grid(color=LIGHT, linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.text(0.98, 0.03, "Same 218-candidate comparison; repaired run has 71 landed attacks",
            transform=ax.transAxes, ha="right", fontsize=8, color=GRAY)
    _save(fig, "fig6_auditor_operating_points")


def matched_evaluation() -> None:
    data = json.loads((ROOT / "artifact" / "results"
                       / "matched_filesystem.json").read_text(encoding="utf-8"))
    conditions = ["NONE", "PLAIN_SANDBOX", "MBA", "STATIC_LP", "MCPGATE"]
    labels = ["No\ndefense", "Plain\nsandbox", "Response\nauditor",
              "Static least\nprivilege", "MCPGate"]
    scenarios = [("A1", "Destination"), ("A2", "Content"), ("A3", "Hidden field"),
                 ("A4", "Extra effect"), ("A5", "Replay"),
                 ("A6", "False success"), ("A7", "Link alias")]
    prevented = {(s, c): [0, 0] for s, _ in scenarios for c in conditions}
    for server in data["servers"]:
        for cell in server.get("cells", []):
            key = (cell["scenario"], cell["condition"])
            if cell["scenario"] == "H0" or key not in prevented:
                continue
            prevented[key][1] += 1
            if cell["prevented"]:
                prevented[key][0] += 1
    grid = np.full((len(scenarios), len(conditions)), np.nan)
    for i, (scen, _) in enumerate(scenarios):
        for j, cond in enumerate(conditions):
            k, n = prevented[(scen, cond)]
            if n:
                grid[i, j] = k / n
    fig, ax = plt.subplots(figsize=(10.8, 5.2))
    cmap = plt.matplotlib.colors.LinearSegmentedColormap.from_list(
        "prev", ["#FEE2E2", "#FEF3C7", "#DCFCE7"])
    ax.imshow(grid, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i, (scen, _) in enumerate(scenarios):
        for j, cond in enumerate(conditions):
            k, n = prevented[(scen, cond)]
            if not n:
                continue
            ax.text(j, i, f"{k}/{n}", ha="center", va="center", fontsize=9,
                    color=TEAL if k == n else (RED if k == 0 else GRAY),
                    fontweight="bold")
    ax.set_xticks(range(len(conditions)), labels, fontsize=9)
    ax.set_yticks(range(len(scenarios)),
                  [f"{s}  {name}" for s, name in scenarios], fontsize=9)
    ax.set_title("Attacks prevented per scenario across five conditions "
                 "(prevented / servers)", fontsize=12.5, fontweight="bold")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    _save(fig, "fig7_matched_evaluation")


def matched_summary() -> None:
    conditions = ["NONE", "PLAIN_SANDBOX", "MBA", "STATIC_LP", "MCPGATE"]
    labels = ["No\ndefense", "Plain\nsandbox", "Response\nauditor",
              "Static least\nprivilege", "MCPGate"]

    def rate(path):
        data = json.loads((ROOT / "artifact" / "results" / path).read_text(encoding="utf-8"))
        out = {c: [0, 0] for c in conditions}
        for server in data["servers"]:
            for cell in server.get("cells", []):
                if cell["scenario"] == "H0":
                    continue
                out[cell["condition"]][1] += 1
                if cell["prevented"]:
                    out[cell["condition"]][0] += 1
        return [out[c][0] / out[c][1] if out[c][1] else 0.0 for c in conditions]

    fs = rate("matched_filesystem.json")
    sql = rate("matched_sql.json")
    x = np.arange(len(conditions))
    width = 0.38
    fig, ax = plt.subplots(figsize=(10.6, 4.8))
    b1 = ax.bar(x - width / 2, [v * 100 for v in fs], width,
                label="Filesystem (5 servers)", color=BLUE)
    b2 = ax.bar(x + width / 2, [v * 100 for v in sql], width,
                label="SQL (2 servers)", color=TEAL)
    for bars in (b1, b2):
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                    f"{bar.get_height():.0f}%", ha="center", va="bottom",
                    fontsize=9, fontweight="bold")
    ax.set_xticks(x, labels, fontsize=9.5)
    ax.set_ylabel("Attacks prevented", fontsize=10)
    ax.set_ylim(0, 108)
    ax.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax.set_title("Effect-integrity admission prevents what coarser policies miss, "
                 "in two domains", fontsize=12.5, fontweight="bold")
    ax.legend(frameon=False, fontsize=9.5, loc="upper left")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(length=0)
    _save(fig, "fig8_matched_summary")


def contact_sheet() -> None:
    from PIL import Image, ImageOps, ImageDraw

    names = [
        "fig1_mcpgate_architecture", "fig2_study_flow",
        "fig3_controlled_baselines", "fig4_controlled_ablations",
        "fig5_exact_write_latency", "fig6_auditor_operating_points",
        "fig7_matched_evaluation", "fig8_matched_summary",
    ]
    images = [Image.open(OUT / f"{name}.png").convert("RGB") for name in names]
    thumb_width = 900
    thumbs = []
    for name, source in zip(names, images):
        ratio = thumb_width / source.width
        resized = source.resize((thumb_width, int(source.height * ratio)))
        canvas = Image.new("RGB", (thumb_width, resized.height + 38), "white")
        canvas.paste(resized, (0, 38))
        ImageDraw.Draw(canvas).text((12, 10), name, fill="black")
        thumbs.append(canvas)
    height = sum(image.height for image in thumbs) + 20 * (len(thumbs) - 1)
    sheet = Image.new("RGB", (thumb_width, height), "#CBD5E1")
    y = 0
    for thumb in thumbs:
        sheet.paste(ImageOps.expand(thumb, border=1, fill="#94A3B8"), (0, y))
        y += thumb.height + 20
    sheet.save(OUT / "contact_sheet.png")


def main() -> None:
    architecture()
    study_flow()
    baseline_matrix()
    ablation_matrix()
    latency_baseline()
    operating_points()
    matched_evaluation()
    matched_summary()
    contact_sheet()
    print("generated 8 submission figures and contact sheet")


if __name__ == "__main__":
    main()

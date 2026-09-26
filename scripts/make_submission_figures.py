"""Generate the manuscript figures in a publication style.

Figures are vector PDFs sized for the two-column USENIX layout (3.33 in per
column, 7 in full width). They use a Times-compatible serif font at caption
size, embed TrueType fonts rather than Type 3, carry no title of their own
(the LaTeX caption states what each figure shows), and use the Okabe-Ito
palette so every encoding survives common color-vision deficiencies. Numbers
are read from checked-in result files.
"""

from __future__ import annotations

import json
import csv
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper" / "figures"
SUBMISSION = ROOT / "paper" / "submission" / "figures"
# Okabe-Ito palette
BLUE = "#0072B2"
TEAL = "#009E73"
ORANGE = "#E69F00"
RED = "#D55E00"
SKY = "#56B4E9"
GRAY = "#555555"
LIGHT = "#E5E5E5"
COLUMN, FULL = 3.33, 7.0

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "STIXGeneral", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 8,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})

# Figures that appear in the submission source.
PAPER_FIGURES = ("fig0_two_worlds", "fig1_mcpgate_architecture", "fig2_study_flow",
                 "fig6_auditor_operating_points", "fig7_matched_evaluation",
                 "fig8_matched_summary")


def _save(fig: plt.Figure, name: str) -> None:
    # A caption, not the image, names the figure.
    for axis in fig.axes:
        axis.set_title("")
    if getattr(fig, "_suptitle", None) is not None:
        fig._suptitle.set_text("")
    OUT.mkdir(parents=True, exist_ok=True)
    kwargs = {"bbox_inches": "tight", "pad_inches": 0.02, "facecolor": "white"}
    fig.savefig(OUT / f"{name}.svg", **kwargs)
    fig.savefig(OUT / f"{name}.png", dpi=220, **kwargs)
    fig.savefig(OUT / f"{name}.pdf", **kwargs)
    plt.close(fig)
    if name in PAPER_FIGURES:
        SUBMISSION.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(OUT / f"{name}.pdf", SUBMISSION / f"{name}.pdf")


def architecture() -> None:
    fig, ax = plt.subplots(figsize=(FULL, 1.95))
    ax.set_xlim(0, 14.2)
    ax.set_ylim(0, 4.0)
    ax.axis("off")
    stages = [
        ("1", "Check request\nshape", BLUE),
        ("2", "Reserve\nallowance", BLUE),
        ("3", "Run server in\nprivate staging", ORANGE),
        ("4", "Stop every\nwriter", ORANGE),
        ("5", "Recheck\ndelivered call", BLUE),
        ("6", "Read staging\nonce", TEAL),
        ("7", "Diff tree\nwith contract", TEAL),
        ("8", "Promote the\nsame bytes", TEAL),
    ]
    width, gap, start = 1.52, 0.2, 0.22
    y = 1.35
    # the untrusted part of the pipeline
    zone_x = start + 2 * (width + gap) - 0.1
    ax.add_patch(Rectangle((zone_x, y - 0.22), 2 * width + gap + 0.2, 1.62,
                           facecolor="none", edgecolor=ORANGE, linewidth=0.8,
                           linestyle=(0, (3, 2))))
    ax.text(zone_x + (2 * width + gap + 0.2) / 2, y - 0.5,
            "untrusted server runs here", ha="center", fontsize=6.5,
            color="#8A5A00", style="italic")
    for index, (number, label, color) in enumerate(stages):
        x = start + index * (width + gap)
        text_color = "black" if color == ORANGE else "white"
        ax.add_patch(FancyBboxPatch(
            (x, y), width, 1.18,
            boxstyle="round,pad=0.03,rounding_size=0.08",
            facecolor=color, edgecolor="none",
        ))
        ax.text(x + 0.1, y + 0.95, number, color=text_color, fontsize=7,
                fontweight="bold", ha="left", va="center")
        ax.text(x + width / 2, y + 0.47, label, color=text_color, fontsize=6.6,
                ha="center", va="center", linespacing=1.1)
        if index < len(stages) - 1:
            ax.add_patch(FancyArrowPatch(
                (x + width + 0.01, y + 0.59), (x + width + gap - 0.01, y + 0.59),
                arrowstyle="-|>", mutation_scale=6, color=GRAY, linewidth=0.8,
            ))
    ax.text(0.22, 3.4, "Approved call", fontsize=7.5, fontweight="bold",
            color=GRAY, va="center")
    ax.text(14.0, 3.4, "Trusted store", fontsize=7.5, fontweight="bold",
            color=GRAY, ha="right", va="center")
    ax.add_patch(FancyArrowPatch((2.0, 3.4), (12.1, 3.4), arrowstyle="-|>",
                                 mutation_scale=8, color="#BBBBBB", linewidth=1.2))
    ax.text(7.1, 0.28, "Refusal at any step discards staging and marks the "
            "allowance slot FAILED; nothing reaches the trusted store.",
            ha="center", fontsize=6.6, color=GRAY)
    _save(fig, "fig1_mcpgate_architecture")


def two_worlds() -> None:
    """Honest and malicious worlds that a client cannot tell apart."""
    fig, ax = plt.subplots(figsize=(COLUMN, 1.75))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")

    def lane(y, world, effect, effect_color):
        ax.text(0.05, y + 0.95, world, fontsize=7, fontweight="bold", color=GRAY)
        for x, w, label, face in ((0.05, 2.1, "Client", "#DDDDDD"),
                                  (3.7, 2.1, "Server", "#DDDDDD"),
                                  (7.4, 2.5, effect, effect_color)):
            ax.add_patch(FancyBboxPatch((x, y), w, 0.75,
                                        boxstyle="round,pad=0.02,rounding_size=0.1",
                                        facecolor=face, edgecolor="none"))
            ax.text(x + w / 2, y + 0.375, label, ha="center", va="center",
                    fontsize=6.8, color="white" if face != "#DDDDDD" else "black")
        ax.add_patch(FancyArrowPatch((2.2, y + 0.52), (3.65, y + 0.52),
                                     arrowstyle="-|>", mutation_scale=6,
                                     color=GRAY, linewidth=0.7))
        ax.add_patch(FancyArrowPatch((3.65, y + 0.23), (2.2, y + 0.23),
                                     arrowstyle="-|>", mutation_scale=6,
                                     color=GRAY, linewidth=0.7))
        ax.text(2.93, y + 0.62, "$a$", fontsize=7, ha="center", va="bottom")
        ax.text(2.93, y + 0.13, "$r$", fontsize=7, ha="center", va="top")
        ax.add_patch(FancyArrowPatch((5.85, y + 0.375), (7.35, y + 0.375),
                                     arrowstyle="-|>", mutation_scale=6,
                                     color=GRAY, linewidth=0.7))

    lane(3.9, "Honest world", "effect $e$", TEAL)
    lane(1.1, "Malicious world", "effect $e^{*}$", RED)
    ax.text(2.93, 0.25, "same $(a, r)$ in both worlds",
            ha="center", fontsize=6.6, style="italic", color=GRAY)
    ax.text(8.65, 0.25, "different effects",
            ha="center", fontsize=6.6, style="italic", color=GRAY)
    _save(fig, "fig0_two_worlds")


def study_flow() -> None:
    stages = [
        ("Registry candidates\nrunnable without credentials", 8692),
        ("Answered tools/list", 4121),
        ("Usable paired\nwrite trials", 1242),
    ]
    fig, ax = plt.subplots(figsize=(COLUMN, 1.45))
    y = np.arange(len(stages))[::-1]
    counts = [count for _, count in stages]
    ax.barh(y, counts, height=0.62, color=[BLUE, SKY, ORANGE], edgecolor="none")
    for yi, (_, count) in zip(y, stages):
        share = 100 * count / stages[0][1]
        ax.text(count + 120, yi, f"{count:,}  ({share:.1f}%)", va="center",
                fontsize=7)
    ax.set_yticks(y, [label for label, _ in stages])
    ax.set_xlim(0, 11500)
    ax.set_xlabel("Servers")
    ax.xaxis.set_major_formatter(
        plt.matplotlib.ticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
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
    fig, ax = plt.subplots(figsize=(COLUMN, 2.2))
    # pre-registered deployability target: detection >= 20% at FPR <= 10%
    ax.add_patch(Rectangle((0, 20), 10, 5, facecolor=TEAL, alpha=0.15,
                           edgecolor=TEAL, linewidth=0.8, zorder=1))
    ax.text(11, 22.5, "pre-registered target\n(no point reached it)",
            fontsize=6.5, color=TEAL, va="center")
    for point, marker, color in (("strict", "o", BLUE), ("permissive", "s", ORANGE)):
        earlier = [r for r in rows if r["Point"] == point
                   and r["Run"] != "R7 calibrated + error flag"]
        final = [r for r in rows if r["Point"] == point
                 and r["Run"] == "R7 calibrated + error flag"]
        ax.scatter([r["fpr"] for r in earlier], [r["tpr"] for r in earlier],
                   marker=marker, s=16, facecolor="none", edgecolor=color,
                   linewidth=0.8, zorder=3, label=f"{point}, earlier runs")
        ax.scatter([r["fpr"] for r in final], [r["tpr"] for r in final],
                   marker=marker, s=26, color=color, zorder=4,
                   label=f"{point}, final run")
    ax.set_xlim(-2, 84)
    ax.set_ylim(-1, 26)
    ax.set_xlabel("False-positive rate on honest servers (%)")
    ax.set_ylabel("Attacks detected (%)")
    ax.grid(color=LIGHT, linewidth=0.5)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="center right", handletextpad=0.3,
              borderaxespad=0.2)
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
    labels = ["None", "Sandbox", "Auditor", "Static\nLP", "MCPGate"]
    fig, ax = plt.subplots(figsize=(COLUMN, 2.35))
    cmap = plt.matplotlib.colors.LinearSegmentedColormap.from_list(
        "prevented", ["#FFFFFF", "#C6DBEF", BLUE])
    ax.imshow(grid, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i, (scen, _) in enumerate(scenarios):
        for j, cond in enumerate(conditions):
            k, n = prevented[(scen, cond)]
            if not n:
                continue
            ax.text(j, i, f"{k}/{n}", ha="center", va="center", fontsize=7,
                    color="white" if k / n > 0.6 else "black")
    ax.set_xticks(range(len(conditions)), labels)
    ax.set_yticks(range(len(scenarios)), [name for _, name in scenarios])
    ax.set_xticks(np.arange(-0.5, len(conditions)), minor=True)
    ax.set_yticks(np.arange(-0.5, len(scenarios)), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.2)
    ax.tick_params(which="both", length=0)
    ax.xaxis.tick_top()
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

    labels = ["None", "Sandbox", "Auditor", "Static\nLP", "MCPGate"]
    fs = rate("matched_filesystem.json")
    sql = rate("matched_sql.json")
    x = np.arange(len(conditions))
    width = 0.38
    fig, ax = plt.subplots(figsize=(COLUMN, 1.85))
    b1 = ax.bar(x - width / 2, [v * 100 for v in fs], width,
                label="Filesystem (5 servers, 31 attacks)", color=BLUE,
                edgecolor="black", linewidth=0.4)
    b2 = ax.bar(x + width / 2, [v * 100 for v in sql], width,
                label="SQL (2 servers, 10 attacks)", color=ORANGE,
                edgecolor="black", linewidth=0.4, hatch="////")
    for bars in (b1, b2):
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2,
                    f"{bar.get_height():.0f}", ha="center", va="bottom",
                    fontsize=6.5)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Attacks prevented (%)")
    ax.set_ylim(0, 125)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.legend(frameon=False, loc="upper left", ncol=1, handlelength=1.4,
              borderaxespad=0.1)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="x", length=0)
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
    two_worlds()
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

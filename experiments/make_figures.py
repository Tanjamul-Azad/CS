"""
Generate the paper's figures from the D1 corpus.

    python experiments/make_figures.py

Writes PDF (for LaTeX) and PNG (for reading) into figures/.
Every figure carries its own n, so a stale figure cannot be silently
mistaken for a current one.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from measure.classify import classify, derive_all, wilson_ci  # noqa: E402
from measure.harvest import load_corpus  # noqa: E402
from measure.report import read_fraction  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIGDIR = ROOT / "figures"

# Colourblind-safe, and legible in greyscale print.
C_BAD, C_MID, C_OK, C_BEST = "#B2182B", "#EF8A62", "#67A9CF", "#2166AC"
CLASS_COLORS = {"A0": C_BAD, "A1": C_MID, "A2": C_OK, "A3": C_BEST}

plt.rcParams.update({
    "font.size": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 150,
})


def save(fig, name: str) -> None:
    FIGDIR.mkdir(exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(FIGDIR / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)
    print(f"  figures/{name}.pdf + .png")


# --- F1: class distribution ---------------------------------------------

def fig_classes(classes: dict, n: int) -> None:
    dist = Counter(c for c, _ in classes.values())
    labels = ["A0\nunrelatable", "A1\nself-relatable",
              "A2\nread-backable", "A3\ninvariant-bound"]
    keys = ["A0", "A1", "A2", "A3"]
    vals = [100 * dist.get(k, 0) / n for k in keys]
    errs = [[100 * (dist.get(k, 0) / n - wilson_ci(dist.get(k, 0), n)[0])
             for k in keys],
            [100 * (wilson_ci(dist.get(k, 0), n)[1] - dist.get(k, 0) / n)
             for k in keys]]

    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    bars = ax.bar(labels, vals, color=[CLASS_COLORS[k] for k in keys],
                  yerr=errs, capsize=3, ecolor="#444", width=0.62)
    for b, v, k in zip(bars, vals, keys):
        ax.text(b.get_x() + b.get_width() / 2, v + 2.2,
                f"{v:.1f}%", ha="center", fontsize=9, fontweight="bold")
    ax.set_ylabel("share of tools (%)")
    ax.set_ylim(0, max(vals) * 1.28)
    ax.set_title(f"Auditability of MCP tools in the wild  (n={n:,})", fontsize=10)
    # Sits in open space to the right of the A0 bar, so it must be dark.
    ax.annotate("undetectable at any\naudit budget",
                xy=(0.34, vals[0] * 0.62), xytext=(1.05, vals[0] * 0.80),
                fontsize=8, color="#333", ha="left", va="center",
                arrowprops=dict(arrowstyle="->", color="#666", lw=0.8))
    save(fig, "F1-auditability-distribution")


# --- F2: the cost ladder -------------------------------------------------

def fig_ladder() -> None:
    """The paper's core claim. Hard-coded from the adversary ladder --
    these are properties of the implementations in bank_stateful.py, not
    of the corpus."""
    names = ["forge\nresponse", "+ shadow\nledger", "+ shadow\nbalance"]
    loc = [3, 9, 17]
    caught = [True, True, False]

    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    colors = [C_OK if c else C_BAD for c in caught]
    bars = ax.bar(names, loc, color=colors, width=0.55)
    for b, v, c in zip(bars, loc, caught):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.4,
                f"{v} LOC", ha="center", fontsize=9, fontweight="bold")
        ax.text(b.get_x() + b.get_width() / 2, v / 2,
                "caught" if c else "EVADES",
                ha="center", color="white", fontsize=9, fontweight="bold")

    ax.axhspan(0, 4, color="#888", alpha=0.10)
    ax.text(2.42, 2, "documented real-world\nMCP compromises",
            fontsize=7.5, color="#444", va="center", ha="right", style="italic")
    ax.set_ylabel("attacker code beyond honest baseline (LOC)")
    ax.set_ylim(0, 21)
    ax.set_title("Defenses do not stop the attacker — they price them", fontsize=10)
    save(fig, "F2-cost-ladder")


# --- F3: read coverage ---------------------------------------------------

def fig_read_coverage(tools, classes: dict) -> None:
    by_server = defaultdict(list)
    for t in tools:
        by_server[t.server_id].append(t)
    servers = {s: ts for s, ts in by_server.items() if len(ts) >= 2}

    bands = [(0.0, 0.01), (0.01, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 1.01)]
    labels = ["none", "<20%", "20–40%", "40–60%", ">60%"]
    xs, ys, ns = [], [], []
    for (lo, hi), lab in zip(bands, labels):
        sids = [s for s, ts in servers.items() if lo <= read_fraction(ts) < hi]
        keys = [(s, t) for (s, t) in classes if s in sids]
        if not keys:
            continue
        xs.append(lab)
        ys.append(100 * sum(1 for k in keys if classes[k][0] == "A0") / len(keys))
        ns.append(len(keys))

    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    ax.plot(xs, ys, "o-", color=C_BAD, lw=2, ms=7)
    for x, y, k in zip(xs, ys, ns):
        ax.annotate(f"{y:.0f}%\nn={k}", (x, y), textcoords="offset points",
                    xytext=(0, 10), ha="center", fontsize=7.5)
    ax.set_xlabel("share of a server's tools that are reads")
    ax.set_ylabel("A0 rate (%)")
    ax.set_ylim(0, 124)
    ax.set_title("A server with no reads cannot be audited at any size",
                 fontsize=10, pad=12)
    save(fig, "F3-read-coverage")


# --- F4: official vs community ------------------------------------------

def fig_official_vs_community(classes: dict, tools) -> None:
    """Reference servers are the best case, not the ecosystem."""
    official = {k for k in classes if k[0].startswith("modelcontextprotocol/")}
    if not official:
        print("  (skipping F4: no official servers in corpus)")
        return
    groups = {
        "official reference": [classes[k][0] for k in classes if k in official],
        "community": [classes[k][0] for k in classes if k not in official],
    }

    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    keys = ["A0", "A1", "A2", "A3"]
    bottoms = [0.0, 0.0]
    xs = list(range(len(groups)))
    for k in keys:
        vals = [100 * sum(1 for c in v if c == k) / max(len(v), 1)
                for v in groups.values()]
        ax.bar(xs, vals, bottom=bottoms, color=CLASS_COLORS[k],
               label=k, width=0.5)
        for x, (v, b) in enumerate(zip(vals, bottoms)):
            if v > 6:
                ax.text(x, b + v / 2, f"{v:.0f}%", ha="center",
                        color="white", fontsize=8, fontweight="bold")
        bottoms = [b + v for b, v in zip(bottoms, vals)]

    ax.set_xticks(xs)
    ax.set_xticklabels([f"{k}\n(n={len(v):,})" for k, v in groups.items()])
    ax.set_ylabel("share of tools (%)")
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, fontsize=8, ncol=4,
              loc="upper center", bbox_to_anchor=(0.5, 1.16))
    ax.set_title("The servers researchers test on are not the servers users run",
                 fontsize=10, pad=22)
    save(fig, "F4-official-vs-community")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path,
                    default=ROOT / "data" / "processed" / "d1_corpus.jsonl")
    args = ap.parse_args()

    tools = load_corpus(args.corpus)
    # F4 contrasts community against the official reference servers, which
    # live in a separate corpus written by run_harvest.py. Merge when present.
    official = ROOT / "data" / "processed" / "registry_corpus.jsonl"
    if official.exists():
        seen = {(t.server_id, t.name) for t in tools}
        extra = [t for t in load_corpus(official)
                 if (t.server_id, t.name) not in seen]
        if extra:
            print(f"  + {len(extra)} official reference tools for F4")
            tools = tools + extra
    classes = classify(tools, derive_all(tools))
    n = len(classes)
    print(f"figures from {n:,} tools / "
          f"{len({t.server_id for t in tools})} servers\n")

    fig_classes(classes, n)
    fig_ladder()
    fig_read_coverage(tools, classes)
    fig_official_vs_community(classes, tools)
    print("
Regenerate after any corpus or classifier change.")


if __name__ == "__main__":
    main()

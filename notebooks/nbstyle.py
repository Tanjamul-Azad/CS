"""Shared figure style for the analysis notebooks.

One place for the palette and the axis defaults, so every figure in the
project is consistent and the colour rules are stated once rather than
re-decided per chart.

Palette: the dataviz reference categorical theme, slots 1-3, used
verbatim. Those three slots are the documented all-pairs-validated subset
(worst-pair CVD dE 9.2 light), which is why no figure here uses more than
three categorical series -- past three, a fourth slot puts yellow beside
orange and fails the all-pairs floor. Where more than three groups exist
(the escape partition), they are encoded as ONE series with the group of
interest emphasised, not as four hues.

Rules applied throughout, from the same reference:
  - one axis, never two y-scales
  - colour follows the entity, never its rank
  - text stays in ink colours; a coloured mark beside it carries identity
  - grid and axes recede; no chartjunk
  - a legend whenever two or more series are present
"""

from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt

# Categorical slots 1-3 (light mode).
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
SERIES = [BLUE, ORANGE, AQUA]

# Single-hue ordinal ramp for staged magnitudes (the funnel). Steps 250+
# only: anything lighter drops below 2:1 on a light surface.
ORDINAL = ["#86b6ef", "#5598e7", "#2a78d6", "#184f95"]

# Ink. Text never takes a series colour.
INK = "#1a1a19"
INK_2 = "#57564f"
MUTED = "#8a897f"
GRID = "#e4e3dd"
SURFACE = "#ffffff"

# Status. Reserved -- never reused as "series 4".
CRITICAL = "#b42318"


def use_style() -> None:
    """Apply the shared rcParams. Call once at the top of a notebook."""
    mpl.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "figure.dpi": 110,
        "savefig.dpi": 160,
        "savefig.bbox": "tight",

        "font.size": 10,
        "font.family": "DejaVu Sans",
        "text.color": INK,
        "axes.labelcolor": INK_2,
        "xtick.color": INK_2,
        "ytick.color": INK_2,

        "axes.titlesize": 11.5,
        "axes.titleweight": "semibold",
        "axes.titlelocation": "left",
        "axes.titlepad": 10,
        "axes.labelsize": 9.5,

        # Recessive frame: only the axes that carry meaning.
        "axes.edgecolor": GRID,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,

        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "axes.axisbelow": True,

        "legend.frameon": False,
        "legend.fontsize": 9,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
    })


def bar_labels(ax, bars, fmt="{:,.0f}", pad=3, color=INK_2) -> None:
    """Direct-label bars. Selective by construction: these charts have few
    enough bars that every one carries a number the reader needs."""
    for b in bars:
        ax.annotate(fmt.format(b.get_height()),
                    (b.get_x() + b.get_width() / 2, b.get_height()),
                    ha="center", va="bottom", xytext=(0, pad),
                    textcoords="offset points", fontsize=9, color=color)


def save(fig, name: str, results_dir) -> None:
    """Write a figure into the tracked results tree."""
    d = results_dir / "figures"
    d.mkdir(parents=True, exist_ok=True)
    fig.savefig(d / f"{name}.png")
    print(f"saved results/figures/{name}.png")

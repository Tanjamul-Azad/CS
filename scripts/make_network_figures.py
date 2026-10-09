"""Figures for the network arm and the rewritten first page.

  fig0_teaser                    the postmark-mcp 1.0.16 incident: same call, same
                                 reply, different outgoing request; measured outcome
                                 of each defense in our pilot
  fig1_effectseal_architecture   pin time plus the two call-time paths (local state
                                 and outgoing requests)
  fig17_network_attacks          diverted requests stopped per attack type on the
                                 registry network servers, EffectSeal-N vs a
                                 destination (host allow-list) policy

Every number is read from a checked-in result JSON; nothing is typed by hand.
Style is shared with make_submission_figures.py (Okabe-Ito, validated with the
dataviz palette checker; orange falls below 3:1 on white, so orange marks carry
direct labels).

    python scripts/make_network_figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import (Circle, Ellipse, FancyArrowPatch, FancyBboxPatch,  # noqa: E402
                                Rectangle)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_strengthening_figures as sf  # noqa: E402

RES = sf.RES
BLUE, TEAL, ORANGE, RED, SKY, GRAY, LIGHT = sf.BLUE, sf.TEAL, sf.ORANGE, sf.RED, sf.SKY, sf.GRAY, sf.LIGHT
COLUMN, FULL = sf.COLUMN, sf.FULL
EVIDENCE = json.loads((sf.ROOT / "artifact/paper-evidence-20261009.json").read_text(encoding="utf-8"))
PILOT = EVIDENCE["network_postmark"]
AGENTBOUND = "network_postmark_agentbound_20261008-223502"
TOOLHIVE = "network_postmark_toolhive_20261008-230230"
MCPSCAN = "network_postmark_mcpscan_20261008-224058"
MATCHED = EVIDENCE["network_matched"]


def summary(run: str) -> dict:
    return json.loads((RES / run / "summary.json").read_text(encoding="utf-8"))


def postmark_outcomes() -> list[tuple[str, int, int]]:
    """(defense, diverted sends stopped, diverted sends) from the pilot runs."""
    pilot = summary(PILOT)["attacks"]
    es = (sum(v["effectseal"]["stopped"] for k,v in pilot.items() if not k.startswith("N-A8")),
          sum(v["effectseal"]["landed"] for k,v in pilot.items() if not k.startswith("N-A8")))
    rows = []
    scan = summary(MCPSCAN)["results"]
    attacks = {k: v for k, v in scan.items() if k.startswith("N-A")}
    rows.append(("Pinning alerts\n(mcp-scan)", sum(v["flagged_by_pinning"] for v in attacks.values()),
                 len(attacks)))
    for label, run in (("Host allow-list\n(ToolHive)", TOOLHIVE), ("Host allow-list\n(AgentBound)", AGENTBOUND)):
        att = {k:v for k,v in summary(run)["attacks"].items() if not k.startswith("N-A8")}
        trials = sum(v["trials"] for v in att.values())
        rows.append((label, trials - sum(v["diverted_or_noop"] for v in att.values()), trials))
    rows.append(("EffectSeal\n(request template)", *es))
    assert rows[-1] == ("EffectSeal\n(request template)", 21, 21), rows
    return rows


def teaser() -> None:
    fig = plt.figure(figsize=(COLUMN, 2.6))
    top = fig.add_axes([0.0, 0.46, 1.0, 0.54])
    top.set_xlim(0, 10)
    top.set_ylim(0.3, 4.3)
    top.axis("off")
    cols = [(0.0, 1.25, ""), (1.35, 2.75, "Approved call"), (4.2, 1.85, "Server's reply"),
            (6.1, 3.78, "Request sent to the provider")]
    for x, w, head in cols[1:]:
        top.text(x + w / 2, 3.95, head, ha="center", va="center", fontsize=7.2, fontweight="bold")
    top.text(0.05, 3.95, "(a)", ha="left", va="center", fontsize=7, fontweight="bold")
    rows = [(2.85, "1.0.15\n(honest)", "To: alice@corp", None),
            (1.55, "1.0.16\n(rug pull)", "To: alice@corp", "Bcc: attacker")]
    for y, ver, req, extra in rows:
        top.text(0.62, y, ver, ha="center", va="center", fontsize=7, linespacing=1.0)
        for (x, w, _), text, face in ((cols[1], "sendEmail(\nto=alice@corp)", "#EEF4FA"),
                                      (cols[2], "“Email sent”", "#EEF4FA")):
            top.add_patch(FancyBboxPatch((x, y - 0.5), w, 1.0,
                                         boxstyle="round,pad=0.02,rounding_size=0.1",
                                         facecolor=face, edgecolor="none"))
            top.text(x + w / 2, y, text, ha="center", va="center", fontsize=7,
                     family="monospace", linespacing=1.05)
        x, w, _ = cols[3]
        top.add_patch(FancyBboxPatch((x, y - 0.5), w, 1.0,
                                     boxstyle="round,pad=0.02,rounding_size=0.1",
                                     facecolor="#EEF4FA" if extra is None else "#FBE9DD",
                                     edgecolor="none" if extra is None else RED, linewidth=0.8))
        body = req if extra is None else f"{req}\n{extra}"
        top.text(x + w / 2, y, body, ha="center", va="center", fontsize=7, family="monospace",
                 linespacing=1.15)
    for (x, w, _), verdict, color in ((cols[1], "identical", GRAY), (cols[2], "identical", GRAY),
                                      (cols[3], "differs", RED)):
        top.text(x + w / 2, 0.55, verdict, ha="center", va="center", fontsize=7, color=color,
                 style="italic", fontweight="bold" if color == RED else "normal")
    top.plot([0.05, 9.95], [0.95, 0.95], color=LIGHT, lw=0.6)

    ax = fig.add_axes([0.36, 0.08, 0.6, 0.34])
    fig.text(0.005, 0.43, "(b)", ha="left", va="center", fontsize=7, fontweight="bold")
    data = postmark_outcomes()
    ys = list(range(len(data)))[::-1]
    for y, (label, k, n) in zip(ys, data):
        share = 100 * k / n
        color = BLUE if label.startswith("EffectSeal") else "#9A9A9A"
        ax.barh(y, share, height=0.62, color=color, edgecolor="none")
        ax.text(share + 2.5, y, f"{k}/{n}", va="center", fontsize=7)
    ax.set_yticks(ys, [d[0] for d in data], fontsize=7, linespacing=0.95)
    ax.set_xlim(0, 118)
    ax.set_xticks([0, 50, 100], ["0", "50", "100%"], fontsize=7)
    ax.set_xlabel("Pinning alerts; sends refused (%)", fontsize=7, labelpad=1.5)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="y", length=0, pad=2)
    sf.save(fig, "fig0_teaser")


def architecture() -> None:
    """Component view: who is trusted, where the server is confined, and the
    numbered admission steps shared by the local-state and network paths."""
    fig, ax = plt.subplots(figsize=(FULL, 3.0))
    ax.set_xlim(0, 21.7)
    ax.set_ylim(0.15, 9.35)
    ax.set_aspect("equal")
    ax.axis("off")
    trust_fill, untrusted_fill, untrusted_text, world_fill = "#DCE9F5", "#FBE8C4", "#7A4E00", "#EDEDED"

    def box(x, y, w, h, text, face, edge="none", tcolor="black", size=7, ls="-", weight="normal"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                    facecolor=face, edgecolor=edge, linewidth=0.7, linestyle=ls,
                                    zorder=3))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color=tcolor,
                fontsize=size, linespacing=1.1, zorder=4, fontweight=weight)

    def store(x, y, w, h, text, face, edge):
        # A data store, drawn as a cylinder.
        e = 0.32
        ax.add_patch(Rectangle((x, y + e / 2), w, h - e, facecolor=face, edgecolor="none",
                               zorder=3))
        ax.add_patch(Ellipse((x + w / 2, y + e / 2), w, e, facecolor=face, edgecolor=edge,
                             linewidth=0.7, zorder=2.9))
        for side in (x, x + w):
            ax.plot([side, side], [y + e / 2, y + h - e / 2], color=edge, lw=0.7, zorder=3.1)
        ax.add_patch(Ellipse((x + w / 2, y + h - e / 2), w, e, facecolor=face, edgecolor=edge,
                             linewidth=0.7, zorder=3.2))
        ax.text(x + w / 2, y + (h - e / 2) / 2, text, ha="center", va="center", fontsize=7,
                linespacing=1.1, zorder=4)

    def arrow(points, color=GRAY, ls="-"):
        for (x0, y0), (x1, y1) in zip(points[:-2], points[1:-1]):
            ax.plot([x0, x1], [y0, y1], color=color, lw=0.8, ls=ls, zorder=2)
        ax.add_patch(FancyArrowPatch(points[-2], points[-1], arrowstyle="-|>", mutation_scale=7,
                                     color=color, linewidth=0.8, linestyle=ls, zorder=2,
                                     shrinkA=0, shrinkB=0))

    def step(x, y, n):
        ax.add_patch(Circle((x, y), 0.25, facecolor="black", edgecolor="white", linewidth=0.6,
                            zorder=5))
        ax.text(x, y - 0.01, str(n), ha="center", va="center", color="white", fontsize=6.3,
                fontweight="bold", zorder=6)

    def label(x, y, text, color=GRAY, ha="left", size=7, **kw):
        ax.text(x, y, text, ha=ha, va="center", fontsize=size, color=color, zorder=4, **kw)

    # (a) Pin time.
    label(0.15, 9.1, "(a) Pin time: once per approved server version", "black",
          fontweight="bold")
    box(0.2, 7.45, 2.6, 1.2, "Approved\nexample call $a_0$", trust_fill, BLUE)
    box(3.4, 7.45, 4.0, 1.2, "Honest runs on\nperturbed copies of $a_0$\n(broker records)",
        untrusted_fill, ORANGE, ls=(0, (3, 1.5)))
    box(8.0, 7.45, 3.9, 1.2, "Abstract arguments;\nanti-unify the runs\ninto bounded holes",
        trust_fill, BLUE)
    store(12.5, 7.35, 3.6, 1.4, "Templates $\\tau$\n(effects, requests)", trust_fill, BLUE)
    for x0, x1 in ((2.8, 3.4), (7.4, 8.0), (11.9, 12.5)):
        arrow([(x0 + 0.04, 8.05), (x1 - 0.06, 8.05)])
    label(16.45, 8.05, "slack: a bound, in bits,\non what $\\tau$ leaves free", GRAY,
          style="italic", size=6.8)

    # (b) Call time: the trusted region holds everything but the server.
    label(0.15, 6.75, "(b) Call time", "black", fontweight="bold")
    ax.add_patch(FancyBboxPatch((2.95, 0.3), 15.95, 6.1, boxstyle="round,pad=0,rounding_size=0.2",
                                facecolor="#F4F8FC", edgecolor=BLUE, linewidth=0.9, zorder=0.5))
    label(18.75, 6.1, "EffectSeal (trusted)", BLUE, ha="right", fontweight="bold")
    ax.add_patch(FancyBboxPatch((6.55, 0.45), 3.5, 5.45, boxstyle="round,pad=0,rounding_size=0.15",
                                facecolor="#FEF7EA", edgecolor=ORANGE, linewidth=0.9,
                                linestyle=(0, (3, 1.5)), zorder=1))
    label(8.3, 5.6, "Confined sandbox", untrusted_text, ha="center", fontweight="bold")
    label(8.3, 4.95, "no direct egress;\ndummy token only", untrusted_text, ha="center",
          style="italic", size=6.6)

    box(0.2, 4.85, 2.05, 1.2, "LLM agent\n(MCP client)", world_fill)
    box(3.25, 4.85, 2.95, 1.2, "Check call $a$;\nbuild $C=\\tau(a)$", trust_fill, BLUE)
    box(3.25, 3.0, 2.95, 1.2, "Reserve one\nallowance slot", trust_fill, BLUE)
    box(6.85, 2.9, 2.9, 1.4, "MCP server\n(unmodified,\nuntrusted)", ORANGE)
    store(6.85, 0.65, 2.9, 1.4, "Private copy $D$\n(only writable)", untrusted_fill, ORANGE)
    arrow([(2.25, 5.45), (3.21, 5.45)])
    label(2.73, 5.72, "$a$", GRAY, ha="center", size=7)
    arrow([(4.72, 4.85), (4.72, 4.24)])
    arrow([(6.2, 3.6), (6.81, 3.6)])
    arrow([(8.3, 2.9), (8.3, 2.09)])
    label(8.42, 2.5, "writes", GRAY, size=6.6)
    step(3.25, 6.05, 1)
    step(3.25, 4.2, 2)
    step(6.85, 4.3, 3)

    # The pinned template reaches step 1 along the gap between the panels.
    arrow([(14.3, 7.35), (14.3, 6.95), (4.72, 6.95), (4.72, 6.09)], BLUE, ls=(0, (4, 2)))
    label(9.6, 7.17, "$\\tau$ for this server version", BLUE, ha="center", size=6.6)

    # The two effect paths run the same steps 4-6; step 5 is the decision.
    cols, w, h = (10.35, 13.22, 16.09), 2.52, 1.2
    lanes = (
        (3.0, "Outgoing requests: the broker",
         ("Terminate TLS;\ncanonical view", "Check every\nwrite against $C$",
          "Inject the real\ncredential; send"),
         "Upstream API\n(e.g., Postmark)"),
        (0.75, "Local state: the mediator",
         ("Stop writers;\nread $D$ once", "Check effect\n$E$ against $C$",
          "Promote the\nsame bytes"),
         "Real files,\nSQLite"),
    )
    for y, title, stages, world in lanes:
        label(10.2, y + h + 0.55, title, "black", style="italic")
        for i, (x, text) in enumerate(zip(cols, stages)):
            if i == 1:
                box(x, y, w, h, text, BLUE, tcolor="white")
            else:
                box(x, y, w, h, text, trust_fill, BLUE)
            step(x, y + h, 4 + i)
            if i:
                arrow([(cols[i - 1] + w + 0.03, y + h / 2), (x - 0.05, y + h / 2)])
        box(19.25, y, 2.4, h, world, world_fill)
        arrow([(cols[2] + w + 0.03, y + h / 2), (19.21, y + h / 2)])
        arrow([(9.75, y + h / 2), (10.31, y + h / 2)])

    # Refusal path.
    ax.add_patch(FancyBboxPatch((3.25, 0.6), 2.95, 1.95, boxstyle="round,pad=0,rounding_size=0.12",
                                facecolor="white", edgecolor=RED, linewidth=0.7,
                                linestyle=(0, (2, 1.5)), zorder=1))
    ax.text(4.72, 1.575, "Any failed check:\ndiscard $D$ or drop\nthe request; mark\nthe slot failed",
            ha="center", va="center", fontsize=6.8, color=RED, linespacing=1.15, zorder=4)
    sf.save(fig, "fig1_effectseal_architecture")


ATTACK_LABELS = {
    "A1_add_field": "Add a field (Bcc)",
    "A2_change_value": "Change a value",
    "A3_append_text": "Append text",
    "A4_extra_same_host": "Extra write, same host",
    "A5_extra_other_host": "Extra write, other host",
    "A6_credential_channel": "Credential channel",
    "A7_duplicate": "Duplicate send",
    "A8_silent_noop": "No-op: incomplete",
}


def network_attacks() -> None:
    att = summary(MATCHED)["attacks"]
    order = list(ATTACK_LABELS)
    fig, ax = plt.subplots(figsize=(COLUMN, 2.8))
    h = 0.36
    total_es = total_dst = total_n = 0
    for i, key in enumerate(order):
        v = att[key]
        y = len(order) - 1 - i
        n = v["applicable"]
        total_n += n
        total_es += v["effectseal_stops"]
        total_dst += v["destination_stops"]
        for off, k, color, name in ((h / 2, v["effectseal_stops"], BLUE, "EffectSeal (request template)"),
                                    (-h / 2, v["destination_stops"], ORANGE, "Destination policy (host allow-list)")):
            share = 100 * k / n
            ax.barh(y + off, share, height=h * 0.9, color=color, edgecolor="none",
                    label=name if i == 0 else None)
            ax.text(share + 2, y + off, f"{k}/{n}", va="center", fontsize=7)
    assert (total_es, total_n) == (912, 936) and total_dst == 120, (total_es, total_dst, total_n)
    ax.set_yticks(range(len(order)), [ATTACK_LABELS[k] for k in order][::-1], fontsize=7)
    ax.set_xlim(0, 125)
    ax.set_xticks([0, 50, 100], ["0", "50", "100%"], fontsize=7)
    ax.set_xlabel("Refused sends; no-op completion failures", fontsize=7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(frameon=False, fontsize=7, loc="upper center", ncol=1,
              bbox_to_anchor=(0.45, 1.22), handlelength=1.0)
    sf.save(fig, "fig17_network_attacks")


def main() -> None:
    teaser()
    architecture()
    network_attacks()
    print("generated network figures")


if __name__ == "__main__":
    main()

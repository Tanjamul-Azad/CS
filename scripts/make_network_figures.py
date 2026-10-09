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
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

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
    fig = plt.figure(figsize=(COLUMN, 3.0))
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
        ax.barh(y, max(share, 0.8), height=0.62, color=color, edgecolor="none")
        ax.text(share + 2.5, y, f"{k}/{n}", va="center", fontsize=7)
    ax.set_yticks(ys, [d[0] for d in data], fontsize=7, linespacing=0.95)
    ax.set_xlim(0, 118)
    ax.set_xticks([0, 50, 100], ["0", "50", "100%"], fontsize=7)
    ax.set_xlabel("Alerts (pinning); unauthorized sends refused", fontsize=7, labelpad=1.5)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="y", length=0, pad=2)
    sf.save(fig, "fig0_teaser")


def architecture() -> None:
    fig, ax = plt.subplots(figsize=(FULL, 2.85))
    ax.set_xlim(0, 14.2)
    ax.set_ylim(0.25, 6.55)
    ax.axis("off")

    def box(x, y, w, h, text, color, tcolor="white", size=7.2):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.08",
                                    facecolor=color, edgecolor="none"))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color=tcolor,
                fontsize=size, linespacing=1.08)

    def arrow(x0, y0, x1, y1, color=GRAY, style="-|>"):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=6,
                                     color=color, linewidth=0.8))

    ax.text(0.2, 6.3, "Pin time: once per approved server version", fontsize=7,
            fontweight="bold", color=GRAY)
    pin = [("Approved\nexemplar call", SKY, "black"),
           ("Perturbed honest runs\n(private copies; broker\nin record mode)", ORANGE, "black"),
           ("Anti-unify changed\nobjects and outgoing\nrequests", BLUE, "white"),
           ("Effect and request\ntemplates, slack\nin bits", BLUE, "white")]
    for i, (t, c, tc) in enumerate(pin):
        x = 0.2 + i * 2.6
        box(x, 5.05, 2.35, 1.0, t, c, tc)
        if i:
            arrow(x - 0.25, 5.55, x - 0.02, 5.55)
    tmpl_x, tmpl_y = 0.2 + 3 * 2.6 + 1.17, 5.05

    width, gap, start = 1.78, 0.22, 0.2

    def lane(y, title, stages, zone, note):
        ax.text(0.2, y + 1.08, title, fontsize=7, fontweight="bold", color=GRAY)
        zx = start + zone[0] * (width + gap) - 0.1
        zw = (zone[1] - zone[0]) * (width + gap) - gap + 0.2
        ax.add_patch(Rectangle((zx, y - 0.16), zw, 1.08, facecolor="none", edgecolor=ORANGE,
                               linewidth=0.8, linestyle=(0, (3, 2))))
        ax.text(zx + zw / 2, y - 0.36, note, ha="center", fontsize=7, color="#8A5A00",
                style="italic")
        for i, (t, c) in enumerate(stages):
            x = start + i * (width + gap)
            box(x, y, width, 0.76, t, c, "black" if c == ORANGE else "white")
            if i:
                arrow(x - gap + 0.01, y + 0.38, x - 0.01, y + 0.38)

    y_local, y_net = 2.95, 0.72
    lane(y_local, "Call time, local state (files, SQLite)",
         [("Check request\nshape", BLUE), ("Reserve\nallowance", BLUE),
          ("Run server on\na private copy", ORANGE), ("Stop every\nwriter", ORANGE),
          ("Read the copy\nonce", TEAL), ("Check the\ninstantiated\ntemplate", TEAL),
          ("Promote the\nsame bytes", TEAL)],
         (2, 4), "untrusted server: no network, read-only root, private copy writable")
    lane(y_net, "Call time, outgoing requests (network)",
         [("Server runs with\na dummy token", ORANGE), ("Only route out:\nthe broker", BLUE),
          ("TLS, typed\ncanonical view", TEAL), ("Durably reserve\nthe call", BLUE),
          ("Check ordered\nrequest template", TEAL), ("Inject credential\nand send", TEAL),
          ("Record send\noutcome", TEAL)],
         (0, 1), "no direct egress")
    # The pinned template feeds both check steps. One line runs down the gap
    # between the fifth and sixth columns, so it crosses no box.
    bus_x = start + 5 * (width + gap) - gap / 2
    check_left = start + 5 * (width + gap) + 0.25
    arrow(bus_x, tmpl_y, check_left, y_local + 0.76, BLUE)
    ax.plot([bus_x, bus_x], [tmpl_y, y_net + 1.05], color=BLUE, linewidth=0.8)
    arrow(bus_x, y_net + 1.05, start + 4 * (width + gap) + 0.25, y_net + 0.76, BLUE)
    del tmpl_x
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
            ax.barh(y + off, max(share, 0.8), height=h * 0.9, color=color, edgecolor="none",
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

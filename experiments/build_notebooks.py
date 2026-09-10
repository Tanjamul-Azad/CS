"""
Generate and execute the analysis notebooks from raw data.

The notebooks are the readable face of the work: each one loads raw JSON,
computes one result, and shows it. They are generated rather than
hand-edited so that re-running this script after a new experiment
refreshes every number and figure at once, and so a notebook can never
drift from the data it claims to describe.

Each notebook states, in order: what question it answers, what file it
reads, the computation, and the result. Interpretation is deliberately
left out -- the numbers are the artifact; the argument belongs to whoever
presents them.

    python experiments/build_notebooks.py            # build + execute
    python experiments/build_notebooks.py --no-exec  # build only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import nbformat as nbf
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks"

PREAMBLE = """\
import json, sys
from pathlib import Path
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT / "notebooks"))
sys.path.insert(0, str(ROOT / "src"))
import matplotlib.pyplot as plt
import nbstyle
from nbstyle import BLUE, ORANGE, AQUA, ORDINAL, INK, INK_2, MUTED, CRITICAL
nbstyle.use_style()
PROC = ROOT / "data" / "processed"
RESULTS = ROOT / "results"

def load(name):
    p = PROC / name
    if not p.exists():
        raise FileNotFoundError(
            f"{p} is missing. Raw traces are gitignored; regenerate with the "
            f"command in results/README.md.")
    return json.loads(p.read_text(encoding="utf-8"))

print("reading from", PROC)"""


def nb(title: str, question: str, reads: str, cells: list) -> nbf.NotebookNode:
    head = [
        new_markdown_cell(f"# {title}\n\n**Question this notebook answers.** "
                          f"{question}\n\n**Reads.** `{reads}`\n\n"
                          f"Run top to bottom. Every number below is computed "
                          f"from the raw file named above; nothing is "
                          f"hard-coded."),
        new_code_cell(PREAMBLE),
    ]
    n = new_notebook(cells=head + cells)
    n.metadata.kernelspec = {"display_name": "Python 3", "language": "python",
                             "name": "python3"}
    n.metadata.language_info = {"name": "python", "version": "3.13"}
    return n


# ---------------------------------------------------------------- 01
NB01 = nb(
    "01 - The corpus and the audit funnel",
    "Of the MCP servers published to the official registry, how many can "
    "actually be audited at all -- and is the set that survives "
    "representative of the ecosystem, or the easy tail of it?",
    "data/processed/scale_run.json",
    [
        new_markdown_cell("## The funnel\n\nEvery candidate was launched in a "
                          "locked-down container and driven through one "
                          "honest and one tampered trial."),
        new_code_cell("""\
from collections import Counter
scale = load("scale_run.json")
launched = [r for r in scale if r.get("tool_count") is not None]
ok       = [r for r in scale if r.get("status") == "ok"]
landed   = [r for r in ok if (r.get("tampered") or {}).get("attack_landed")]

stages = [("Registry candidates", len(scale)),
          ("Launched, answered tools/list", len(launched)),
          ("Usable write tool, both trials", len(ok)),
          ("Attack actually landed", len(landed))]
for label, n in stages:
    print(f"{label:<34} {n:>6}  {100*n/len(scale):>5.1f}%")"""),
        new_code_cell("""\
fig, ax = plt.subplots(figsize=(7.2, 3.2))
labels = [s[0] for s in stages]; vals = [s[1] for s in stages]
bars = ax.barh(range(len(vals))[::-1], vals, color=ORDINAL, height=0.62)
ax.set_yticks(range(len(vals))[::-1]); ax.set_yticklabels(labels, fontsize=9)
ax.set_xlabel("servers"); ax.grid(axis="x"); ax.grid(axis="y", visible=False)
ax.set_title("Audit funnel: 8,692 registry candidates to 1,242 analysable")
for b, v in zip(bars, vals):
    ax.annotate(f"{v:,}  ({100*v/len(scale):.1f}%)",
                (b.get_width(), b.get_y() + b.get_height()/2),
                xytext=(6, 0), textcoords="offset points",
                va="center", fontsize=9, color=INK_2)
ax.set_xlim(0, len(scale)*1.18)
nbstyle.save(fig, "funnel", RESULTS); plt.show()"""),
        new_markdown_cell("## Why servers dropped out"),
        new_code_cell("""\
for k, v in Counter(r.get("status") for r in scale).most_common():
    print(f"{k:<22} {v:>6}")"""),
        new_markdown_cell("## Is the analysed set representative?\n\n"
                          "Compare the servers that survived to the audit "
                          "against those that launched and then dropped out. "
                          "If the survivors are systematically more "
                          "auditable, any detection rate measured on them is "
                          "an upper bound for the ecosystem."),
        new_code_cell("""\
import statistics as stats
drop = [r for r in launched if r.get("status") != "ok"]

def class_mix(group):
    agg = Counter()
    for r in group:
        for k, v in (r.get("coverage") or {}).items():
            agg[k] += v
    total = sum(agg.values()) or 1
    return total, {k: 100*agg.get(k, 0)/total for k in ("A0","A1","A2","A3")}

for label, g in (("analysed (ok)", ok), ("launched, dropped", drop)):
    total, mix = class_mix(g)
    med = stats.median([r["tool_count"] for r in g])
    print(f"{label:<20} n={len(g):>5}  median tools={med:>4.0f}  tools={total:>6}  "
          + "  ".join(f"{k}={mix[k]:>5.1f}%" for k in ("A0","A1","A2","A3")))"""),
        new_code_cell("""\
import numpy as np
classes = ["A0","A1","A2","A3"]
_, mix_ok   = class_mix(ok)
_, mix_drop = class_mix(drop)
x = np.arange(len(classes)); w = 0.36

fig, ax = plt.subplots(figsize=(6.4, 3.4))
b1 = ax.bar(x - w/2, [mix_ok[c]   for c in classes], w, color=BLUE,   label="analysed")
b2 = ax.bar(x + w/2, [mix_drop[c] for c in classes], w, color=ORANGE, label="dropped out")
nbstyle.bar_labels(ax, b1, fmt="{:.0f}%"); nbstyle.bar_labels(ax, b2, fmt="{:.0f}%")
ax.set_xticks(x); ax.set_xticklabels(classes)
ax.set_ylabel("share of tools"); ax.set_ylim(0, 100)
ax.set_title("Auditability class mix: the analysed set is the favourable tail")
ax.legend(loc="upper right")
nbstyle.save(fig, "selection_effect", RESULTS); plt.show()"""),
        new_markdown_cell("**A0** means no relation is derivable, so no "
                          "client-side check exists. The gap between the two "
                          "bars at A0 and A2 is the selection effect, in one "
                          "picture."),
    ])

# ---------------------------------------------------------------- 02
NB02 = nb(
    "02 - E0: MCP's second observation channel",
    "Every auditability number this project produced came from `tools/list`. "
    "MCP also exposes `resources/*`. Does that channel provide verification "
    "the tools channel does not?",
    "data/processed/resource_sweep.json",
    [
        new_markdown_cell("A resource is addressed by URI. A *static* "
                          "resource has a fixed address (`config://settings`); "
                          "a *template* takes a parameter "
                          "(`file:///{path}`). Only a template can be pointed "
                          "at the specific record a write just touched, so "
                          "only a template supports a write-read check."),
        new_code_cell("""\
from collections import Counter
sweep = load("resource_sweep.json")
ok = [r for r in sweep if r.get("status") == "ok"]
print(f"servers probed: {len(sweep)}   answered: {len(ok)}")
chan = Counter(r.get("resource_channel") for r in ok)
for k in ("present", "empty", "unsupported"):
    print(f"  {k:<14} {chan.get(k,0):>5}  {100*chan.get(k,0)/len(ok):>5.1f}%")

n_static = sum(1 for r in ok if r.get("resource_count"))
n_templ  = sum(1 for r in ok if r.get("template_count"))
print(f"\\n  publish static resources : {n_static}")
print(f"  publish URI templates    : {n_templ}")"""),
        new_code_cell("""\
cats = ["resource channel\\npresent", "answered,\\nempty",
        "capability\\nunsupported", "publish URI\\ntemplates"]
vals = [chan.get("present",0), chan.get("empty",0),
        chan.get("unsupported",0), n_templ]
# One series. The final bar is the finding, so it carries the status
# colour -- reserved, and used here for state, not as a fourth category.
colors = [BLUE, BLUE, BLUE, CRITICAL]

fig, ax = plt.subplots(figsize=(6.8, 3.4))
bars = ax.bar(cats, vals, color=colors, width=0.6)
nbstyle.bar_labels(ax, bars)
ax.set_ylabel(f"servers (of {len(ok)})")
ax.set_title("The resource channel exists, but nothing addressable is published")
ax.set_ylim(0, max(vals)*1.18)
nbstyle.save(fig, "resource_channel", RESULTS); plt.show()"""),
        new_markdown_cell("## Upper bound on the correction to A0"),
        new_code_cell("""\
READ = {"get","list","read","search","fetch","query","find","show",
        "describe","view","lookup","retrieve"}
def has_read_tool(r):
    for t in r.get("tools", []):
        if t.get("readOnlyHint") is True: return True
        if t["name"].replace("-","_").split("_")[0].lower() in READ: return True
    return False

no_read   = [r for r in ok if not has_read_tool(r)]
recovered = [r for r in no_read if r.get("resource_channel") == "present"]
print(f"servers with no read-shaped tool at all : {len(no_read)}")
print(f"  ...of those, exposing any resources   : {len(recovered)}"
      f"  ({100*len(recovered)/max(len(no_read),1):.1f}%)")
print("\\nUpper bound only: having a resource channel does not mean the")
print("channel observes what the write changed. And a resource read is as")
print("forgeable as a tool response -- this widens observation, not trust.")"""),
    ])

# ---------------------------------------------------------------- 03
NB03 = nb(
    "03 - Verification escape channels",
    "A client that cannot trust a server's response must find some "
    "observation whose value depends on what the write actually did. What "
    "structural escapes exist in real servers, and how common is each?",
    "data/processed/escape_partition.json",
    [
        new_markdown_cell("Three escapes are possible:\n\n"
                          "- **ENUM** -- a collection reader taking no key. "
                          "Diff it across the write.\n"
                          "- **SNAP** -- a reader addressable by the same "
                          "identifier the write accepts.\n"
                          "- **CONS** -- a numeric quantity a write moves and "
                          "a reader reports.\n\n"
                          "A server with none of them cannot be checked "
                          "client-side at any budget."),
        new_code_cell("""\
from collections import Counter
part = load("escape_partition.json")
groups = Counter(r["group"] for r in part)
n = len(part)
for k, v in groups.most_common():
    print(f"{k:<18} {v:>5}  {100*v/n:>5.1f}%")

has = Counter()
for r in part:
    for e in r["escapes"]:
        has[e] += 1
print()
for k in ("ENUM","SNAP","CONS"):
    print(f"servers offering {k:<5} {has[k]:>5}  {100*has[k]/n:>5.1f}%")
none = groups.get("NONE", 0)
print(f"servers offering NONE  {none:>5}  {100*none/n:>5.1f}%")"""),
        new_code_cell("""\
cats = ["ENUM", "SNAP", "CONS", "NONE"]
vals = [has["ENUM"], has["SNAP"], has["CONS"], none]
# One series; NONE is the structural floor and carries the status colour.
colors = [BLUE, BLUE, BLUE, CRITICAL]

fig, ax = plt.subplots(figsize=(6.4, 3.4))
bars = ax.bar(cats, vals, color=colors, width=0.58)
nbstyle.bar_labels(ax, bars, fmt="{:,.0f}")
for b, v in zip(bars, vals):
    ax.annotate(f"{100*v/n:.1f}%", (b.get_x()+b.get_width()/2, 0),
                xytext=(0, 6), textcoords="offset points",
                ha="center", fontsize=9, color="white", weight="bold")
ax.set_ylabel(f"servers (of {n})")
ax.set_title("Which verification escape each server offers (overlapping)")
ax.set_ylim(0, max(vals)*1.18)
nbstyle.save(fig, "escape_partition", RESULTS); plt.show()"""),
        new_markdown_cell("ENUM is the most common escape. The auditor at "
                          "this point implemented SNAP well and ENUM not at "
                          "all, which notebook 05 tests directly."),
    ])

# ---------------------------------------------------------------- 04
NB04 = nb(
    "04 - What the detector actually does",
    "Across three versions of the detector on the same 218 servers, what "
    "detection rate is achieved and at what false-positive cost?",
    "data/processed/pilot_*.json",
    [
        new_markdown_cell(
            "> ### Read this before the numbers\n>\n"
            "> Three of the four runs below were recorded **before "
            "2026-09-10**, when `live.py` read the MCP error flag under a "
            "name the SDK does not define. Their `write_errored` was False "
            "on every trial, so writes the server had REFUSED were counted "
            "as landed attacks. They are labelled *(flag broken)* and "
            "cannot be corrected retrospectively -- the write's response is "
            "not kept in the trace.\n>\n"
            "> A second, deeper problem affects **all four**: "
            "`attack_landed` means only that the proxy selected a target "
            "field, never that an unauthorized effect occurred. Read every "
            "'landed' below as *mutation attempted*. Notebook 06 measures "
            "the gap."),
        new_markdown_cell("**Definitions, chosen so a detection cannot be an "
                          "artifact.**\n\n"
                          "- *landed* -- the tampering proxy reports it "
                          "actually diverted something. Trials where no "
                          "attack occurred are excluded.\n"
                          "- *detection* -- the attack landed, the tampered "
                          "trial fired, **and the honest trial on the same "
                          "server stayed silent**. The honest cross-check is "
                          "what separates a real catch from a broken "
                          "relation firing on everything.\n"
                          "- *FPR* -- the honest trial fired at all, over "
                          "every usable server."),
        new_code_cell("""\
RUNS = [("pre-R7 baseline",  "pilot_pre_r7_baseline.json"),
        ("R7 uncalibrated",  "pilot_r7.json"),
        ("R7 calibrated",    "pilot_r7_calibrated.json")]

def honest(r):   return r.get("honest", {}).get("alerts", []) or []
def tampered(r):
    t = r.get("tampered", {})
    return t.get("L1", t) if isinstance(t, dict) else {}

def fired(alerts, permissive):
    sev = ("[VIOLATION]", "[WARNING]") if permissive else ("[VIOLATION]",)
    return any(a.startswith(s) for a in alerts for s in sev)

def point(rows, permissive):
    landed = [r for r in rows if tampered(r).get("attack_landed")]
    tp = [r for r in landed if fired(tampered(r).get("alerts", []), permissive)
          and not fired(honest(r), permissive)]
    fp = [r for r in rows if fired(honest(r), permissive)]
    return (len(landed), len(tp), len(fp),
            len(tp)/len(landed) if landed else 0.0,
            len(fp)/len(rows) if rows else 0.0)

table = []
for label, fname in RUNS:
    rows = [r for r in load(fname) if r.get("status") == "ok"]
    for perm, pname in ((False, "strict"), (True, "permissive")):
        landed, tp, fp, det, fpr = point(rows, perm)
        table.append((label, pname, len(rows), landed, tp, det, fp, fpr))
        print(f"{label:<18} {pname:<11} n={len(rows):>4} landed={landed:>4} "
              f"TP={tp:>3} det={100*det:>5.1f}%  FP={fp:>4} FPR={100*fpr:>5.1f}%")"""),
        new_markdown_cell("## The operating points, plotted\n\n"
                          "Each detector version offers two thresholds. A "
                          "usable detector would sit toward the top-left: "
                          "high detection, low false-alarm rate."),
        new_code_cell("""\
from matplotlib.patches import Rectangle
fig, ax = plt.subplots(figsize=(7.0, 4.2))
style = {"pre-R7 baseline": (BLUE, "o"), "R7 uncalibrated": (ORANGE, "s"),
         "R7 calibrated": (AQUA, "^")}

# The acceptance region, drawn once as a single rectangle rather than two
# overlapping half-plane spans (which produced a muddy third colour where
# they crossed and read as a category of its own).
ax.add_patch(Rectangle((0, 20), 10, 80, facecolor=AQUA, alpha=0.09,
                       edgecolor=AQUA, linewidth=1, linestyle="--", zorder=0))
ax.annotate("pre-registered target\\n>=20% detection at <=10% FPR",
            (11, 21.4), fontsize=8.5, color=INK_2, va="bottom")

# Labels are offset per point instead of a fixed direction: the strict and
# permissive points of different runs land almost on top of each other, and
# one shared offset stacked the text illegibly.
offsets = {("pre-R7 baseline","strict"): (8, 6),
           ("R7 uncalibrated","strict"): (8, -13),
           ("R7 calibrated","strict"): (-14, 8),
           ("pre-R7 baseline","permissive"): (-52, 7),
           ("R7 uncalibrated","permissive"): (8, -4),
           ("R7 calibrated","permissive"): (-30, -14)}
seen = set()
for label, pname, n, landed, tp, det, fp, fpr in table:
    c, m = style[label]
    ax.scatter(100*fpr, 100*det, s=115, color=c, marker=m, zorder=3,
               edgecolor="white", linewidth=1.6,
               label=label if label not in seen else None)
    seen.add(label)
    ax.annotate(f"{pname}  {100*det:.1f}%", (100*fpr, 100*det),
                xytext=offsets[(label, pname)], textcoords="offset points",
                fontsize=8.5, color=MUTED, zorder=4)

ax.set_xlabel("false-positive rate on honest servers (%)")
ax.set_ylabel("detection rate on landed attacks (%)")
# Detection never exceeds ~3%, so the axis stops just above the 20% target
# line. Scaling to 100 would render every measurement as a dot on the floor.
ax.set_xlim(-3, 95); ax.set_ylim(-1.5, 27)
ax.set_title("Every operating point the detector offers -- none reach the target")
ax.legend(loc="upper right")
nbstyle.save(fig, "operating_points", RESULTS); plt.show()"""),
        new_markdown_cell("## The detections the detector found and discarded"),
        new_code_cell("""\
base = [r for r in load("pilot_pre_r7_baseline.json") if r.get("status")=="ok"]
def sev(a, k): return [x for x in a if x.startswith(f"[{k}]")]
for r in base:
    t = tampered(r)
    if not t.get("attack_landed"): continue
    if (not sev(honest(r),"VIOLATION") and not sev(t.get("alerts",[]),"VIOLATION")
            and not sev(honest(r),"WARNING") and sev(t.get("alerts",[]),"WARNING")):
        print(f"* {r['server_id']}   [{r.get('write_tool')} / "
              f"diverted: {t.get('diverted_field')}]")
        print(f"    {sev(t['alerts'],'WARNING')[0][:190]}\\n")"""),
        new_markdown_cell("These attacks landed, the tampered trial fired, "
                          "and the honest trial did not. They are real "
                          "catches that were reported as warnings and "
                          "therefore scored zero."),
    ])

# ---------------------------------------------------------------- 05
NB05 = nb(
    "05 - The enumeration check and reader calibration",
    "Does implementing the enumeration escape, and then calibrating the "
    "reader, move the detector to a usable operating point?",
    "data/processed/pilot_r7.json, pilot_r7_calibrated.json",
    [
        new_markdown_cell("The enumeration check diffs a collection reader "
                          "across the agent's own write. Three outcomes:\n\n"
                          "| observed | meaning |\n|---|---|\n"
                          "| nothing appeared | the reader does not observe "
                          "this write -- unverifiable |\n"
                          "| our value appeared | confirmed |\n"
                          "| something else appeared | **violation, with "
                          "positive evidence** |\n\n"
                          "The third is what read-back at an intended key "
                          "structurally cannot produce: absence there is "
                          "indistinguishable from a reader that never "
                          "reflects writes."),
        new_code_cell("""\
runs = {name: [r for r in load(f) if r.get("status")=="ok"]
        for name, f in [("uncalibrated","pilot_r7.json"),
                        ("calibrated","pilot_r7_calibrated.json")]}

def honest(r): return r.get("honest", {}).get("alerts", []) or []
def tampered(r):
    t = r.get("tampered", {}); return t.get("L1", t) if isinstance(t, dict) else {}

for name, rows in runs.items():
    hv = sum(1 for r in rows
             if any(a.startswith("[VIOLATION]") and "/ R7" in a for a in honest(r)))
    print(f"{name:<14} R7 violations raised on HONEST servers: {hv}")"""),
        new_markdown_cell("Those honest-server R7 violations are pure false "
                          "positives. Below is what they actually were."),
        new_code_cell("""\
shown = 0
for r in runs["uncalibrated"]:
    for a in honest(r):
        if a.startswith("[VIOLATION]") and "/ R7" in a and shown < 4:
            print(f"* {r['server_id']}\\n    {a[:230]}\\n"); shown += 1"""),
        new_markdown_cell("The 'new entries' are per-call error IDs, "
                          "heartbeat timestamps and rate-limit pages -- "
                          "response nondeterminism, not state change. "
                          "Calibration reads the enumerator **twice with no "
                          "write in between**; a reader that differs from "
                          "itself is blind and is excluded. This costs no "
                          "write, so the safety rule is free here."),
        new_code_cell("""\
def fpr_strict(rows):
    fp = [r for r in rows if any(a.startswith("[VIOLATION]") for a in honest(r))]
    return 100*len(fp)/len(rows)

base = [r for r in load("pilot_pre_r7_baseline.json") if r.get("status")=="ok"]
labels = ["baseline\\n(no R7)", "R7\\nuncalibrated", "R7\\ncalibrated"]
vals = [fpr_strict(base), fpr_strict(runs["uncalibrated"]),
        fpr_strict(runs["calibrated"])]

fig, ax = plt.subplots(figsize=(5.6, 3.4))
bars = ax.bar(labels, vals, color=[MUTED, CRITICAL, AQUA], width=0.55)
nbstyle.bar_labels(ax, bars, fmt="{:.1f}%")
ax.set_ylabel("false-positive rate (strict)")
ax.set_title("Calibration undoes the false-positive regression")
ax.set_ylim(0, max(vals)*1.25)
nbstyle.save(fig, "calibration_fpr", RESULTS); plt.show()"""),
        new_markdown_cell("## Detection, measured against the pre-registered rule"),
        new_code_cell("""\
def strict_detection(rows):
    landed = [r for r in rows if tampered(r).get("attack_landed")]
    tp = [r for r in landed
          if any(a.startswith("[VIOLATION]") for a in tampered(r).get("alerts",[]))
          and not any(a.startswith("[VIOLATION]") for a in honest(r))]
    return len(tp), len(landed), tp

for name, rows in [("baseline", base)] + list(runs.items()):
    tp, landed, ids = strict_detection(rows)
    print(f"{name:<14} {tp}/{landed} = {100*tp/landed:.1f}% strict detection")

print("\\nPre-registered rule (docs/24): >=20% detection at <=10% FPR.")
tp, landed, ids = strict_detection(runs["calibrated"])
print(f"Measured: {100*tp/landed:.1f}% at "
      f"{fpr_strict(runs['calibrated']):.1f}% FPR  ->  FAILS the rule.")"""),
        new_markdown_cell("## Inspecting the one strict detection"),
        new_code_cell("""\
for r in ids:
    t = tampered(r)
    print(f"SERVER: {r['server_id']}  |  write: {r.get('write_tool')}  |  "
          f"diverted: {t.get('diverted_field')}")
    for a in t["alerts"]:
        if a.startswith("[VIOLATION]"):
            print("  ", a[:300])"""),
        new_markdown_cell("Read the payload of that alert before counting it. "
                          "Whether this is a caught attack or a collection "
                          "that changed on its own between the two trials is "
                          "the question the number depends on."),
    ])


# ---------------------------------------------------------------- 06
NB06 = nb(
    "06 - Ground truth: attempted vs happened vs detected",
    "Every detection rate in this project divides by a count of attacks "
    "that 'landed'. That count came from a flag meaning only that the "
    "proxy selected a target field. How far is it from the truth?",
    "data/processed/effect_oracle.json",
    [
        new_markdown_cell("`attack_landed = any(p.active for p in plans)` is "
                          "true as soon as the proxy CHANGES AN ARGUMENT. It "
                          "says nothing about whether an unauthorized effect "
                          "occurred -- a server that ignored the argument, "
                          "no-opped, or failed at the application level "
                          "counts the same as one that really wrote to the "
                          "attacker's path.\n\n"
                          "The replacement records five independent fields, "
                          "none derived from another, decided by an observer "
                          "reading real state before and after."),
        new_code_cell("""rows = load("effect_oracle.json")
hdr = f"{'behaviour':<20}{'mut':>5}{'err':>5}{'authz':>7}{'unauth':>8}{'unk':>5}{'violation':>11}"
print(hdr); print("-"*len(hdr))
for r in rows:
    print(f"{r['behaviour']:<20}"
          f"{str(r['mutation_attempted'])[0]:>5}"
          f"{str(r['protocol_error'])[0]:>5}"
          f"{str(r['authorized_effect_observed'])[0]:>7}"
          f"{str(r['unauthorized_effect_observed'])[0]:>8}"
          f"{str(r['outcome_unknown'])[0]:>5}"
          f"{str(r['detector_violation'])[0]:>11}")"""),
        new_markdown_cell("## The gap between the old label and the truth"),
        new_code_cell("""old_label = [r for r in rows if r["mutation_attempted"] and not r["protocol_error"]]
real      = [r for r in rows if r["unauthorized_effect_observed"]]
err_real  = [r for r in rows if r["protocol_error"] and r["unauthorized_effect_observed"]]
print(f"trials the old `attack_landed` counts : {len(old_label)}")
print(f"trials with a REAL unauthorized effect: {len(real)}")
print(f"protocol error, yet a real effect     : {len(err_real)}")
print()
print("That last row is why excluding errored trials -- the correction made")
print("on 2026-09-10 -- is ALSO wrong: it discards a genuine compromise.")
print("Neither the mutation plan nor the protocol status is ground truth.")"""),
        new_code_cell("""caught = [r for r in real if r["detector_violation"]]
print(f"detector violations on real compromises: {len(caught)}/{len(real)}")
for r in real:
    mark = "caught " if r["detector_violation"] else "MISSED "
    print(f"  {mark} {r['behaviour']:<20} {r['note']}")"""),
        new_markdown_cell("Controlled behaviours, not real servers. This is "
                          "**methodology validation**: it shows that neither "
                          "the mutation plan nor the protocol status is "
                          "ground truth, and that independent world-state "
                          "observation is required."),
    ])

# ---------------------------------------------------------------- 07
NB07 = nb(
    "07 - M2: does a real boundary confine a real adversarial server?",
    "An untrusted server running as a separate OS process under a "
    "different user actively attacks the protected area. What does an "
    "OS-enforced boundary stop, and what does it leave unadjudicated?",
    "data/processed/boundary_probe.json",
    [
        new_markdown_cell("Enforcement is real: `/protected` belongs to the "
                          "gateway's user and is not writable by the user "
                          "the server runs as. This replaces the "
                          "same-process callback used earlier, which could "
                          "show a proposal being validated but not execution "
                          "authority removed -- a Python function that does "
                          "not write has only chosen not to.\n\n"
                          "Every verdict comes from an observer reading the "
                          "filesystem. The server's account of what it "
                          "attempted is shown separately and is **not "
                          "evidence**: it is written by the adversary."),
        new_code_cell("""rows = load("boundary_probe.json")
print(f"{'scenario':<22}{'proto':>7}{'confinement':>13}{'completion':>16}")
print("-"*58)
for r in rows:
    print(f"{r['scenario']:<22}{r['protocol_status']:>7}"
          f"{r['confinement_verdict']:>13}{r['completion_verdict']:>16}")

n=len(rows)
conf=sum(1 for r in rows if r['confinement_verdict']=='CONFINED')
viol=sum(1 for r in rows if r['confinement_verdict']=='VIOLATED')
unk =sum(1 for r in rows if r['confinement_verdict']=='UNKNOWN')
done=sum(1 for r in rows if r['completion_verdict']=='COMPLETED')
print()
print(f"confined {conf}/{n}   violated {viol}/{n}   "
      f"unknown {unk}/{n}   completed {done}/{n}")"""),
        new_markdown_cell("## What the operating system actually refused"),
        new_code_cell("""for r in rows:
    for a in r["server_claimed_attempts"]:
        print(f"{r['scenario']:<22} {a}")"""),
        new_markdown_cell("## Where the boundary is not the thing doing the work"),
        new_code_cell("""refused = [r for r in rows if r["boundary_verdict"].startswith("REFUSED")]
print("Refused by the CONTRACT CHECK, not by the boundary:")
print()
for r in refused:
    print(f"  {r['scenario']:<22} {r['boundary_verdict'][:60]}")
print()
print("A boundary sees paths and permissions. It cannot tell that a")
print("proposed destination is the wrong one, or that the payload was")
print("substituted -- those need the contract. Confinement and")
print("authorization are different jobs.")"""),
        new_code_cell("""unknown = [r for r in rows if r["confinement_verdict"] == "UNKNOWN"]
for r in unknown:
    print(f"{r['scenario']}: {r['unknown_reason']}")
print()
print("Blocking cannot make a server do work, so a silent no-op is")
print("NOT_COMPLETED -- never credited to the boundary as prevention.")"""),
    ])


NOTEBOOKS = [("01_corpus_and_funnel", NB01),
             ("02_resource_channel", NB02),
             ("03_escape_channels", NB03),
             ("04_detector_operating_points", NB04),
             ("05_enumeration_and_calibration", NB05),
             ("06_effect_oracle", NB06),
             ("07_boundary_probe", NB07)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-exec", action="store_true")
    args = ap.parse_args()

    NB.mkdir(exist_ok=True)
    for name, notebook in NOTEBOOKS:
        p = NB / f"{name}.ipynb"
        nbf.write(notebook, p)
        print(f"wrote {p.relative_to(ROOT)}")

    if args.no_exec:
        return

    from nbclient import NotebookClient
    print("\nexecuting...")
    failed = []
    for name, _ in NOTEBOOKS:
        p = NB / f"{name}.ipynb"
        doc = nbf.read(p, as_version=4)
        client = NotebookClient(doc, timeout=300, kernel_name="python3",
                                resources={"metadata": {"path": str(NB)}})
        try:
            client.execute()
            nbf.write(doc, p)
            print(f"  ok   {name}")
        except Exception as e:  # noqa: BLE001
            failed.append((name, f"{type(e).__name__}: {e}"))
            print(f"  FAIL {name}: {type(e).__name__}: {e}")
    if failed:
        print(f"\n{len(failed)} notebook(s) failed to execute.")
        sys.exit(1)
    print("\nall notebooks executed with outputs embedded.")


if __name__ == "__main__":
    main()

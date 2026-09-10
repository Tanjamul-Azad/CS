"""
How much trusted specification buys how much useful protection, at what cost?

Supersedes the framing in `run_append_pilot.py`, which asked a binary
question of one workflow. That framing hid two things this one measures:

  * a workflow is not "underspecified" -- individual PROPERTIES are.
    "Summarise the report into summary.txt" leaves the summary's semantic
    acceptability undetermined while leaving the destination and the frame
    condition perfectly checkable. Collapsing that to one verdict throws
    away most of what can be enforced.
  * specification is not free and not all-or-nothing. It arrives in
    degrees, and each degree costs someone effort.

So the axis is a LADDER of trusted information, applied to every workflow:

    L1  destination only        the approved file is the only one that changed
    L2  + structure             shape constraints: parseable, preserved,
                                cardinality, non-empty output
    L3  + content               the values themselves, where they are known

and the measurement at each rung is protection, honest completion,
per-property UNKNOWN, and the effort the specification took to write.

WHAT THIS DOES NOT ASSUME. It does NOT start from "underspecified means
high UNKNOWN, and that is the finding". Withholding a specification and
then observing UNKNOWN is a design consequence, not a result. The
measurement is how often real workflows leave a property undetermined,
and how much of it is recoverable by climbing the ladder.

VERDICT IS NOT ACTION. A property can be UNKNOWN while others are FAIL.
An UNKNOWN must never mask a known violation elsewhere in the same
execution, so verdicts are per-property and the commit decision is a
separate, declared policy over them (see `UNKNOWN_POLICY`).

    python experiments/run_specification_ladder.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "experiments" / "pilot" / "ladder_server.py"
OUT = ROOT / "data" / "processed" / "specification_ladder.json"

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"

# What the enforcement does when a property cannot be decided. Declared
# here rather than implied by the code, because "we could not tell" is a
# policy question, not a technical one, and different deployments answer
# it differently. Reported alongside every result.
UNKNOWN_POLICY = "commit"        # commit | block | confirm


# -- workflows --------------------------------------------------------------

@dataclass
class Workflow:
    name: str
    klass: str                      # exact | constrained | underspecified
    target: str
    initial: dict                   # filename -> content
    approved: dict                  # arguments of the approved call
    # Specification effort, recorded as declared fields per rung. A proxy,
    # and labelled as one: it counts what someone had to state, not how
    # long they took to think of it.
    spec_fields: dict = field(default_factory=dict)


LEDGER_INITIAL = [
    {"id": "r1", "recipient": "alice@example.test", "amount": 100},
    {"id": "r2", "recipient": "bob@example.test", "amount": 250},
]


def _jsonl(records: list) -> str:
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in records)


WORKFLOWS = [
    Workflow(
        "write_report", "exact", "report.txt",
        initial={"notes.txt": "raw notes\n"},
        approved={"path": "report.txt", "content": "quarterly numbers\n"},
        spec_fields={"L1": ["path"], "L2": ["path", "non_empty"],
                     "L3": ["path", "non_empty", "exact_bytes"]},
    ),
    Workflow(
        "append_record", "constrained", "ledger.jsonl",
        initial={"ledger.jsonl": _jsonl(LEDGER_INITIAL)},
        approved={"path": "ledger.jsonl",
                  "record": {"id": "r3", "recipient": "carol@example.test",
                             "amount": 75}},
        spec_fields={"L1": ["path"],
                     "L2": ["path", "parseable", "preserved", "cardinality"],
                     "L3": ["path", "parseable", "preserved", "cardinality",
                            "required_values"]},
    ),
    Workflow(
        "summarise", "underspecified", "summary.txt",
        initial={"report.txt": "a long report about revenue\n" * 20},
        approved={"path": "summary.txt", "source": "report.txt"},
        # L3 is deliberately ABSENT: no trusted statement determines which
        # summaries are acceptable. That absence is the thing being
        # measured, not a gap to be papered over.
        spec_fields={"L1": ["path"], "L2": ["path", "non_empty", "shorter_than_source"]},
    ),
]


# -- attacks ----------------------------------------------------------------

ATTACKS = ["honest", "wrong_destination", "content_substitution",
           "extra_file", "alter_other_file", "partial_write",
           "delayed_child", "silent_noop"]


# -- per-property checking --------------------------------------------------

def observe(root: Path) -> dict:
    return {str(p.relative_to(root)): p.read_text(encoding="utf-8",
                                                  errors="replace")
            for p in sorted(root.rglob("*")) if p.is_file()}


def parse_jsonl(blob: str):
    out = []
    for ln in blob.splitlines():
        if not ln.strip():
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            return out, False
    return out, True


def check_properties(wf: Workflow, rung: str, before: dict, after: dict) -> dict:
    """Per-property verdicts at one rung of the ladder.

    Each property is PASS, FAIL, or UNKNOWN independently. A property the
    current rung says nothing about is UNKNOWN -- never silently PASS,
    which would let missing specification read as satisfied specification.
    """
    target = wf.target
    v: dict[str, str] = {}

    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    deleted = {k for k in before if k not in after}

    # L1 and above: destination, and the frame around it.
    v["destination"] = PASS if changed <= {target} else FAIL
    v["frame_intact"] = PASS if not (changed - {target}) and not deleted else FAIL
    v["output_produced"] = PASS if after.get(target) else FAIL

    if rung == "L1":
        v["structure"] = UNKNOWN
        v["content"] = UNKNOWN
        return v

    # L2: structure.
    if wf.klass == "constrained":
        pre, _ = parse_jsonl(before.get(target, ""))
        post, ok = parse_jsonl(after.get(target, ""))
        if not ok:
            v["structure"] = FAIL
        elif post[:len(pre)] != pre:
            v["structure"] = FAIL          # preservation
        elif len(post) - len(pre) != 1:
            v["structure"] = FAIL          # cardinality
        else:
            v["structure"] = PASS
    elif wf.klass == "underspecified":
        body = after.get(target, "")
        src = after.get(wf.approved.get("source", ""), "")
        v["structure"] = (PASS if body and len(body) < len(src) else FAIL)
    else:
        v["structure"] = PASS if after.get(target) else FAIL

    if rung == "L2":
        v["content"] = UNKNOWN
        return v

    # L3: content. Only exists where a trusted statement determines it.
    if "L3" not in wf.spec_fields:
        # The honest outcome for an underspecified property. Not a
        # failure of the mechanism -- a fact about the task.
        v["content"] = UNKNOWN
        return v

    if wf.klass == "exact":
        v["content"] = (PASS if after.get(target) == wf.approved["content"]
                        else FAIL)
    else:
        pre, _ = parse_jsonl(before.get(target, ""))
        post, ok = parse_jsonl(after.get(target, ""))
        added = post[len(pre):] if ok else []
        v["content"] = (PASS if len(added) == 1
                        and added[0] == wf.approved["record"] else FAIL)
    return v


def decide(verdicts: dict) -> str:
    """Commit decision from per-property verdicts.

    A FAIL anywhere blocks, whatever else is UNKNOWN -- an undetermined
    property must not mask a determined violation in the same execution.
    """
    if FAIL in verdicts.values():
        return "discard"
    if UNKNOWN in verdicts.values():
        return {"commit": "commit", "block": "discard",
                "confirm": "confirm"}[UNKNOWN_POLICY]
    return "commit"


# -- independent oracle -----------------------------------------------------

def oracle(wf: Workflow, attack: str, before: dict, after: dict) -> dict:
    """Ground truth, from state and the attack's own definition -- never
    from the property checker above."""
    target = wf.target
    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    deleted = {k for k in before if k not in after}

    unauthorized = []
    for k in changed - {target}:
        unauthorized.append(f"{k} changed without approval")
    for k in deleted:
        unauthorized.append(f"{k} deleted without approval")

    body = after.get(target, "")
    if wf.klass == "exact" and body and body != wf.approved["content"]:
        unauthorized.append("target holds bytes that were not approved")
    if wf.klass == "constrained":
        pre, _ = parse_jsonl(before.get(target, ""))
        post, ok = parse_jsonl(after.get(target, ""))
        if not ok:
            unauthorized.append("target corrupted")
        else:
            if post[:len(pre)] != pre:
                unauthorized.append("a pre-existing record changed")
            for rec in post[len(pre):]:
                if rec != wf.approved["record"]:
                    unauthorized.append("an unapproved record was added")
    if wf.klass == "underspecified" and attack == "content_substitution":
        # The only case where ground truth is available for an
        # underspecified property: the attack's definition says what it
        # wrote. This is knowledge the DEFENSE does not have, which is
        # exactly the asymmetry being measured.
        if "ATTACKER" in body:
            unauthorized.append("target holds attacker-authored content")

    completed = bool(after.get(target)) and not unauthorized
    return {"unauthorized_effect": bool(unauthorized),
            "oracle_findings": unauthorized,
            "task_completed": completed,
            "no_change": after == before}


# -- conditions -------------------------------------------------------------

def run_server(wf: Workflow, attack: str, root: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, "-u", str(SERVER)],
        input=json.dumps({"workflow": wf.name, "klass": wf.klass,
                          "attack": attack, "target": wf.target,
                          "approved": wf.approved, "root": str(root)}) + "\n",
        capture_output=True, text=True, timeout=60)
    lines = (proc.stdout or "").strip().splitlines()
    return json.loads(lines[-1]) if lines else {"server_notes": ["no response"]}


def trial(wf: Workflow, attack: str, condition: str, rung: str) -> dict:
    root = Path(tempfile.mkdtemp(prefix="ladder-"))
    stage = None
    try:
        for name, content in wf.initial.items():
            (root / name).write_text(content, encoding="utf-8")
        before = observe(root)

        if condition == "undefended":
            run_server(wf, attack, root)
            time.sleep(0.6)
            after = observe(root)
            verdicts, decision, staged = {}, "no defense", None

        else:   # contract at rung `rung`
            stage = Path(tempfile.mkdtemp(prefix="ladderstage-"))
            shutil.copytree(root, stage, dirs_exist_ok=True)
            run_server(wf, attack, stage)
            time.sleep(0.6)
            staged = observe(stage)
            verdicts = check_properties(wf, rung, before, staged)
            decision = decide(verdicts)
            if decision == "commit":
                shutil.rmtree(root); shutil.copytree(stage, root)
            after = observe(root)

        o = oracle(wf, attack, before, after)
        return {"workflow": wf.name, "class": wf.klass, "attack": attack,
                "condition": condition, "rung": rung if condition != "undefended" else "-",
                "verdicts": verdicts, "decision": decision,
                "unknown_policy": UNKNOWN_POLICY,
                "spec_fields": len(wf.spec_fields.get(rung, [])) if condition != "undefended" else 0,
                "rung_available": rung in wf.spec_fields or condition == "undefended",
                "before": before, "staged": staged, "after": after, **o}
    finally:
        shutil.rmtree(root, ignore_errors=True)
        if stage:
            shutil.rmtree(stage, ignore_errors=True)


def main() -> None:
    rows = []
    for wf in WORKFLOWS:
        for attack in ATTACKS:
            rows.append(trial(wf, attack, "undefended", "-"))
            for rung in ("L1", "L2", "L3"):
                rows.append(trial(wf, attack, "contract", rung))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1), encoding="utf-8")

    print("=" * 94)
    print("SPECIFICATION LADDER -- protection bought per rung, and its cost")
    print("=" * 94)
    print(f"\nUNKNOWN policy: {UNKNOWN_POLICY}  (a declared choice, not a")
    print("technical consequence; block/confirm would move these numbers)\n")

    for wf in WORKFLOWS:
        print(f"\n{wf.name}  [{wf.klass}]  target={wf.target}")
        print("-" * 94)
        undef = {r["attack"]: r for r in rows
                 if r["workflow"] == wf.name and r["condition"] == "undefended"}
        landed = [a for a in ATTACKS
                  if a != "honest" and undef[a]["unauthorized_effect"]]
        print(f"  attacks that landed undefended: {len(landed)}"
              f"   ({', '.join(landed) or 'none'})")

        print(f"  {'rung':<6}{'spec fields':>12}{'prevented':>11}"
              f"{'honest done':>13}{'UNKNOWN props':>15}")
        for rung in ("L1", "L2", "L3"):
            sub = {r["attack"]: r for r in rows
                   if r["workflow"] == wf.name and r["rung"] == rung}
            if not sub:
                continue
            avail = rung in wf.spec_fields
            prevented = sum(1 for a in landed if not sub[a]["unauthorized_effect"])
            honest_ok = sub["honest"]["task_completed"]
            unk = sum(1 for r in sub.values()
                      for v in r["verdicts"].values() if v == UNKNOWN)
            tot = sum(len(r["verdicts"]) for r in sub.values()) or 1
            tag = "" if avail else "  (no L3 exists for this task)"
            print(f"  {rung:<6}{len(wf.spec_fields.get(rung, [])):>12}"
                  f"{prevented:>7}/{len(landed):<3}"
                  f"{str(honest_ok):>13}{100*unk/tot:>14.0f}%{tag}")

    print("\n" + "=" * 94)
    print("READ THIS BEFORE THE NUMBERS")
    print("=" * 94)
    print("""
  UNKNOWN here is a consequence of what was specified, not a discovery.
  Withholding L3 and then observing an undetermined content property is
  design, not measurement. What the ladder measures is how much of a
  real task's authorization is recoverable by stating more -- and where,
  as in `summarise`, no amount of stating fixes it because the acceptable
  outcome is not a function of the request.

  Per-property verdicts matter: an UNKNOWN content property sits beside
  PASS/FAIL destination and frame properties in the same execution, and a
  FAIL anywhere blocks regardless of what is UNKNOWN. Collapsing them
  would let missing specification read as satisfied specification.

  Spec fields is a PROXY for effort -- it counts what had to be stated,
  not the time or expertise to arrive at it.
""")
    print(f"wrote {OUT.relative_to(ROOT)}")
    print("reproduce: python experiments/run_specification_ladder.py")


if __name__ == "__main__":
    main()

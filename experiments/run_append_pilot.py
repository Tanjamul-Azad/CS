"""
Append pilot -- one workflow, three conditions, independently scored.

Purpose (docs/27 §9 step 1): check that the MEASUREMENT works before
building the full matrix. This validates an instrument. It does not
settle M1 and it does not demonstrate a system contribution.

WHY A STRUCTURED APPEND. It is the CONSTRAINED workflow class: the
caller knows a record must be added and what it must contain, but not the
file's final bytes. So the contract is a postcondition, and every attack
here is permission-compatible -- the server only touches files it is
allowed to touch. A path-level grant cannot separate any of them from an
honest append, because at the path level they are identical.

THE CONTRACT, five components, each checkable:

    target        only the approved file changed
    preservation  pre-existing records unchanged
    cardinality   exactly one new record
    required      the new record carries the approved id, recipient, amount
    frame         no other file changed

"A well-formed record was added" is deliberately NOT sufficient: an
attacker can write a valid record with the wrong recipient. Equally, no
semantic correctness beyond what the contract states is assumed.

THREE CONDITIONS, NOT FOUR. docs/27 lists a fourth -- "proposed
mediation" -- to be compared against the simple validator. No mechanism
difference has been specified yet, so running the same implementation
twice under two names would manufacture a comparison. It is omitted until
there is something to compare.

ORACLE INDEPENDENCE. The oracle does NOT reuse the contract predicates.
Each scenario separately declares the end state an honest execution
produces; the oracle reads real state and compares against that. Two
specifications, two code paths -- so a mistake in one does not hide
itself in the other by scoring its own output as correct.

    python experiments/run_append_pilot.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "experiments" / "pilot" / "append_server.py"
OUT = ROOT / "data" / "processed" / "append_pilot.json"
LEDGER = "ledger.jsonl"

INITIAL = [
    {"id": "r1", "recipient": "alice@example.test", "amount": 100},
    {"id": "r2", "recipient": "bob@example.test", "amount": 250},
]
APPROVED = {"id": "r3", "recipient": "carol@example.test", "amount": 75}


# -- scenarios --------------------------------------------------------------

@dataclass
class Scenario:
    name: str
    note: str
    # The end state an HONEST execution produces. Declared per scenario,
    # independently of the contract, and used only by the oracle.
    expect_records: list = field(default_factory=list)
    expect_other_files: dict = field(default_factory=dict)
    is_attack: bool = True


HONEST_END = INITIAL + [APPROVED]

SCENARIOS = [
    Scenario("honest", "appends exactly the approved record",
             HONEST_END, {}, is_attack=False),
    Scenario("wrong_field_value",
             "well-formed record, correct id, attacker's recipient", HONEST_END),
    Scenario("alter_existing",
             "appends correctly and quietly edits a prior record", HONEST_END),
    Scenario("extra_record", "appends the approved record and one more",
             HONEST_END),
    Scenario("extra_file", "appends correctly, also writes a second "
                           "permitted file", HONEST_END),
    Scenario("partial_write_then_error",
             "writes a truncated record, then reports failure", HONEST_END),
    Scenario("delayed_child_write",
             "appends correctly, child appends again after responding",
             HONEST_END),
    Scenario("silent_noop", "does nothing, reports nothing wrong", HONEST_END),
]


# -- trusted observation ----------------------------------------------------

def observe(root: Path) -> dict:
    """Raw state. No interpretation, no contract vocabulary."""
    files = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            files[str(p.relative_to(root))] = p.read_text(encoding="utf-8",
                                                          errors="replace")
    return files


def parse_records(blob: str) -> tuple[list, bool]:
    """(records, parseable). A truncated line makes the ledger
    unparseable, which is itself an observation worth keeping."""
    out = []
    for ln in blob.splitlines():
        if not ln.strip():
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            return out, False
    return out, True


def oracle(before: dict, after: dict, sc: Scenario) -> dict:
    """Independent judgement from observed state alone.

    Deliberately does not consult the contract. If both used the same
    predicate, a bug in it would score its own output as correct.

    THE DISTINCTION THIS FUNCTION EXISTS TO KEEP. An earlier version
    compared the final state against the honest end state and reported any
    difference as an unauthorized effect. That scored a contract DISCARD
    -- state rolled back, nothing unauthorized committed -- identically to
    a successful compromise, because the approved record is missing in
    both. They are opposite outcomes.

      authorized effect     the approved change is present
      unauthorized effect   some change from BEFORE that the approval did
                            not cover

    A rollback has neither. It is confinement working at a utility cost,
    and it is measured against `before`, never against the honest ideal.
    """
    pre, _ = parse_records(before.get(LEDGER, ""))
    post, parseable = parse_records(after.get(LEDGER, ""))
    other_before = {k: v for k, v in before.items() if k != LEDGER}
    other_after = {k: v for k, v in after.items() if k != LEDGER}

    authorized = (parseable and post == sc.expect_records
                  and other_after == sc.expect_other_files)

    unauthorized = []
    if not parseable:
        unauthorized.append("ledger is not parseable")
    else:
        if post[:len(pre)] != pre:
            unauthorized.append("a pre-existing record was changed")
        for i, rec in enumerate(post[len(pre):]):
            if rec != APPROVED:
                unauthorized.append(f"added record {i} is not the approved one")
    for k, v in other_after.items():
        if other_before.get(k) != v:
            unauthorized.append(f"file {k} changed and was not approved")

    return {
        "authorized_effect_observed": bool(authorized),
        "unauthorized_effect_observed": bool(unauthorized),
        "oracle_findings": unauthorized,
        "no_observable_change": after == before,
        "ledger_parseable": parseable,
    }


# -- the contract (the defense's own predicate) -----------------------------

def contract_check(before: dict, after: dict) -> dict:
    """Five components. This is the DEFENSE, not the oracle."""
    pre, _ = parse_records(before.get(LEDGER, ""))
    post, parseable = parse_records(after.get(LEDGER, ""))
    failures = []

    changed = {k for k in set(before) | set(after)
               if before.get(k) != after.get(k)}
    if changed - {LEDGER}:
        failures.append(f"target: changed {sorted(changed - {LEDGER})}")
    if not parseable:
        failures.append("target: ledger not parseable after the call")

    if post[:len(pre)] != pre:
        failures.append("preservation: a pre-existing record changed")
    if len(post) - len(pre) != 1:
        failures.append(f"cardinality: {len(post) - len(pre)} records added")
    elif post[-1] != APPROVED:
        diffs = [k for k in set(APPROVED) | set(post[-1])
                 if APPROVED.get(k) != post[-1].get(k)]
        failures.append(f"required values: new record differs in {sorted(diffs)}")

    return {"contract_pass": not failures, "contract_failures": failures}


# -- conditions -------------------------------------------------------------

def run_server(scenario: str, root: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, "-u", str(SERVER)],
        input=json.dumps({"scenario": scenario, "approved": APPROVED,
                          "root": str(root)}) + "\n",
        capture_output=True, text=True, timeout=60)
    line = (proc.stdout or "").strip().splitlines()
    return json.loads(line[-1]) if line else {"protocol_error": True,
                                              "server_notes": ["no response"]}


def trial(sc: Scenario, condition: str) -> dict:
    root = Path(tempfile.mkdtemp(prefix="append-"))
    try:
        (root / LEDGER).write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in INITIAL),
            encoding="utf-8")
        before = observe(root)

        if condition in ("undefended", "path_permission"):
            # Both let the server act on the real state. They differ only
            # in what a path grant would have refused -- and every attack
            # here is permission-compatible, so it refuses none of them.
            # Running it anyway is the point: it shows the grant is not
            # the thing making the difference.
            resp = run_server(sc.name, root)
            import time
            time.sleep(0.8)          # let a delayed child land
            after = observe(root)
            committed = after
            decision = "allowed (no content constraint)"

        elif condition == "contract_validator":
            # Stage, run, observe, check, commit or discard.
            stage = Path(tempfile.mkdtemp(prefix="stage-"))
            try:
                shutil.copytree(root, stage, dirs_exist_ok=True)
                stage_before = observe(stage)
                resp = run_server(sc.name, stage)
                import time
                time.sleep(0.8)
                stage_after = observe(stage)
                verdict = contract_check(stage_before, stage_after)
                if verdict["contract_pass"]:
                    shutil.rmtree(root)
                    shutil.copytree(stage, root)
                    decision = "committed"
                else:
                    decision = "discarded: " + "; ".join(
                        verdict["contract_failures"])
                after = observe(root)
                committed = after
                resp = {**resp, **verdict}
            finally:
                shutil.rmtree(stage, ignore_errors=True)
        else:
            raise ValueError(condition)

        o = oracle(before, committed, sc)
        return {
            "scenario": sc.name, "note": sc.note, "condition": condition,
            "is_attack": sc.is_attack,
            "protocol_error": bool(resp.get("protocol_error")),
            "server_notes": resp.get("server_notes", []),
            "contract_pass": resp.get("contract_pass"),
            "contract_failures": resp.get("contract_failures", []),
            "decision": decision,
            "before": before, "after": committed,
            **o,
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


CONDITIONS = ["undefended", "path_permission", "contract_validator"]


def main() -> None:
    rows = [trial(sc, c) for sc in SCENARIOS for c in CONDITIONS]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1), encoding="utf-8")

    by = {}
    for r in rows:
        by.setdefault(r["scenario"], {})[r["condition"]] = r

    print("=" * 100)
    print("APPEND PILOT -- constrained workflow, permission-compatible attacks")
    print("=" * 100)
    print("\nInstrument validation only. Not M1, not a system contribution.")
    print("Every attack touches only permitted files, so a path grant")
    print("refuses none of them -- that is what makes them the interesting")
    print("case, not a weakness of the baseline.\n")

    hdr = (f"{'scenario':<26}{'undef':>7}{'path':>7}{'contract':>10}"
           f"{'authz':>7}{'oracle finding':>32}")
    print(hdr); print("-" * 100)
    for name, p in by.items():
        u = p["undefended"]; pp = p["path_permission"]; cv = p["contract_validator"]
        f = (cv["oracle_findings"] or ["-"])[0]
        print(f"{name:<26}"
              f"{'BAD' if u['unauthorized_effect_observed'] else 'ok':>7}"
              f"{'BAD' if pp['unauthorized_effect_observed'] else 'ok':>7}"
              f"{'BAD' if cv['unauthorized_effect_observed'] else 'ok':>10}"
              f"{'yes' if cv['authorized_effect_observed'] else 'no':>7}"
              f"{f[:31]:>32}")

    attacks = [n for n, p in by.items() if p["undefended"]["is_attack"]]
    landed = [n for n in attacks
              if by[n]["undefended"]["unauthorized_effect_observed"]]
    for cond in ("path_permission", "contract_validator"):
        stopped = [n for n in landed
                   if not by[n][cond]["unauthorized_effect_observed"]]
        print(f"\n  {cond:<20} prevented {len(stopped)}/{len(landed)} "
              f"of attacks the undefended control demonstrated")

    honest = by["honest"]
    print("\n  what happened to the attacks that landed:")
    for cond in ("path_permission", "contract_validator"):
        rolled = [n for n in landed if by[n][cond]["no_observable_change"]]
        still = [n for n in landed
                 if by[n][cond]["unauthorized_effect_observed"]]
        print(f"    {cond:<20} rolled back {len(rolled)}   "
              f"still compromised {len(still)}")

    print(f"\n  honest completion   undefended={honest['undefended']['authorized_effect_observed']}"
          f"  path={honest['path_permission']['authorized_effect_observed']}"
          f"  contract={honest['contract_validator']['authorized_effect_observed']}")

    never = [n for n in attacks if n not in landed]
    if never:
        print(f"\n  did NOT land even undefended: {', '.join(never)}")
        print("  excluded from prevention -- counting them would credit a")
        print("  defense for an attack that never worked.")

    # Cross-check the DEFENSE's decision against the ORACLE's independent
    # reading of the undefended run. Comparing it against the oracle's
    # reading of the DEFENDED run would be circular: the contract caused
    # the rollback the oracle then observes, so they agree by construction
    # and nothing is tested. The question is whether the contract rejects
    # exactly the calls that would really have caused an unauthorized
    # effect.
    print("\n  contract decision vs what the attack really did (undefended):")
    fp, fn, noop_reject = [], [], []
    for name, p in by.items():
        rejected = p["contract_validator"]["contract_pass"] is False
        really_bad = p["undefended"]["unauthorized_effect_observed"]
        did_nothing = p["undefended"]["no_observable_change"]
        if rejected and not really_bad:
            (noop_reject if did_nothing else fp).append(name)
        elif really_bad and not rejected:
            fn.append(name)

    print(f"    missed a real compromise      : {len(fn)}"
          f"  {', '.join(fn) or '-'}")
    print(f"    rejected a harmless call      : {len(fp)}"
          f"  {', '.join(fp) or '-'}")
    print(f"    rejected a call that did NOTHING: {len(noop_reject)}"
          f"  {', '.join(noop_reject) or '-'}")
    if noop_reject:
        print("      Not a security failure and not a false positive on an")
        print("      honest call: the approved effect genuinely did not")
        print("      happen, so the contract is right to withhold a commit.")
        print("      It is a UTILITY cost and belongs in its own column.")

    print(f"\nwrote {OUT.relative_to(ROOT)}")
    print("reproduce: python experiments/run_append_pilot.py")


if __name__ == "__main__":
    main()

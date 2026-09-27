"""Workstream G: pin-time templates on the second held-out batch.

Same protocol as the development run (run_template_generalization.py), on
four servers never used in development, with the library frozen in
artifact/batch2-evaluation-plan.json. Two additions fixed in that plan before
the run: staged files are templated over their canonical view
(mcpgate.canonical), and the SQLite server is attacked with the SQL modes.
Pin-time policies (budget and structural) are evaluated on honest and
poisoned templates.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "docker"))

import run_matched_filesystem as mf  # noqa: E402
import run_template_generalization as tg  # noqa: E402
from run_adaptive_templates import budget_ok, structural_ok  # noqa: E402
from mcpgate.canonical import canonical_view  # noqa: E402
from mcpgate.template_inference import (TemplateError, infer_template,  # noqa: E402
                                        Observation, perturb_arguments)
from mcpgate.tree_mediator import TreeEntry, TreeSnapshot  # noqa: E402

PLAN = ROOT / "artifact" / "batch2-evaluation-plan.json"
MANIFEST = ROOT / "artifact" / "held-out-batch2-manifest.json"
OUT = ROOT / "artifact" / "results" / "batch2_templates.json"


def staged_canonical(sandbox: Path) -> dict:
    raw = mf._tree_snapshot_from_walk(sandbox)
    return {p: (e.kind, canonical_view(p, e.content) if e.kind == "file" and e.content
                is not None else e.content) for p, e in raw.entries.items()}


def snap(entries: dict) -> TreeSnapshot:
    out = {}
    for p, (k, c) in entries.items():
        if k == "file":
            out[p] = TreeEntry("file", size=len(c or b""),
                               sha256=hashlib.sha256(c or b"").hexdigest(), content=c or b"")
        else:
            out[p] = TreeEntry(k)
    return TreeSnapshot(entries=out)


def admit(contract, entries: dict, *, unsafe_check: bool) -> dict:
    if contract is None:
        return {"allowed": False, "reason": "no contract for this call"}
    if unsafe_check:
        bad = [p for p, (k, _) in entries.items() if k in {"symlink", "hardlink", "special"}]
        if bad:
            return {"allowed": False, "reason": f"unsafe object types: {bad[:8]}"}
    verdict = contract.evaluate(snap(entries))
    return {"allowed": verdict.allowed, "reason": verdict.reason[:600]}


def sql_landed(mode, attacked, honest, call_error):
    def rows(e):
        return {line for _, (k, c) in e.items() if k == "file" and c
                for line in c.decode("utf-8", "replace").splitlines() if line.startswith("row ")}

    def tables(e):
        return {line for _, (k, c) in e.items() if k == "file" and c
                for line in c.decode("utf-8", "replace").splitlines() if line.startswith("columns ")}
    a_rows, h_rows = rows(attacked), rows(honest)
    differs = tg._norm(attacked) != tg._norm(honest)
    if mode == "sql_value":
        evidence = bool(h_rows - a_rows) and not call_error
    elif mode == "sql_extra_row":
        evidence = len(a_rows) > len(h_rows)
    elif mode == "sql_extra_table":
        evidence = len(tables(attacked)) > len(tables(honest))
    else:
        evidence = len(a_rows) < len(h_rows) and not call_error
    return {"landed": bool(differs and evidence), "differs": differs, "evidence": bool(evidence)}


def pin_poisoned(pinner, plan, exemplar, fixed, tool):
    rng = random.Random(plan["training"]["seed"] + "-poison")
    observations = []
    for i in range(plan["training"]["runs"]):
        args = perturb_arguments(exemplar, rng, fixed=fixed, natural=bool(i % 2))
        pinner.count += 1
        sandbox = mf._fresh(pinner.base / f"poison-{pinner.count:03d}")
        mf._run_container(pinner.docker, pinner.server, sandbox, mode="noisy",
                          probe_args=tg._probe(args))
        observations.append(Observation(args, staged_canonical(sandbox),
                                        observed_at=datetime.now(timezone.utc)))
    return infer_template(tool, observations, fixed={k: exemplar.get(k) for k in sorted(fixed)})


def evaluate(docker, server, plan, base):
    tg._staged = staged_canonical  # pin() stages through the canonical view
    pinner = tg.Pinner(docker, server, base)
    pinned = tg.pin(pinner, plan)
    template = pinned["template"]
    print(f"    template: {len(template.objects)} objects, fixed={pinned['fixed']}", flush=True)
    rng = random.Random(plan["held_out_honest"]["seed"])
    n = plan["held_out_honest"]["calls"]
    shifted = plan["held_out_honest"]["scale_shift"]["calls"]
    scale = plan["held_out_honest"]["scale_shift"]["text_scale"]
    n_nat = plan["held_out_honest"]["natural_calls"]
    honest_rows, honest_state = [], []
    for index in range(n):
        s = scale if index >= n - shifted else 1.0
        natural = n - shifted - n_nat <= index < n - shifted
        args = perturb_arguments(pinned["exemplar"], rng, fixed=pinned["fixed"], scale=s,
                                 natural=natural)
        record, sandbox = pinner.run(args, tag="honest")
        entries = staged_canonical(sandbox)
        try:
            contract = template.instantiate(args, now=datetime.now(timezone.utc))
            slack = template.slack(args, clock_bound=True)
        except TemplateError as error:
            contract, slack = None, None
            print(f"    template error: {error}", flush=True)
        verdict = admit(contract, entries, unsafe_check=True)
        err = tg._last_call_error(record)
        honest_rows.append({"index": index, "scale": s, "natural": natural, "args": args,
                            "call_error": err, "allowed": verdict["allowed"],
                            "reason": verdict["reason"],
                            "false_block": (not err) and not verdict["allowed"],
                            "slack_bits": None if slack is None else slack.total_bits,
                            "slack_level": None if slack is None else slack.level,
                            "slack_per_rule": None if slack is None else dict(slack.per_rule)})
        if s == 1.0 and not natural:
            honest_state.append((args, entries))
        print(f"    honest {index:2d} nat={natural} scale={s} "
              f"{'OK' if verdict['allowed'] else ('ERR' if err else 'FALSE-BLOCK')} "
              f"slack={honest_rows[-1]['slack_bits']}", flush=True)

    modes = plan["attacks"]["sql" if server["effect_domain"] == "sql" else "fs"]
    attack_rows = []
    for mode in modes:
        for args, honest in honest_state[:plan["attacks"]["argument_sets_per_mode"]]:
            record, sandbox = pinner.run(args, mode=mode, tag=f"attack-{mode}")
            err = tg._last_call_error(record)
            attacked = staged_canonical(sandbox)
            if mode.startswith("sql_"):
                truth = sql_landed(mode, attacked, honest, err)
            else:
                truth = tg.landed(mode, attacked, honest, err)
            try:
                contract = template.instantiate(args, now=datetime.now(timezone.utc))
            except TemplateError:
                contract = None
            full = admit(contract, attacked, unsafe_check=True)
            blind = admit(tg.path_only(contract) if contract else None, attacked,
                          unsafe_check=False)
            attack_rows.append({"mode": mode, "args": args, "call_error": err, **truth,
                                "effectseal_template": full, "path_template": blind,
                                "prevented": {"NONE": False,
                                              "PATH_TEMPLATE": truth["landed"] and not blind["allowed"],
                                              "EFFECTSEAL_TEMPLATE": truth["landed"] and not full["allowed"]}})
            print(f"    attack {mode:15s} landed={truth['landed']} "
                  f"ES-T={'REFUSE' if not full['allowed'] else 'admit'} "
                  f"PATH-T={'REFUSE' if not blind['allowed'] else 'admit'}", flush=True)
    poisoned = pin_poisoned(pinner, plan, pinned["exemplar"], set(pinned["fixed"]), pinned["tool"])
    honest_slack = template.slack(pinned["exemplar"], clock_bound=True)
    poison_slack = poisoned.slack(pinned["exemplar"], clock_bound=True)
    policies = {"honest": {"slack_bits": honest_slack.total_bits, "budget": budget_ok(honest_slack),
                           "structural": structural_ok(template)},
                "poisoned": {"slack_bits": poison_slack.total_bits, "budget": budget_ok(poison_slack),
                             "structural": structural_ok(poisoned),
                             "changed_template": poisoned.to_json() != template.to_json()}}
    print(f"    pin policies: {policies}", flush=True)
    return {"server_id": server["id"], "package": server["package"], "version": server["version"],
            "effect_domain": server["effect_domain"], "tool": pinned["tool"],
            "fixed_fields": pinned["fixed"], "template": template.to_json(),
            "honest": honest_rows, "attacks": attack_rows, "pin_policies": policies,
            "runs": pinner.log}


def main() -> int:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    for path, digest in plan["library_frozen"].items():
        actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        if actual != digest:
            raise SystemExit(f"library changed since freeze: {path}")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    docker = mf._docker()
    scratch = Path(os.environ["MCPGATE_SCRATCH"]).parent / "batch2_templates"
    result = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
              "phase": plan["phase"], "plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
              "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(), "servers": []}
    for server in manifest["servers"]:
        print(f"=== {server['id']}", flush=True)
        try:
            row = evaluate(docker, server, plan, scratch / server["id"].replace("/", "__"))
        except Exception as error:  # noqa: BLE001
            import traceback
            row = {"server_id": server["id"], "error": f"{type(error).__name__}: {error}",
                   "trace": traceback.format_exc()[-1500:], "honest": [], "attacks": []}
            print(f"    ERROR {row['error']}", flush=True)
        result["servers"].append(row)
        honest = [r for s in result["servers"] for r in s["honest"] if not r["call_error"]]
        landed = [a for s in result["servers"] for a in s["attacks"] if a["landed"]]
        result["summary"] = {
            "honest_calls": len(honest), "false_blocks": sum(r["false_block"] for r in honest),
            "attacks_attempted": sum(len(s["attacks"]) for s in result["servers"]),
            "attacks_landed": len(landed),
            "prevented": {c: sum(a["prevented"][c] for a in landed)
                          for c in ("NONE", "PATH_TEMPLATE", "EFFECTSEAL_TEMPLATE")}}
        OUT.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Pin-time effect-template inference on the frozen filesystem servers.

The matched evaluation derives each contract from honest runs of the exact call
being admitted. This runner instead follows the deployment story:

  pin      run the approved server version on a few PERTURBED arguments in
           private copies and infer one effect template per tool
           (mcpgate.template_inference);
  admit    for each new call with UNSEEN arguments, instantiate the template
           into a tree contract at admission time and apply it to the staged
           result.

Held-out honest calls measure false blocks and contract slack. Attacks are
realized by the same interposition shims and consistent-liar tier as the
matched evaluation, on held-out arguments. Whether an attack landed is decided
by comparing its staged state with the honest staged state of the same
arguments; that honest run is an evaluator-only oracle the defense never sees.
Both admission policies are pure functions of the staged tree, so they are
applied to the same staged run.

The frozen plan is artifact/template-generalization-plan.json. These five
servers are the development set for this workstream; see the plan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "docker"))

import run_matched_filesystem as mf  # noqa: E402
from matched_probe import workload  # noqa: E402
from mcpgate.template_inference import (  # noqa: E402
    _CLOCK, EffectTemplate, Observation, TemplateError, enum_fields,
    infer_template, perturb_arguments)
from mcpgate.tree_mediator import (ContentPredicate, PathRule,  # noqa: E402
                                   TreeEffectContract)

PLAN = ROOT / "artifact" / "template-generalization-plan.json"
OUT = ROOT / "artifact" / "results" / "template_generalization.json"
MODE_SCENARIO = {"path": "A1", "content": "A2", "extra": "A4",
                 "noop": "A6", "symlink": "A7"}
PAYLOAD = b"ATTACKER CONTROLLED PAYLOAD"


def _probe(args: dict | None = None, *, schema: bool = False) -> list[str]:
    out = []
    if args is not None:
        out += ["--args-json", json.dumps(args)]
    if schema:
        out += ["--dump-schema"]
    return out


def _staged(sandbox: Path) -> dict[str, tuple[str, bytes | None]]:
    snap = mf._tree_snapshot_from_walk(sandbox)
    return {p: (e.kind, e.content) for p, e in snap.entries.items()}


def _has_effect(sandbox: Path) -> bool:
    """Did the run change any file in the client area?"""
    return any(kind == "file" for kind, _ in _staged(sandbox).values())


def _exemplar(server_id: str) -> tuple[str, dict]:
    sequence = workload(server_id, None, mf.MARKER, mf.CONTENT)
    return sequence[-1]


def _last_call_error(record: dict) -> bool:
    driver = record["driver"]
    calls = driver.get("calls") or []
    return driver.get("status") != "DRIVER_OK" or (bool(calls) and calls[-1]["is_error"])


class Pinner:
    def __init__(self, docker: str, server: dict, base: Path):
        self.docker, self.server, self.base = docker, server, base
        self.count = 0
        self.log: list[dict] = []

    def run(self, args: dict, *, mode: str = "none", schema: bool = False,
            tag: str = "run") -> tuple[dict, Path]:
        self.count += 1
        sandbox = mf._fresh(self.base / f"{tag}-{self.count:03d}")
        record = mf._run_container(self.docker, self.server, sandbox, mode=mode,
                                   probe_args=_probe(args, schema=schema))
        self.log.append({"tag": tag, "mode": mode, "args": args,
                         "exit_code": record["exit_code"],
                         "driver_status": record["driver"].get("status"),
                         "call_error": _last_call_error(record),
                         "latency_ms": record["latency_ms"]})
        return record, sandbox


def pin(pinner: Pinner, plan: dict) -> dict:
    tool, exemplar = _exemplar(pinner.server["id"])
    record, exemplar_box = pinner.run(exemplar, schema=True, tag="schema")
    schema = (record["driver"].get("tool_schemas") or {}).get(tool, {})
    validity = bool(plan["training"].get("validity_check"))
    exemplar_effect = _has_effect(exemplar_box)
    fixed = set(enum_fields(schema))
    rng = random.Random(plan["training"]["seed"])
    # discover fields the honest server refuses to see perturbed
    for name, value in exemplar.items():
        if name in fixed or not isinstance(value, str):
            continue
        probe_args = perturb_arguments({name: value}, rng)
        trial = {**exemplar, **probe_args}
        record, sandbox = pinner.run(trial, tag="discover")
        if _last_call_error(record):
            fixed.add(name)
        elif validity and exemplar_effect and not _has_effect(sandbox):
            # development change 5: a perturbation that silently writes
            # nothing selects behavior, so the field is held fixed
            fixed.add(name)
    observations = []
    # the approved exemplar itself is a natural observation; perturbations
    # alternate between random and natural-word free text (development change 4)
    training_args = [dict(exemplar)] + [
        perturb_arguments(exemplar, rng, fixed=fixed, natural=bool(i % 2))
        for i in range(plan["training"]["runs"])]
    # development change 7: some training runs use three times longer text,
    # so length-dependent structure (DOCX paragraph splits) is seen at pin time
    training_args += [
        perturb_arguments(exemplar, rng, fixed=fixed, natural=True,
                          scale=plan["training"].get("long_scale", 3.0))
        for _ in range(plan["training"].get("long_runs", 0))]
    for args in training_args:
        record, sandbox = pinner.run(args, tag="train")
        if _last_call_error(record):
            raise RuntimeError(f"honest training call failed: {record['driver']}")
        observations.append(Observation(args, _staged(sandbox),
                                        observed_at=datetime.now(timezone.utc)))
    template = infer_template(tool, observations,
                              fixed={k: exemplar.get(k) for k in sorted(fixed)})
    return {"tool": tool, "exemplar": exemplar, "fixed": sorted(fixed),
            "schema_enums": sorted(enum_fields(schema)), "template": template}


def path_only(contract: TreeEffectContract) -> TreeEffectContract:
    """Content-blind ablation: same rules, no content or kind restriction."""
    rules = tuple(PathRule(name=r.name, pattern=r.pattern,
                           kinds=frozenset({"file", "directory", "symlink",
                                            "hardlink", "special"}),
                           operations=r.operations, min_matches=r.min_matches,
                           max_matches=r.max_matches, content=ContentPredicate("any"))
                  for r in contract.rules)
    return TreeEffectContract(request=contract.request,
                              expected_before=contract.expected_before, rules=rules)


def admit(contract: TreeEffectContract | None, sandbox: Path, *,
          unsafe_check: bool) -> dict:
    if contract is None:
        return {"allowed": False, "reason": "no contract for this call"}
    snap = mf._tree_snapshot_from_walk(sandbox)
    if unsafe_check:
        dangerous = [p for p, e in snap.entries.items()
                     if e.kind in {"symlink", "hardlink", "special"}]
        if dangerous:
            return {"allowed": False, "reason": f"unsafe object types: {dangerous[:8]}"}
    verdict = contract.evaluate(snap)
    return {"allowed": verdict.allowed, "reason": verdict.reason[:600]}


def _norm(entries: dict) -> dict:
    out = {}
    for path, (kind, content) in entries.items():
        if kind == "file" and content is not None:
            try:
                text = _CLOCK.sub("<clock>", content.decode("utf-8"))
                out[path] = (kind, text)
            except UnicodeDecodeError:
                out[path] = (kind, hashlib.sha256(content).hexdigest())
        else:
            out[path] = (kind, None)
    return out


def landed(mode: str, attacked: dict, honest: dict, call_error: bool) -> dict:
    a, h = _norm(attacked), _norm(honest)
    differs = a != h
    if mode == "content":
        evidence = any(c and PAYLOAD in c for k, c in attacked.values() if k == "file")
    elif mode == "path":
        evidence = set(a) != set(h)
    elif mode == "extra":
        evidence = bool(set(a) - set(h))
    elif mode == "noop":
        evidence = (not call_error) and any(
            p not in a or a[p] != h[p] for p, (k, _) in h.items() if k == "file")
    elif mode == "symlink":
        evidence = any(k in {"symlink", "hardlink", "special"} for k, _ in attacked.values())
    else:
        evidence = False
    return {"landed": bool(differs and evidence), "differs": differs,
            "evidence": bool(evidence)}


def evaluate_server(docker: str, server: dict, applicable: set[str], plan: dict,
                    base: Path) -> dict:
    pinner = Pinner(docker, server, base)
    pinned = pin(pinner, plan)
    template: EffectTemplate = pinned["template"]
    print(f"    template: {len(template.objects)} objects, fixed={pinned['fixed']}",
          flush=True)
    rng = random.Random(plan["held_out_honest"]["seed"])
    n = plan["held_out_honest"]["calls"]
    shifted = plan["held_out_honest"]["scale_shift"]["calls"]
    scale = plan["held_out_honest"]["scale_shift"]["text_scale"]
    honest_rows: list[dict] = []
    honest_state: list[tuple[dict, dict]] = []
    for index in range(n):
        s = scale if index >= n - shifted else 1.0
        natural = plan["held_out_honest"].get("natural_calls", 0) > 0 and             n - shifted - plan["held_out_honest"]["natural_calls"] <= index < n - shifted
        args = perturb_arguments(pinned["exemplar"], rng, fixed=pinned["fixed"], scale=s,
                                 natural=natural)
        record, sandbox = pinner.run(args, tag="honest")
        now = datetime.now(timezone.utc)
        try:
            contract = template.instantiate(args, now=now)
            slack = template.slack(args, clock_bound=True)
        except TemplateError as error:
            contract, slack = None, None
            print(f"    template error: {error}", flush=True)
        verdict = admit(contract, sandbox, unsafe_check=True)
        row = {"index": index, "scale": s, "natural": natural, "args": args,
               "call_error": _last_call_error(record),
               "allowed": verdict["allowed"], "reason": verdict["reason"],
               "false_block": (not _last_call_error(record)) and not verdict["allowed"],
               "slack_bits": None if slack is None else slack.total_bits,
               "slack_level": None if slack is None else slack.level,
               "slack_per_rule": None if slack is None else dict(slack.per_rule)}
        honest_rows.append(row)
        if s == 1.0:
            honest_state.append((args, _staged(sandbox)))
        print(f"    honest {index:2d} scale={s} "
              f"{'OK' if row['allowed'] else 'FALSE-BLOCK'} "
              f"slack={row['slack_bits']}", flush=True)

    attack_rows: list[dict] = []
    per_mode = plan["attacks"]["argument_sets_per_mode"]
    for mode, scenario in MODE_SCENARIO.items():
        if scenario not in applicable:
            continue
        for args, honest in honest_state[:per_mode]:
            record, sandbox = pinner.run(args, mode=mode, tag=f"attack-{mode}")
            call_error = _last_call_error(record)
            attacked = _staged(sandbox)
            truth = landed(mode, attacked, honest, call_error)
            now = datetime.now(timezone.utc)
            try:
                contract = template.instantiate(args, now=now)
            except TemplateError:
                contract = None
            full = admit(contract, sandbox, unsafe_check=True)
            blind = admit(path_only(contract) if contract else None, sandbox,
                          unsafe_check=False)
            row = {"mode": mode, "scenario": scenario, "args": args,
                   "call_error": call_error, **truth,
                   "effectseal_template": full,
                   "path_template": blind,
                   "prevented": {
                       "NONE": False,
                       "PATH_TEMPLATE": truth["landed"] and not blind["allowed"],
                       "EFFECTSEAL_TEMPLATE": truth["landed"] and not full["allowed"],
                   }}
            attack_rows.append(row)
            print(f"    attack {mode:8s} landed={truth['landed']} "
                  f"ES-T={'REFUSE' if not full['allowed'] else 'admit'} "
                  f"PATH-T={'REFUSE' if not blind['allowed'] else 'admit'}", flush=True)
    return {"server_id": server["id"], "package": server["package"],
            "version": server["version"], "tool": pinned["tool"],
            "fixed_fields": pinned["fixed"], "schema_enums": pinned["schema_enums"],
            "template": template.to_json(), "honest": honest_rows,
            "attacks": attack_rows, "runs": pinner.log}


def summarize(servers: list[dict]) -> dict:
    honest = [r for s in servers for r in s["honest"] if not r["call_error"]]
    attacks = [a for s in servers for a in s["attacks"]]
    landed_rows = [a for a in attacks if a["landed"]]
    by_server = {}
    for s in servers:
        rows = [r for r in s["honest"] if not r["call_error"]]
        slacks = [r["slack_bits"] for r in rows if r["slack_bits"] is not None]
        by_server[s["server_id"]] = {
            "honest_calls": len(rows),
            "false_blocks": sum(r["false_block"] for r in rows),
            "slack_bits_max": max(slacks) if slacks else None,
            "slack_levels": sorted({r["slack_level"] for r in rows if r["slack_level"]}),
            "landed": sum(a["landed"] for a in s["attacks"]),
            "prevented_effectseal_template": sum(
                a["prevented"]["EFFECTSEAL_TEMPLATE"] for a in s["attacks"]),
            "prevented_path_template": sum(
                a["prevented"]["PATH_TEMPLATE"] for a in s["attacks"]),
        }
    return {
        "honest_calls": len(honest),
        "false_blocks": sum(r["false_block"] for r in honest),
        "false_block_rate": (sum(r["false_block"] for r in honest) / len(honest)
                             if honest else None),
        "attacks_attempted": len(attacks),
        "attacks_landed": len(landed_rows),
        "prevented": {c: sum(a["prevented"][c] for a in landed_rows)
                      for c in ("NONE", "PATH_TEMPLATE", "EFFECTSEAL_TEMPLATE")},
        "by_server": by_server,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-id", action="append")
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--plan", default=str(PLAN))
    args = parser.parse_args()
    plan_path = Path(args.plan)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    docker = mf._docker()
    manifest = json.loads(mf.MANIFEST.read_text(encoding="utf-8"))
    eval_plan = json.loads(mf.PLAN.read_text(encoding="utf-8"))
    applicability = {p["id"]: set(p["applicable"]) for p in eval_plan["server_plans"]}
    by_id = {s["id"]: s for s in manifest["servers"]}
    out = Path(args.out)
    result: dict[str, Any] = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "phase": plan["phase"],
        "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        "inference_sha256": hashlib.sha256(
            (ROOT / "src" / "mcpgate" / "template_inference.py").read_bytes()).hexdigest(),
        "servers": [],
    }
    for server_id in args.server_id or plan["servers"]:
        print(f"=== {server_id}", flush=True)
        base = mf.SCRATCH.parent / "template" / server_id.replace("/", "__")
        try:
            row = evaluate_server(docker, by_id[server_id],
                                  applicability[server_id], plan, base)
        except Exception as error:  # noqa: BLE001 - record, keep going
            row = {"server_id": server_id, "error": f"{type(error).__name__}: {error}",
                   "honest": [], "attacks": []}
            print(f"    ERROR {row['error']}", flush=True)
        result["servers"].append(row)
        result["summary"] = summarize([s for s in result["servers"] if "error" not in s])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

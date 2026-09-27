"""Workstream D: adaptive attacks against pin-time effect templates.

An adversary that knows the mechanism has three levers: hide data inside the
freedom a template leaves (holes), write into places a weaker contract left
unconstrained, or poison the template at pin time so its holes are wide.
This runner measures each against both the pin-time template and the
fixed-call contract of the matched evaluation. Plan:
artifact/adaptive-templates-plan.json.
"""

from __future__ import annotations

import hashlib
import json
import math
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
from mcpgate.template_inference import Observation, infer_template, perturb_arguments  # noqa: E402

PLAN = ROOT / "artifact" / "adaptive-templates-plan.json"
OUT = ROOT / "artifact" / "results" / "adaptive_templates.json"
COVERT_DIGITS = "141592653589793"
COVERT_LETTERS = "PWNEDxEXFILxxxx"
PAYLOAD = b"ATTACKER CONTROLLED PAYLOAD"


def covert_clock(d: str) -> str:
    return f"{d[0:2]}:{d[2:4]}:{d[4:6]}.{d[6:]}Z"


def budget_ok(slack) -> bool:
    return (not math.isinf(slack.total_bits)) and slack.total_bits <= 128


def structural_ok(template) -> bool:
    """Post-hoc pin policy (from adaptive run 1): every hole in a file path or
    content must be a clock value, and no object may be a fallback pattern."""
    for obj in template.objects:
        if obj.path is None:
            return False
        for tokens in (obj.path, obj.content or ()):
            if any(t[0] == "H" and not t[1].startswith("clock:") for t in tokens):
                return False
    return True


def run_mode(pinner, args, mode, extra_env=None, tag=None):
    """Run one container with extra tamper settings in its environment."""
    pinner.count += 1
    sandbox = mf._fresh(pinner.base / f"{tag or mode}-{pinner.count:03d}")
    record = mf._run_container(pinner.docker, pinner.server, sandbox, mode=mode,
                               probe_args=tg._probe(args), extra_env=extra_env)
    return record, sandbox


def staged_text(sandbox: Path) -> dict[str, bytes]:
    return {p: c for p, (k, c) in tg._staged(sandbox).items() if k == "file" and c}


def pin_poisoned(pinner, plan_a, exemplar, fixed):
    rng = random.Random(plan_a["training"]["seed"])
    observations = []
    for _ in range(plan_a["training"]["runs"]):
        args = perturb_arguments(exemplar, rng, fixed=fixed)
        record, sandbox = run_mode(pinner, args, "noisy", tag="poison-train")
        observations.append(Observation(args, tg._staged(sandbox),
                                        observed_at=datetime.now(timezone.utc)))
    return infer_template(tg._exemplar(pinner.server["id"])[0], observations,
                          fixed={k: exemplar.get(k) for k in sorted(fixed)})


def evaluate(docker, server, plan, plan_a, base):
    pinner = tg.Pinner(docker, server, base)
    pinned = tg.pin(pinner, plan_a)
    template = pinned["template"]
    exemplar = pinned["exemplar"]
    reference = mf.derive_reference(docker, server, base / "fixed-ref")
    fixed_contract = mf.build_contract(server, reference)
    predicted = template.slack(exemplar, clock_bound=True)
    rows = []
    # honest control: the template must admit the honest exemplar call
    record, sandbox = run_mode(pinner, exemplar, "none", tag="control")
    control = tg.admit(template.instantiate(exemplar, now=datetime.now(timezone.utc)),
                       sandbox, unsafe_check=True)
    fixed_control = tg.admit(fixed_contract, sandbox, unsafe_check=True)
    print(f"    control   T={'admit' if control['allowed'] else 'REFUSE'} "
          f"F={'admit' if fixed_control['allowed'] else 'REFUSE'}", flush=True)
    attacks = {
        "covert": ("covert", {"MCPGATE_TAMPER_COVERT": COVERT_DIGITS}),
        "overslack": ("covert", {"MCPGATE_TAMPER_COVERT": COVERT_LETTERS}),
        "inject": ("inject", {"MCPGATE_TAMPER_INJECT_RE": r"\.(log|jsonl)$"}),
    }
    for name, (mode, env) in attacks.items():
        for rep in range(plan["repetitions"]):
            record, sandbox = run_mode(pinner, exemplar, mode, env, tag=name)
            files = staged_text(sandbox)
            if name == "covert":
                marker = covert_clock(COVERT_DIGITS).encode()
                hits = sum(c.count(marker) for c in files.values())
                landed = hits > 0
            elif name == "overslack":
                marker = covert_clock(COVERT_LETTERS).encode()
                hits = sum(c.count(marker) for c in files.values())
                landed = hits > 0
            else:
                hits = sum(1 for p, c in files.items()
                           if PAYLOAD in c and (p.endswith(".log") or p.endswith(".jsonl")))
                landed = hits > 0
            now = datetime.now(timezone.utc)
            t_verdict = tg.admit(template.instantiate(exemplar, now=now), sandbox,
                                 unsafe_check=True)
            f_verdict = tg.admit(fixed_contract, sandbox, unsafe_check=True)
            row = {"attack": name, "rep": rep, "landed": landed, "hits": hits,
                   "call_error": tg._last_call_error(record),
                   "template_admits": t_verdict["allowed"],
                   "template_reason": t_verdict["reason"][:300],
                   "fixed_admits": f_verdict["allowed"],
                   "fixed_reason": f_verdict["reason"][:300]}
            if name == "covert":
                row["achieved_bits"] = round(hits * 15 * math.log2(10), 3)
            rows.append(row)
            print(f"    {name:9s} r{rep} landed={landed} hits={hits} "
                  f"T={'admit' if t_verdict['allowed'] else 'REFUSE'} "
                  f"F={'admit' if f_verdict['allowed'] else 'REFUSE'}", flush=True)
    poisoned = pin_poisoned(pinner, plan_a, exemplar, set(pinned["fixed"]))
    p_slack = poisoned.slack(exemplar, clock_bound=True)
    print(f"    predicted slack {predicted.total_bits} (budget ok {budget_ok(predicted)}); "
          f"poisoned slack {p_slack.total_bits} (budget ok {budget_ok(p_slack)})", flush=True)
    return {"server_id": server["id"], "template": template.to_json(),
            "predicted_slack_bits": predicted.total_bits,
            "predicted_slack_per_rule": dict(predicted.per_rule),
            "honest_template_passes_budget": budget_ok(predicted),
            "honest_template_passes_structural": structural_ok(template),
            "poisoned_template_passes_structural": structural_ok(poisoned),
            "honest_control": {"template": control, "fixed": fixed_control},
            "poisoned_template": poisoned.to_json(),
            "poisoned_slack_bits": p_slack.total_bits,
            "poisoned_slack_per_rule": dict(p_slack.per_rule),
            "poisoned_template_passes_budget": budget_ok(p_slack),
            "fixed_contract_unconstrained_files": reference.get("unconstrained_files", []),
            "attacks": rows, "runs": pinner.log}


def main() -> int:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    plan_a = json.loads(tg.PLAN.read_text(encoding="utf-8"))
    docker = mf._docker()
    by_id = {s["id"]: s for s in json.loads(mf.MANIFEST.read_text(encoding="utf-8"))["servers"]}
    scratch = Path(os.environ["MCPGATE_SCRATCH"]).parent / "adaptive"
    result = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
              "phase": plan["phase"],
              "plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
              "inference_sha256": hashlib.sha256(
                  (ROOT / "src" / "mcpgate" / "template_inference.py").read_bytes()).hexdigest(),
              "servers": []}
    for server_id in plan["servers"]:
        print(f"=== {server_id}", flush=True)
        try:
            row = evaluate(docker, by_id[server_id], plan, plan_a,
                           scratch / server_id.replace("/", "__"))
        except Exception as error:  # noqa: BLE001
            import traceback
            row = {"server_id": server_id, "error": f"{type(error).__name__}: {error}",
                   "trace": traceback.format_exc()[-1500:]}
            print(f"    ERROR {row['error']}", flush=True)
        result["servers"].append(row)
        OUT.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

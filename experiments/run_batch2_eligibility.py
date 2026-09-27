"""Pre-effect eligibility for the second held-out batch (workstream G).

For each pinned candidate, in the frozen order: build the integrity-checked
image and run tools/list in an isolated, network-less container. No tool is
called, so no effect or security outcome is observed. Stops once enough
candidates are schema-eligible; every skip is recorded with its reason.
Reuses the build and probe of run_heldout_eligibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import run_heldout_eligibility as base

ROOT = Path(__file__).resolve().parents[1]
PINNED = ROOT / "artifact" / "held-out-batch2-pinned.json"
OUT = ROOT / "artifact" / "results" / "batch2_eligibility.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=14,
                        help="stop after this many schema-eligible servers")
    args = parser.parse_args()
    docker = base._docker_executable()
    pinned = json.loads(PINNED.read_text(encoding="utf-8"))
    result = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
              "phase": "PRE_EFFECT_ELIGIBILITY_ONLY", "effect_calls_per_candidate": 0,
              "pinned_sha256": hashlib.sha256(PINNED.read_bytes()).hexdigest(),
              "rows": []}
    eligible = 0
    for index, row in enumerate(pinned["rows"], 1):
        if eligible >= args.target:
            break
        cand = {"id": row["id"], "ecosystem": row["ecosystem"], "package": row["package"],
                "version": row.get("version", ""), "integrity": row.get("integrity", ""),
                "binary": row.get("binary", "")}
        out = {"order": index, "candidate": cand}
        print(f"[{index}] {cand['id']}", flush=True)
        try:
            if row.get("status") != "PINNED":
                raise ValueError(f"not pinned: {row.get('error')}")
            base._validate(cand)
            image = base._image_tag(cand)
            built, build = base._build(docker, cand, image, timeout=420)
            out.update({"image_tag": image, "build": build})
            if built:
                out["image_id"] = base._inspect_image(docker, image)
                out["probe"] = base._probe(docker, cand, image)
        except BaseException as error:  # noqa: BLE001
            out["host_error"] = f"{type(error).__name__}: {error}"
        status = out.get("probe", {}).get("status", "NOT_RUN")
        out["eligible"] = status == "TOOLS_LIST_OK"
        eligible += out["eligible"]
        result["rows"].append(out)
        OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"    build={out.get('build', {}).get('status')} probe={status} "
              f"eligible_so_far={eligible}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

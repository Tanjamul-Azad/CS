"""Workstream C: does confinement turn trusted-state admission into
filesystem world-effect prevention?

EffectSeal's admission check governs what enters trusted state. A server that
also writes OUTSIDE its staging root is not stopped by that check, and the
integrated run recorded exactly such a write. This experiment makes the outer
boundary part of the design and measures it.

The adversary (tamper mode "escape") performs the honest write inside staging
and ALSO copies the honest bytes to paths outside it, silently swallowing any
error so the call still succeeds. Targets:

  /world/escape.dat   a host directory standing in for the user's own files,
                      which an ordinary stdio MCP server running as the user
                      can write
  /tmp/escape.dat     container-local scratch
  /etc/escape.dat     container system path
  /app/escape.dat     container application path

Conditions (execution otherwise identical):

  UNCONFINED  writable container root, /world bind-mounted read-write:
              the common deployment where the server has the user's authority
  CONFINED    EffectSeal's boundary: read-only root, no network, the per-call
              staging root as the ONLY writable mount, /world not mounted

Oracles: the host checks the /world directory after exit; the in-container
probe reports whether each container path exists after the server has exited.
Staged state is admitted with the fixed-call tree contract, so the row also
shows that admission alone accepts an honest-looking staged result while the
escape landed elsewhere.

Honest completion under CONFINED measures the utility cost of the boundary.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

import run_matched_filesystem as mf  # noqa: E402

OUT = ROOT / "artifact" / "results" / "confinement.json"
TARGETS = ["/world/escape.dat", "/tmp/escape.dat", "/etc/escape.dat", "/app/escape.dat"]
REPS = 3


def run_container(docker: str, server: dict, sandbox: Path, world: Path, *,
                  mode: str, confined: bool) -> dict:
    (sandbox / "home").mkdir(exist_ok=True)
    image = server.get("evaluation_image_id", server["image_tag"])
    env = ["-e", f"MCPGATE_TAMPER={mode}", "-e", "MCPGATE_TAMPER_TIER=consistent",
           "-e", "MCPGATE_TAMPER_ROOT=/sandbox",
           "-e", "MCPGATE_TAMPER_ESCAPE=" + ",".join(TARGETS)]
    mounts = ["--mount", f"type=bind,src={sandbox},dst=/sandbox",
              "--mount", f"type=bind,src={mf.PROBE},dst=/app/matched_probe.py,readonly"]
    if mf._is_node(server):
        env += ["-e", "NODE_OPTIONS=--require /app/impl_tamper.cjs"]
        mounts += ["--mount", f"type=bind,src={mf.NODE_SHIM},dst=/app/impl_tamper.cjs,readonly"]
    else:
        env += ["-e", "PYTHONPATH=/app/tamper:/app/src"]
        mounts += ["--mount", f"type=bind,src={mf.PY_SHIM_DIR},dst=/app/tamper,readonly"]
    if confined:
        boundary = ["--read-only", "--network=none", "--cap-drop=ALL",
                    "--security-opt=no-new-privileges", "--pids-limit=256"]
    else:
        boundary = ["--network=none"]  # network stays out of scope in both
        mounts += ["--mount", f"type=bind,src={world},dst=/world"]
    cmd = [docker, "run", "--rm", "--memory=512m", "--cpus=1", *boundary, *env,
           *mounts, "--entrypoint", "python3", image, "/app/matched_probe.py",
           "--server-id", server["id"], "--command", server["launch_command"],
           "--marker", mf.MARKER, "--content", mf.CONTENT,
           "--check-paths", ",".join(t for t in TARGETS if not t.startswith("/world"))]
    started = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180,
                          env=mf.heldout._docker_environment(), check=False)
    record = {"exit_code": proc.returncode,
              "latency_ms": round((time.perf_counter() - started) * 1000, 3),
              "stderr_tail": proc.stderr[-800:]}
    try:
        record["driver"] = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        record["driver"] = {"status": "NO_JSON", "stdout_tail": proc.stdout[-800:]}
    return record


def main() -> int:
    docker = mf._docker()
    manifest = json.loads(mf.MANIFEST.read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in manifest["servers"]}
    import os
    scratch = Path(os.environ["MCPGATE_SCRATCH"]).parent / "confinement"
    result = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
              "phase": "WORKSTREAM_C_CONFINEMENT", "targets": TARGETS, "reps": REPS,
              "node_shim_sha256": hashlib.sha256(mf.NODE_SHIM.read_bytes()).hexdigest(),
              "py_shim_sha256": hashlib.sha256(
                  (mf.PY_SHIM_DIR / "sitecustomize.py").read_bytes()).hexdigest(),
              "rows": []}
    counter = 0
    for server_id in mf.FILESYSTEM_SERVERS:
        server = by_id[server_id]
        base = scratch / server_id.replace("/", "__")
        reference = mf.derive_reference(docker, server, base / "ref")
        contract = mf.build_contract(server, reference)
        for confined in (False, True):
            for mode in ("none", "escape"):
                for rep in range(REPS):
                    counter += 1
                    sandbox = mf._fresh(base / f"{counter:03d}")
                    world = mf._fresh(base / f"world-{counter:03d}")
                    record = run_container(docker, server, sandbox, world,
                                           mode=mode, confined=confined)
                    driver = record["driver"]
                    calls = driver.get("calls") or []
                    call_error = (driver.get("status") != "DRIVER_OK"
                                  or (bool(calls) and calls[-1]["is_error"]))
                    inside = driver.get("post_exists") or {}
                    landed = {"/world/escape.dat": (world / "escape.dat").exists(),
                              **{p: bool(inside.get(p)) for p in TARGETS[1:]}}
                    _, admission = mf.admit_mcpgate(sandbox, contract)
                    row = {"server_id": server_id, "confined": confined, "mode": mode,
                           "rep": rep, "call_error": call_error,
                           "driver_status": driver.get("status"),
                           "honest_completion": (not call_error) and admission["allowed"],
                           "admitted": admission["allowed"],
                           "escape_landed": landed,
                           "world_effect": any(landed.values()),
                           "latency_ms": record["latency_ms"]}
                    result["rows"].append(row)
                    print(f"{server_id.split('/')[-1]:24s} "
                          f"{'CONF' if confined else 'OPEN'} {mode:6s} r{rep} "
                          f"err={call_error} admitted={admission['allowed']} "
                          f"world={[p for p, v in landed.items() if v]}", flush=True)
                    shutil.rmtree(world, ignore_errors=True)
        OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    rows = result["rows"]

    def rate(pred, sel):
        chosen = [r for r in rows if sel(r)]
        return {"n": len(chosen), "k": sum(pred(r) for r in chosen)}

    result["summary"] = {
        "escape_world_effect_unconfined": rate(lambda r: r["world_effect"],
                                               lambda r: r["mode"] == "escape" and not r["confined"]),
        "escape_world_effect_confined": rate(lambda r: r["world_effect"],
                                             lambda r: r["mode"] == "escape" and r["confined"]),
        "escape_admitted_unconfined": rate(lambda r: r["admitted"],
                                           lambda r: r["mode"] == "escape" and not r["confined"]),
        "honest_completion_unconfined": rate(lambda r: r["honest_completion"],
                                             lambda r: r["mode"] == "none" and not r["confined"]),
        "honest_completion_confined": rate(lambda r: r["honest_completion"],
                                           lambda r: r["mode"] == "none" and r["confined"]),
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

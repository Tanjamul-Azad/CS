"""Matched five-condition security evaluation for the filesystem-class servers.

For each frozen server this runner first derives an honest reference by running
the approved workflow several times with no interposition and recording which
changed paths are byte-stable and which are volatile. That reference defines
both the honest oracle and the MCPGate tree contract, so the contract is not
hand-written per server.

Each applicable (scenario, condition) cell is then run. Attacks are realized by
the interposition shims; the request the server receives stays honest. The
trusted-state snapshot is taken host-side, after the container and every
descendant have exited, and every outcome field is decided from that snapshot
rather than from the server response.

Conditions differ only in policy, execution held constant:

  NONE           write straight into trusted state, no policy
  PLAIN_SANDBOX  same, under the hardened container (blast radius only)
  MBA            same, with the response auditor running its default policy
  STATIC_LP      admit from a private copy, but bind destination paths only
  MCPGATE        admit from a private copy under the full tree contract

This is a security experiment on untrusted code. Every server runs with
--network=none, dropped capabilities, no-new-privileges, a read-only image,
a pids limit, and only a disposable bind mount; no host path or credential is
exposed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

import run_heldout_eligibility as heldout  # noqa: E402
from mcpgate import (ContentPredicate, EffectContract, PathRule,  # noqa: E402
                     TreeEffectContract, TreeSnapshot, snapshot_tree)

MANIFEST = ROOT / "artifact" / "held-out-manifest.json"
PLAN = ROOT / "artifact" / "held-out-evaluation-plan.json"
PROBE = ROOT / "docker" / "matched_probe.py"
NODE_SHIM = ROOT / "docker" / "impl_tamper.cjs"
PY_SHIM_DIR = ROOT / "docker" / "tamper_site"
OUT = ROOT / "artifact" / "results" / "matched_filesystem.json"
SCRATCH = Path(os.environ.get(
    "MCPGATE_SCRATCH",
    r"C:\Users\User\AppData\Local\Temp\claude"
    r"\F--UIU-12th-CS-Paper-work\b3e2e253-e9d8-4d48-9234-b2d90545045e"
    r"\scratchpad\matched"))

MARKER = "MCPGATE_MATCHED_2026_09_26"
# No trailing newline and no markdown-special characters: some servers embed the
# value in a structured document and reject content that breaks their roundtrip.
CONTENT = f"approved matched content {MARKER}"
CONDITIONS = ["NONE", "PLAIN_SANDBOX", "MBA", "STATIC_LP", "MCPGATE"]
HONEST_REFERENCE_RUNS = 3

# Filesystem-class servers whose audited effect lands cleanly under /sandbox
# (not under $HOME) and is realized by plain file writes the shims cover.
# crbro-memory and aide-memory write their store under $HOME and aide keeps an
# internal SQLite database, so they are out of this filesystem set and are
# handled honestly elsewhere rather than forced into this oracle.
FILESYSTEM_SERVERS = [
    "io.github.Oncorporation/filesystem-server",
    "io.github.bytedance/mcp-server-filesystem",
    "io.github.aayoawoyemi/ori-memory",
    "ai.smartmemory/compose-mcp",
    "io.github.DanielGuru/repomemory",
]

# Recorded exclusions from the destination-integrity filesystem set, with cause.
EXCLUSIONS = {
    "io.github.mrfentmen/document-generator-mcp":
        "writes to a fixed /tmp/evidence.docx regardless of the requested "
        "filename, so the output destination is not client-selectable and "
        "destination binding does not apply",
    "io.github.Octonove/crbro-memory":
        "stores its data under $HOME rather than a client-supplied path",
    "io.github.aide-memory/aide-memory":
        "keeps an internal SQLite database under $HOME; covered by the SQL arm",
}

SCENARIO_MODE = {
    "H0": "none", "A1": "path", "A2": "content",
    "A4": "extra", "A6": "noop", "A7": "symlink",
}
REQUEST_SCENARIOS = {"A3", "A5"}  # realized at the request, not by interposition


def _docker() -> str:
    docker = heldout._docker_executable()
    if docker is None:
        raise RuntimeError("Docker is unavailable")
    return docker


def _is_node(server: dict) -> bool:
    return server["ecosystem"] == "npm"


def _fresh(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    return path


def _run_container(docker: str, server: dict, sandbox: Path, *, mode: str,
                   extra_field: str | None = None, replay: int = 1,
                   hardened: bool = True, audit: bool = False,
                   tier: str = "consistent") -> dict:
    """Run one server workload in a disposable container against `sandbox`."""
    (sandbox / "home").mkdir(exist_ok=True)
    image = server.get("evaluation_image_id", server["image_tag"])
    env_flags: list[str] = [
        "-e", f"MCPGATE_TAMPER={mode}",
        "-e", f"MCPGATE_TAMPER_TIER={tier}",
        "-e", "MCPGATE_TAMPER_ROOT=/sandbox",
    ]
    mounts = [
        "--mount", f"type=bind,src={sandbox},dst=/sandbox",
        "--mount", f"type=bind,src={PROBE},dst=/app/matched_probe.py,readonly",
    ]
    if _is_node(server):
        env_flags += ["-e", "NODE_OPTIONS=--require /app/impl_tamper.cjs"]
        mounts += ["--mount",
                   f"type=bind,src={NODE_SHIM},dst=/app/impl_tamper.cjs,readonly"]
    else:
        env_flags += ["-e", "PYTHONPATH=/app/tamper:/app/src"]
        mounts += ["--mount",
                   f"type=bind,src={PY_SHIM_DIR},dst=/app/tamper,readonly"]
    hardening = ["--cap-drop=ALL", "--security-opt=no-new-privileges",
                 "--pids-limit=256"] if hardened else []
    run = [docker, "run", "--rm", "--network=none", "--read-only",
           "--memory=512m", "--cpus=1", *hardening, *env_flags, *mounts,
           "--entrypoint", "python3", image, "/app/matched_probe.py",
           "--server-id", server["id"], "--command", server["launch_command"],
           "--marker", MARKER, "--content", CONTENT, "--replay", str(replay)]
    if extra_field:
        run += ["--extra-field", extra_field]
    if audit:
        run += ["--audit"]
    started = time.perf_counter()
    proc = subprocess.run(run, capture_output=True, text=True, timeout=180,
                          env=heldout._docker_environment(), check=False)
    elapsed = time.perf_counter() - started
    record: dict[str, Any] = {
        "exit_code": proc.returncode,
        "latency_ms": round(elapsed * 1000, 3),
        "stderr_tail": proc.stderr[-1500:],
    }
    try:
        record["driver"] = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        record["driver"] = {"status": "NO_JSON", "stdout_tail": proc.stdout[-1500:]}
    return record


def _walk(sandbox: Path) -> dict[str, dict[str, Any]]:
    """Reparse-point-safe recursive snapshot of the audited /sandbox area.

    A symlink the server created inside the Linux container appears to the
    Windows host as a reparse point that ordinary stat calls cannot follow, so
    every entry is classified from os.lstat and unreadable reparse points are
    treated as unsafe link types rather than skipped.
    """
    import stat as stat_mod
    out: dict[str, dict[str, Any]] = {}

    def visit(directory: Path, prefix: str) -> None:
        try:
            children = sorted(os.scandir(directory), key=lambda e: e.name)
        except OSError:
            return
        for child in children:
            rel = f"{prefix}/{child.name}" if prefix else child.name
            try:
                info = os.lstat(child.path)
            except OSError:
                out[rel] = {"kind": "symlink", "target": "<unreadable-reparse>"}
                continue
            mode = info.st_mode
            if stat_mod.S_ISLNK(mode):
                try:
                    target = os.readlink(child.path)
                except OSError:
                    target = "<unreadable-reparse>"
                out[rel] = {"kind": "symlink", "target": target}
            elif stat_mod.S_ISDIR(mode):
                out[rel] = {"kind": "directory"}
                visit(Path(child.path), rel)
            elif stat_mod.S_ISREG(mode):
                try:
                    data = Path(child.path).read_bytes()
                except OSError:
                    out[rel] = {"kind": "special"}
                    continue
                out[rel] = {
                    "kind": "hardlink" if info.st_nlink not in (0, 1) else "file",
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size": len(data),
                    "contains_marker": (MARKER.encode() in data
                                        or _docx_has_marker(data)),
                }
            else:
                out[rel] = {"kind": "special"}

    visit(sandbox, "")
    return out


def _snapshot(sandbox: Path) -> dict[str, dict[str, Any]]:
    """Audited effect only: /sandbox without the server's home directory.

    home holds package caches and per-run runtime state that are not the
    audited effect; servers whose effect legitimately lands under home are not
    in this filesystem-class set.
    """
    return {rel: entry for rel, entry in _walk(sandbox).items()
            if rel != "home" and not rel.startswith("home/")}


def _docx_has_marker(data: bytes) -> bool:
    import io
    import zipfile
    if data[:2] != b"PK":
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return any(MARKER.encode() in archive.read(name)
                       for name in archive.namelist() if name.endswith(".xml"))
    except zipfile.BadZipFile:
        return False


def derive_reference(docker: str, server: dict, base: Path) -> dict:
    """Run the honest workflow several times and classify path stability.

    Runs are spaced in time so that content carrying a per-run timestamp differs
    between runs and is correctly classified as volatile rather than byte-stable.
    Every changed file falls into one of three classes, which become the L3, L2,
    and UNKNOWN rungs of the contract:

      stable        identical bytes in every run  -> exact-content rule
      volatile      differs but carries the marker -> marker-presence rule
      unconstrained present every run but neither  -> path/type only, content
                    unverifiable (the honest UNKNOWN case)
    """
    snapshots: list[dict[str, dict[str, Any]]] = []
    runs: list[dict] = []
    for index in range(HONEST_REFERENCE_RUNS):
        if index:
            time.sleep(1.3)  # expose sub-second timestamped content as volatile
        sandbox = _fresh(base / f"ref-{index}")
        record = _run_container(docker, server, sandbox, mode="none")
        snapshots.append(_snapshot(sandbox))
        runs.append({"exit_code": record["exit_code"],
                     "driver_status": record["driver"].get("status"),
                     "latency_ms": record["latency_ms"]})
    common = set(snapshots[0])
    union = set(snapshots[0])
    for snap in snapshots[1:]:
        common &= set(snap)
        union |= set(snap)
    files = [p for p in sorted(common) if snapshots[0][p]["kind"] == "file"]
    stable, volatile, unconstrained = {}, [], []
    for path in files:
        hashes = {snap[path]["sha256"] for snap in snapshots}
        markers = all(snap[path]["contains_marker"] for snap in snapshots)
        if len(hashes) == 1:
            stable[path] = snapshots[0][path]["sha256"]
        elif markers:
            volatile.append(path)
        else:
            unconstrained.append(path)
    flaky = sorted(union - common)
    marker_paths = sorted([p for p in stable if snapshots[0][p]["contains_marker"]]
                          + volatile)
    return {
        "runs": runs,
        "all_honest_paths": sorted(common),
        "stable_files": stable,
        "volatile_files": sorted(volatile),
        "unconstrained_files": sorted(unconstrained),
        "flaky_paths": flaky,
        "marker_paths": sorted(set(marker_paths)),
        "deterministic": not flaky,
    }


def build_contract(server: dict, reference: dict) -> TreeEffectContract:
    """A tree contract derived from the honest reference (no hand tuning)."""
    rules: list[PathRule] = []
    file_paths = (set(reference["stable_files"]) | set(reference["volatile_files"])
                  | set(reference.get("unconstrained_files", [])))
    directories = set()
    for path in reference["all_honest_paths"]:
        # every honest directory, including empty leaf directories the server
        # creates, must have its own rule or the whole-tree diff refuses it
        if path not in file_paths:
            directories.add(path)
        parent = os.path.dirname(path)
        while parent:
            directories.add(parent)
            parent = os.path.dirname(parent)
    for path, digest in reference["stable_files"].items():
        rules.append(PathRule(
            name=f"stable::{path}", pattern=re.escape(path),
            content=ContentPredicate("exact_sha256", digest),
            min_matches=1, max_matches=1))
    for path in reference["volatile_files"]:
        rules.append(PathRule(
            name=f"volatile::{path}", pattern=re.escape(path),
            content=ContentPredicate("utf8_contains", MARKER),
            min_matches=1, max_matches=1))
    for path in reference.get("unconstrained_files", []):
        # Content is not verifiable for this path; bind only its destination and
        # type. This is the honest UNKNOWN rung and is reported as such.
        rules.append(PathRule(
            name=f"unconstrained::{path}", pattern=re.escape(path),
            content=ContentPredicate("any"), min_matches=1, max_matches=1))
    for directory in sorted(directories):
        rules.append(PathRule(
            name=f"dir::{directory}", pattern=re.escape(directory),
            kinds=frozenset({"directory"}),
            operations=frozenset({"create"}), min_matches=0, max_matches=1))
    empty = TreeSnapshot(entries={})
    return TreeEffectContract(
        request=EffectContract("matched_workflow", binding={"marker": MARKER}),
        expected_before=empty, rules=tuple(rules))


def _tree_snapshot_from_walk(sandbox: Path) -> TreeSnapshot:
    """Build the audited TreeSnapshot type from the reparse-safe walk.

    This feeds the same TreeEffectContract.evaluate used by the unit tests and
    the integrated run, but sources its entries from a Windows-safe walk so a
    Linux symlink dropped by an attack does not crash host-side stat calls.
    """
    from mcpgate.tree_mediator import TreeEntry
    entries: dict[str, TreeEntry] = {}
    for rel, meta in _snapshot(sandbox).items():
        kind = meta["kind"]
        if kind == "file":
            content = (sandbox / rel).read_bytes()
            entries[rel] = TreeEntry("file", size=len(content),
                                     sha256=meta["sha256"], content=content)
        else:
            entries[rel] = TreeEntry(kind if kind in {"symlink", "hardlink",
                                     "directory", "special"} else "special")
    return TreeSnapshot(entries=entries)


def admit_mcpgate(sandbox: Path, contract: TreeEffectContract) -> tuple[dict, dict]:
    """Apply the full tree contract to the private snapshot; promote iff it passes."""
    snap = _tree_snapshot_from_walk(sandbox)
    dangerous = [p for p, e in snap.entries.items()
                 if e.kind in {"symlink", "hardlink", "special"}]
    if dangerous:
        return ({}, {"allowed": False, "phase": "effect-diff",
                     "reason": f"unsafe object types: {dangerous[:8]}"})
    verdict = contract.evaluate(snap)
    if not verdict.allowed:
        return ({}, {"allowed": False, "phase": "effect-diff",
                     "reason": verdict.reason})
    return (_snapshot(sandbox), {"allowed": True, "phase": "commit",
                                 "reason": verdict.reason})


def admit_static_lp(sandbox: Path, granted: set[str]) -> tuple[dict, dict]:
    """Destination-bound admission: keep only changes at granted paths."""
    full = _snapshot(sandbox)
    admitted = {p: e for p, e in full.items()
                if p in granted or e["kind"] == "directory"}
    refused = sorted(set(full) - set(admitted))
    return (admitted, {"granted": sorted(granted), "refused_paths": refused})


def _outcome(scenario: str, trusted: dict, reference: dict) -> dict:
    """Decide the frozen outcome fields from the trusted-state snapshot."""
    stable = reference["stable_files"]
    volatile = set(reference["volatile_files"])
    unconstrained = set(reference.get("unconstrained_files", []))
    honest_known = set(reference["all_honest_paths"])
    honest_paths = set(stable) | volatile

    authorized = True
    for path, digest in stable.items():
        entry = trusted.get(path)
        if not entry or entry.get("kind") != "file" or entry.get("sha256") != digest:
            authorized = False
    for path in volatile:
        entry = trusted.get(path)
        if not entry or not entry.get("contains_marker"):
            authorized = False

    unauthorized = False
    unverified = False
    reasons: list[str] = []
    for path, entry in trusted.items():
        if entry["kind"] in {"symlink", "hardlink", "special"}:
            unauthorized = True
            reasons.append(f"unsafe:{path}")
            continue
        if entry["kind"] == "directory":
            continue
        if path in stable:
            if entry.get("sha256") != stable[path]:
                unauthorized = True
                reasons.append(f"content:{path}")
        elif path in volatile:
            if not entry.get("contains_marker"):
                unauthorized = True
                reasons.append(f"volatile-content:{path}")
        elif path in unconstrained or path in honest_known:
            # a known honest path whose content cannot be verified: not an
            # integrity violation we can assert, but not a guarantee either
            unverified = True
        else:
            unauthorized = True
            reasons.append(f"extra:{path}")

    return {
        "authorized_effect": authorized,
        "unauthorized_effect": unauthorized,
        "content_unverifiable": unverified,
        "unauthorized_reasons": reasons[:12],
        "honest_paths": sorted(honest_paths),
    }


def run_cell(docker: str, server: dict, reference: dict,
             contract: TreeEffectContract, scenario: str, condition: str,
             base: Path) -> dict:
    mode = SCENARIO_MODE.get(scenario, "none")
    extra_field = "extra_path" if scenario == "A3" else None
    replay = 2 if scenario == "A5" else 1
    hardened = condition != "NONE"
    sandbox = _fresh(base / f"{condition}-{scenario}")
    admission_uses_private = condition in {"STATIC_LP", "MCPGATE"}

    record = _run_container(docker, server, sandbox, mode=mode,
                            extra_field=extra_field, replay=replay,
                            hardened=hardened, audit=(condition == "MBA"))
    driver = record["driver"]
    boundary_closed = record["exit_code"] is not None
    protocol_error = driver.get("status") != "DRIVER_OK"

    all_alerts = driver.get("alerts", []) if condition == "MBA" else []
    violations = [a for a in all_alerts
                  if isinstance(a, dict) and a.get("severity") == "violation"]

    admission_refused = False
    if condition in {"NONE", "PLAIN_SANDBOX", "MBA"}:
        trusted = _snapshot(sandbox)
        admission = {"policy": condition, "admits_all": True}
    elif condition == "STATIC_LP":
        granted = set(reference["all_honest_paths"])
        trusted, admission = admit_static_lp(sandbox, granted)
        admission_refused = bool(admission["refused_paths"])
    else:  # MCPGATE
        trusted, admission = admit_mcpgate(sandbox, contract)
        admission_refused = not admission["allowed"]

    outcome = _outcome(scenario, trusted, reference)
    mutation_attempted = scenario != "H0"
    completion = outcome["authorized_effect"] if scenario == "H0" else None
    false_block = (scenario == "H0" and condition != "NONE"
                   and not outcome["authorized_effect"])

    unknown = False
    unknown_reason = None
    if not boundary_closed:
        unknown, unknown_reason = True, "execution closure not proven"

    # A false success is a call the client was told succeeded while no authorized
    # effect entered trusted state and no admission step surfaced the failure.
    false_success = (mutation_attempted and not protocol_error
                     and not outcome["authorized_effect"]
                     and not outcome["unauthorized_effect"]
                     and not admission_refused)

    # Per-scenario harm: an integrity attack harms when an unauthorized effect
    # lands; a no-op attack harms when its false success is not surfaced.
    if scenario == "A6":
        attack_succeeded = false_success
    else:
        attack_succeeded = outcome["unauthorized_effect"]

    prevented = mutation_attempted and not attack_succeeded
    detected_only = (mutation_attempted and attack_succeeded and bool(violations))

    return {
        "server_id": server["id"], "scenario": scenario, "condition": condition,
        "tamper_mode": mode,
        "mutation_attempted": mutation_attempted,
        "protocol_error": protocol_error,
        "authorized_effect": outcome["authorized_effect"],
        "unauthorized_effect": outcome["unauthorized_effect"],
        "content_unverifiable": outcome["content_unverifiable"],
        "unauthorized_reasons": outcome["unauthorized_reasons"],
        "completion": completion,
        "false_block": false_block,
        "false_success": false_success,
        "admission_refused": admission_refused,
        "attack_succeeded": attack_succeeded,
        "unknown": unknown,
        "unknown_reason": unknown_reason,
        "prevented": prevented,
        "detected_only": detected_only,
        "auditor_alerts": all_alerts,
        "auditor_violations": len(violations),
        "server_cpu_seconds": driver.get("server_cpu_seconds"),
        "server_peak_rss_kb": driver.get("server_peak_rss_kb"),
        "latency_ms": record["latency_ms"],
        "exit_code": record["exit_code"],
        "driver_status": driver.get("status"),
        "admission": admission,
        "stderr_tail": record["stderr_tail"][-500:] if protocol_error else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-id", action="append",
                        help="restrict to these server ids (repeatable)")
    parser.add_argument("--reference-only", action="store_true")
    args = parser.parse_args()
    docker = _docker()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    applicability = {p["id"]: set(p["applicable"]) for p in plan["server_plans"]}
    by_id = {s["id"]: s for s in manifest["servers"]}

    wanted = args.server_id or FILESYSTEM_SERVERS
    SCRATCH.mkdir(parents=True, exist_ok=True)
    result = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "MATCHED_FIVE_CONDITION_FILESYSTEM_SECURITY_OUTCOMES",
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
        "node_shim_sha256": hashlib.sha256(NODE_SHIM.read_bytes()).hexdigest(),
        "py_shim_sha256": hashlib.sha256(
            (PY_SHIM_DIR / "sitecustomize.py").read_bytes()).hexdigest(),
        "docker_server_version": heldout._run(
            [docker, "version", "--format", "{{.Server.Version}}"], timeout=30
        ).stdout.strip(),
        "conditions": CONDITIONS,
        "scenario_mode": SCENARIO_MODE,
        "adversary_tier": "consistent",
        "adversary_tier_note": ("attacks mask the server's own reads and directory "
            "listings so a response-level auditor sees a simulated honest world; "
            "the out-of-band host snapshot is unaffected"),
        "excluded_servers": EXCLUSIONS,
        "servers": [],
    }
    for server_id in wanted:
        server = by_id[server_id]
        base = SCRATCH / server_id.replace("/", "__")
        print(f"=== {server_id}: honest reference", flush=True)
        reference = derive_reference(docker, server, base)
        print(f"    stable={len(reference['stable_files'])} "
              f"volatile={len(reference['volatile_files'])} "
              f"unconstrained={len(reference['unconstrained_files'])} "
              f"flaky={len(reference['flaky_paths'])} "
              f"deterministic={reference['deterministic']}", flush=True)
        server_row = {"server_id": server_id, "package": server["package"],
                      "version": server["version"], "reference": reference,
                      "cells": []}
        if not args.reference_only and (reference["stable_files"]
                                        or reference["volatile_files"]):
            contract = build_contract(server, reference)
            server_row["contract_id"] = contract.contract_id
            scenarios = [s for s in SCENARIO_MODE if s in applicability[server_id]]
            scenarios += [s for s in ("A3", "A5") if s in applicability[server_id]]
            for scenario in scenarios:
                for condition in CONDITIONS:
                    cell = run_cell(docker, server, reference, contract,
                                    scenario, condition, base)
                    server_row["cells"].append(cell)
                    if cell["scenario"] == "H0":
                        flag = "OK" if cell["authorized_effect"] else "FALSE-BLOCK"
                    elif cell["prevented"]:
                        flag = "PREV"
                    elif cell["attack_succeeded"]:
                        flag = "LAND" + ("+alert" if cell["detected_only"] else "")
                    else:
                        flag = "?"
                    print(f"    {scenario:3s} {condition:13s} {flag}", flush=True)
        result["servers"].append(server_row)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"written {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

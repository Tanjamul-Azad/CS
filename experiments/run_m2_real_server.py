"""
The capstone integration: the M2-proper mediator, combined with a real,
unmodified, third-party MCP server for the first time.

    python experiments/run_m2_real_server.py

See experiments/boundary/probe_m2_real_server.py for the full design and
why this wasn't done until now (LiveSession has no built-in privilege-
drop; fixed by wrapping the launch command in `su sandbox`, verified live
before being relied on).
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "m2_real_server.json"
ARTIFACT_OUT = ROOT / "artifact" / "results" / "integrated_real_server.json"
LOCK = ROOT / "artifact" / "server-lock.json"
DOCKER_ENV = {**os.environ, "MSYS_NO_PATHCONV": "1", "MSYS2_ARG_CONV_EXCL": "*"}


def _command_output(command: list[str]) -> str | None:
    try:
        proc = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, check=False,
            encoding="utf-8", errors="replace", env=DOCKER_ENV,
        )
    except OSError:
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _load_server_lock() -> tuple[str, str]:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    entry = lock.get("filesystem_mcp", {})
    version = entry.get("version")
    if not isinstance(version, str) or not re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?", version
    ):
        raise RuntimeError(
            "artifact/server-lock.json must contain an exact filesystem-mcp "
            "version before the integrated run. Resolve and record it on the "
            "isolated artifact host; tags such as latest are forbidden."
        )
    integrity = entry.get("integrity")
    if not isinstance(integrity, str) or not re.fullmatch(
        r"sha512-[0-9A-Za-z+/=]+", integrity
    ):
        raise RuntimeError(
            "artifact/server-lock.json must contain the npm sha512 integrity "
            "for the exact filesystem-mcp release"
        )
    return version, integrity


def _build_image(version: str, integrity: str) -> tuple[str, str]:
    revision = _command_output(["git", "rev-parse", "--short=12", "HEAD"])
    revision = revision or "unknown"
    safe_version = re.sub(r"[^0-9A-Za-z_.-]", "-", version)
    image = f"mcpgate-m2:{revision}-filesystem-mcp-{safe_version}"
    command = [
        "docker", "build", "--pull", "--file", "docker/Dockerfile",
        "--build-arg", f"M2_FILESYSTEM_MCP_VERSION={version}",
        "--build-arg", f"M2_FILESYSTEM_MCP_INTEGRITY={integrity}",
        "--tag", image, ".",
    ]
    proc = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, timeout=900,
        env=DOCKER_ENV, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Docker build failed:\n{proc.stderr[-4000:]}")
    image_id = _command_output(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"]
    )
    if not image_id:
        raise RuntimeError("built image could not be inspected")
    return image, image_id


def run() -> list[dict]:
    if shutil.which("docker") is None:
        raise RuntimeError(
            "Docker is required for the real-server isolation probe. "
            "Run this command on the pinned Linux/Docker artifact host; "
            "do not execute the third-party server directly on the host."
        )
    version, integrity = _load_server_lock()
    image, image_id = _build_image(version, integrity)
    cmd = ["docker", "run", "--rm", "--user", "0:0",
           "--memory=512m", "--cpus=1", "--pids-limit=256",
           "--security-opt=no-new-privileges",
           "--cap-drop=ALL", "--cap-add=CHOWN", "--cap-add=DAC_OVERRIDE",
           "--cap-add=FOWNER", "--cap-add=KILL", "--cap-add=SETGID",
           "--cap-add=SETUID", "--network=none", "--read-only",
           "--tmpfs", "/staging_real:rw,noexec,nosuid,size=64m",
           "--tmpfs", "/committed_real:rw,noexec,nosuid,size=64m",
           "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
           "--tmpfs", "/home/sandbox:rw,noexec,nosuid,size=32m",
           "--entrypoint", "python3", image,
           "/app/boundary/probe_m2_real_server.py"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                          env=DOCKER_ENV)
    if proc.returncode != 0:
        print("probe failed inside the container:\n", proc.stderr[-3000:])
        sys.exit(1)
    rows = json.loads(proc.stdout)
    if not isinstance(rows, list):
        raise RuntimeError("probe output is not a JSON row list")
    git_status = _command_output(["git", "status", "--porcelain"])
    metadata = {
        "git_commit": _command_output(["git", "rev-parse", "HEAD"]),
        "git_dirty": None if git_status is None else bool(git_status),
        "host_platform": platform.platform(),
        "python": sys.version,
        "docker_version": _command_output(["docker", "version", "--format",
                                           "{{.Server.Version}}"]),
        "container_kernel": _command_output([
            "docker", "run", "--rm", "--network=none", "--entrypoint",
            "uname", image, "-a",
        ]),
        "image_tag": image,
        "image_id": image_id,
        "server_package": "filesystem-mcp",
        "server_version": version,
        "server_integrity": integrity,
        "runtime_network": "none",
        "container_read_only": True,
        "command": cmd,
    }
    for row in rows:
        row["run_metadata"] = metadata
    return rows


def report(rows: list[dict]) -> None:
    print("=" * 96)
    print("M2 + REAL SERVER -- the mediator confining domdomegg/filesystem-mcp for real")
    print("=" * 96)
    for r in rows:
        print(f"\n  {r['scenario']}:")
        print(f"    landed(proxy)={r['attack_landed_per_proxy']}  "
              f"diverted_field={r['diverted_field']}")
        print(f"    trusted_store={r['verdicts']['trusted_store_admission']}  "
              f"escape_path_untouched={r['verdicts']['observed_escape_path_untouched']}  "
              f"decision={r['decision']}  phase={r['decision_phase']}")
        print(f"    ledger={r['ledger_state']}  "
              f"pipeline_stages={len(r['full_pipeline'])}")
        print(f"    staged_content={str(r['staged_content'])[:40]!r}")
        print(f"    escape_content={str(r['escape_content'])[:40]!r}")
        print(f"    committed_content={str(r['committed_content'])[:40]!r}")
        if r["unauthorized_effects"]:
            print(f"    UNAUTHORIZED: {r['unauthorized_effects']}")
        if r["server_error"]:
            print(f"    error: {r['server_error'][:150]}")
        if r["mediation_error"]:
            print(f"    mediation: {r['mediation_error'][:150]}")

    print("\n" + "=" * 96)
    escape_ever_written = any(r["escape_content"] is not None for r in rows)
    if escape_ever_written:
        print("  The real server's diverted write reached /tmp/exfil.dat FOR REAL (confirmed,")
        print("  not inferred) -- but it never reached the COMMITTED store: the mediator's")
        print("  escape-path check refused the transaction. Detection at the contract layer,")
        print("  same limitation as docs/29: the real external write to /tmp already happened")
        print("  and is not undone by this mechanism -- only kept out of what's trusted.")


def _acceptance_issues(rows: list[dict]) -> list[str]:
    """Fail closed when the capstone did not exercise an honest server.

    A JSON file is still preserved for diagnosis, but a launch/handshake failure
    must never look like a successful artifact command merely because attacks
    also failed to commit.
    """

    issues: list[str] = []
    by_name = {row.get("scenario"): row for row in rows}
    expected = {"honest", "path_diversion", "content_substitution"}
    if set(by_name) != expected:
        issues.append(
            f"expected scenarios {sorted(expected)}, observed {sorted(str(k) for k in by_name)}"
        )
        return issues

    honest = by_name["honest"]
    if honest.get("server_error"):
        issues.append(f"honest server failed: {honest['server_error']}")
    if honest.get("decision") != "committed":
        issues.append(f"honest decision was {honest.get('decision')!r}, not committed")
    if honest.get("ledger_state") != "COMMITTED":
        issues.append("honest allowance did not finish COMMITTED")
    if honest.get("verdicts", {}).get("trusted_store_admission") != "PASS":
        issues.append("honest trusted-store admission failed")

    for name in ("path_diversion", "content_substitution"):
        row = by_name[name]
        if row.get("server_error"):
            issues.append(f"{name} server failed before a meaningful attack: {row['server_error']}")
        if row.get("decision") != "refused":
            issues.append(f"{name} decision was {row.get('decision')!r}, not refused")
        if row.get("ledger_state") != "FAILED":
            issues.append(f"{name} allowance did not finish FAILED")
        if row.get("verdicts", {}).get("trusted_store_admission") != "PASS":
            issues.append(f"{name} trusted-store admission check failed")
    return issues


def main() -> None:
    try:
        rows = run()
    except RuntimeError as error:
        print(f"cannot run M2 real-server probe: {error}", file=sys.stderr)
        raise SystemExit(2) from error
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(rows, indent=1) + "\n"
    OUT.write_text(payload, encoding="utf-8")
    ARTIFACT_OUT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_OUT.write_text(payload, encoding="utf-8")
    report(rows)
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    print(f"wrote {ARTIFACT_OUT.relative_to(ROOT)}")
    issues = _acceptance_issues(rows)
    if issues:
        print("\nINTEGRATED RUN FAILED ACCEPTANCE:", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        raise SystemExit(1)
    print("integrated acceptance: PASS")


if __name__ == "__main__":
    main()

"""Run the pre-effect eligibility pass for frozen held-out candidates.

This command verifies exact package integrity at image build time and then
allows only MCP initialization plus ``tools/list`` with runtime networking
disabled.  It deliberately does not call a tool or read any defense outcome.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "artifact" / "held-out-candidates.json"
OUT = ROOT / "artifact" / "results" / "heldout_eligibility.json"
DOCKERFILE = ROOT / "docker" / "Dockerfile.heldout"
SAFE_PACKAGE = re.compile(r"^(?:@[a-z0-9_.-]+/)?[a-zA-Z0-9_.-]+$")
SAFE_BINARY = re.compile(r"^[a-zA-Z0-9_.-]+$")
SAFE_ARG = re.compile(r"^(?:--?[a-zA-Z0-9_.-]+|/[a-zA-Z0-9_./-]+|[a-zA-Z0-9_.-]+)$")
EXACT_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")


def _docker_executable() -> str | None:
    discovered = shutil.which("docker")
    if discovered:
        return discovered
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            desktop_cli = (
                Path(local_app_data) / "Programs" / "DockerDesktop" /
                "resources" / "bin" / "docker.exe"
            )
            # Some managed Windows environments allow executing Docker Desktop's
            # CLI but deny a preliminary stat() of its per-user install path.
            # Return the conventional path and let subprocess report a precise
            # launch error if Docker Desktop is not installed there.
            return str(desktop_cli)
    return None


def _docker_environment() -> dict[str, str]:
    return {**os.environ, "MSYS_NO_PATHCONV": "1", "MSYS2_ARG_CONV_EXCL": "*"}


def _validate(candidate: dict) -> None:
    if candidate.get("ecosystem") not in {"npm", "pypi"}:
        raise ValueError("ecosystem must be npm or pypi")
    if not SAFE_PACKAGE.fullmatch(str(candidate.get("package", ""))):
        raise ValueError("unsafe package identifier")
    if not SAFE_BINARY.fullmatch(str(candidate.get("binary", ""))):
        raise ValueError("unsafe binary identifier")
    args = candidate.get("eligibility_args", [])
    if not isinstance(args, list) or not all(
        isinstance(arg, str) and SAFE_ARG.fullmatch(arg) for arg in args
    ):
        raise ValueError("unsafe eligibility argument")
    if not EXACT_VERSION.fullmatch(str(candidate.get("version", ""))):
        raise ValueError("version is not exact")
    if not EXACT_VERSION.fullmatch(str(candidate.get("probe_mcp_version", "2.1.1"))):
        raise ValueError("probe MCP version is not exact")
    if not isinstance(candidate.get("pypi_install_dependencies", True), bool):
        raise ValueError("pypi_install_dependencies must be boolean")
    integrity = str(candidate.get("integrity", ""))
    if not re.fullmatch(r"(?:sha512-[0-9A-Za-z+/=]+|sha256:[0-9a-f]{64})", integrity):
        raise ValueError("invalid package integrity")


def _image_tag(candidate: dict) -> str:
    identity = "\0".join([
        *(str(candidate[key]) for key in ("id", "package", "version", "integrity")),
        str(candidate["binary"]),
        json.dumps(candidate.get("eligibility_args", []), separators=(",", ":")),
        str(candidate.get("probe_mcp_version", "2.1.1")),
        str(candidate.get("pypi_install_dependencies", True)).lower(),
    ])
    return "mcpgate-heldout:" + hashlib.sha256(identity.encode()).hexdigest()[:16]


def _run(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    creationflags = (
        subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    )
    process = subprocess.Popen(
        command, cwd=ROOT, env=_docker_environment(),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", creationflags=creationflags,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True, check=False, timeout=30,
            )
        else:
            process.kill()
        try:
            stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
        raise subprocess.TimeoutExpired(
            command, timeout, output=stdout, stderr=stderr
        ) from error
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _inspect_image(docker: str, image: str) -> str | None:
    result = _run(
        [docker, "image", "inspect", image, "--format", "{{.Id}}"],
        timeout=30,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _build(docker: str, candidate: dict, image: str, *, timeout: int = 180) -> tuple[bool, dict]:
    started = time.perf_counter()
    command = [
        docker, "build", "--file", str(DOCKERFILE.relative_to(ROOT)),
        "--build-arg", f"HELDOUT_ECOSYSTEM={candidate['ecosystem']}",
        "--build-arg", f"HELDOUT_PACKAGE={candidate['package']}",
        "--build-arg", f"HELDOUT_VERSION={candidate['version']}",
        "--build-arg", f"HELDOUT_INTEGRITY={candidate['integrity']}",
        "--build-arg", f"HELDOUT_MCP_VERSION={candidate.get('probe_mcp_version', '2.1.1')}",
        "--build-arg", f"HELDOUT_PYPI_DEPS={str(candidate.get('pypi_install_dependencies', True)).lower()}",
        "--tag", image, ".",
    ]
    try:
        result = _run(command, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        return False, {
            "status": "BUILD_TIMEOUT", "elapsed_seconds": round(time.perf_counter() - started, 6),
            "stderr_tail": str(error)[-2000:],
        }
    return result.returncode == 0, {
        "status": "BUILD_OK" if result.returncode == 0 else "BUILD_FAILED",
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-4000:],
    }


def _probe(docker: str, candidate: dict, image: str) -> dict:
    name = "mcpgate-heldout-" + uuid.uuid4().hex[:12]
    server_argv = [candidate["binary"], *candidate.get("eligibility_args", [])]
    server_command = shlex.join(server_argv)
    command = [
        docker, "run", "--rm", "--name", name,
        "--network=none", "--read-only", "--memory=512m", "--cpus=1",
        "--pids-limit=256", "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--tmpfs", "/sandbox:rw,noexec,nosuid,size=64m,uid=10001,gid=10001,mode=0700",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m,uid=10001,gid=10001,mode=0700",
        "--tmpfs", "/home/sandbox:rw,noexec,nosuid,size=32m,uid=10001,gid=10001,mode=0700",
        image, "--server-id", candidate["id"], "--command", server_command,
    ]
    try:
        result = _run(command, timeout=90)
    except subprocess.TimeoutExpired:
        _run([docker, "kill", name], timeout=30)
        return {"status": "PROBE_TIMEOUT", "command": command}
    try:
        payload = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        payload = {
            "status": "INVALID_PROBE_OUTPUT",
            "stdout_tail": result.stdout[-2000:],
        }
    payload["container_exit_code"] = result.returncode
    payload["container_stderr_tail"] = result.stderr[-4000:]
    payload["runtime_command"] = command
    return payload


def _write_result(result: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run(include_reserves: bool = True, *, build_timeout: int = 180,
        resume: bool = False) -> dict:
    docker = _docker_executable()
    if docker is None:
        raise RuntimeError("Docker is unavailable")
    inventory = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    candidates = list(inventory["primary"])
    if include_reserves:
        candidates.extend(inventory.get("reserves", []))
    selection_hash = hashlib.sha256(CANDIDATES.read_bytes()).hexdigest()
    if resume and OUT.is_file():
        result = json.loads(OUT.read_text(encoding="utf-8"))
        if result.get("selection_file_sha256") != selection_hash:
            raise RuntimeError("cannot resume: candidate selection file changed")
        if result.get("phase") != "PRE_EFFECT_ELIGIBILITY_ONLY":
            raise RuntimeError("cannot resume: output is not an eligibility pass")
        result["resumed_utc"] = datetime.now(timezone.utc).isoformat()
    else:
        result = {
            "schema_version": 1,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "selection_file_sha256": selection_hash,
            "phase": "PRE_EFFECT_ELIGIBILITY_ONLY",
            "effect_calls_per_candidate": 0,
            "npm_install_scripts": "disabled",
            "rows": [],
        }
    rows: list[dict] = result["rows"]
    completed_ids = {row.get("candidate", {}).get("id") for row in rows}
    _write_result(result)
    for index, candidate in enumerate(candidates, start=1):
        if candidate["id"] in completed_ids:
            print(f"[{index}/{len(candidates)}] {candidate['id']} (checkpoint)", flush=True)
            continue
        print(f"[{index}/{len(candidates)}] {candidate['id']}", flush=True)
        row = {"candidate": candidate}
        try:
            _validate(candidate)
            image = _image_tag(candidate)
            built, build = _build(docker, candidate, image, timeout=build_timeout)
            row.update({"image_tag": image, "build": build})
            if built:
                row["image_id"] = _inspect_image(docker, image)
                row["probe"] = _probe(docker, candidate, image)
        except BaseException as error:
            row["host_error"] = f"{type(error).__name__}: {error}"
        rows.append(row)
        _write_result(result)
        probe_status = row.get("probe", {}).get("status", "NOT_RUN")
        print(f"  build={row.get('build', {}).get('status')} probe={probe_status}", flush=True)

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary-only", action="store_true")
    parser.add_argument("--build-timeout", type=int, default=180)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    result = run(
        include_reserves=not args.primary_only,
        build_timeout=args.build_timeout,
        resume=args.resume,
    )
    successful = sum(
        row.get("probe", {}).get("status") == "TOOLS_LIST_OK" for row in result["rows"]
    )
    print(f"eligibility tools/list: {successful}/{len(result['rows'])}")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0 if successful >= 10 else 1


if __name__ == "__main__":
    raise SystemExit(main())

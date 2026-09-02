"""
Phase 1, the actual scale run: audit every runnable-standalone server from
the triage inside a locked-down container.

This is the direct answer to docs/19 R1 ("everything you evaluate on, you
wrote"). Each server here is a real, unvetted third-party package found by
GitHub search -- not one of ours -- launched via the exact command a real
user would run (npx/uvx), and driven by the same declaration-driven
tampering proxy already validated against the official filesystem server.

SAFETY. This installs and executes untrusted code. Every container runs:
  --rm                         ephemeral, nothing persists
  --memory / --cpus            resource caps
  --pids-limit                 fork-bomb guard
  --cap-drop=ALL                no Linux capabilities
  --security-opt=no-new-privileges
  -v <scratch>:/sandbox        the ONLY writable path; no other host mount
  non-root (baked into the image, see docker/Dockerfile)
A host-side timeout kills and force-removes the container if a server
hangs, so one bad package cannot stall the run.

    python experiments/run_scale.py
    python experiments/run_scale.py --resume
    python experiments/run_scale.py --report-only
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Registry-checked triage is preferred: the plain triage.json's
# runnable_standalone is a false positive for any server whose declared
# package name was never actually published (15 of the original 32 --
# see run_registry_check.py), and those all fail identically at launch.
_REGISTRY_TRIAGE = ROOT / "data" / "processed" / "triage_registry.json"
_PLAIN_TRIAGE = ROOT / "data" / "processed" / "triage.json"
TRIAGE = _REGISTRY_TRIAGE if _REGISTRY_TRIAGE.exists() else _PLAIN_TRIAGE
OUT = ROOT / "data" / "processed" / "scale_run.json"
SCRATCH_ROOT = ROOT / "data" / "scratch" / "scale_run"
IMAGE = "mcpaudit-runner:latest"

# Git-Bash on Windows rewrites a bare leading "/..." argument into a host
# path before it ever reaches docker, silently turning /sandbox into
# something like C:/Program Files/Git/sandbox. This env pair is the
# documented escape hatch; it must be set on every docker invocation here.
DOCKER_ENV = {**os.environ, "MSYS_NO_PATHCONV": "1", "MSYS2_ARG_CONV_EXCL": "*"}


def load_targets() -> list[dict]:
    rows = json.loads(TRIAGE.read_text(encoding="utf-8"))
    return [r for r in rows if r["runnable_standalone"]]


def _compat_command(command: str) -> str:
    """Pin the MCP SDK our launched server pulls in, for uv-run packages.

    Discovered by running the pilot: `uvx <pkg>` resolves whatever `mcp`
    version satisfies the package's declared constraint, and an unpinned
    package gets the newest one -- 2.x here. Most of the harvested corpus
    was written against the 1.x `FastMCP` API, which 2.x renamed, so an
    otherwise-working server dies during our own client's initialize()
    with an opaque "Connection closed", nowhere near the real cause
    (ModuleNotFoundError: mcp.server.fastmcp, found only by running the
    command directly and reading its stderr). Constraining to `mcp<2`
    fixed it in the one case tested. This is a real ecosystem fact worth
    keeping in the writeup, not something to paper over silently -- the
    scale-run report should say how many servers needed it.
    """
    if command.startswith("uvx "):
        return command.replace("uvx ", 'uvx --with "mcp<2" ', 1)
    return command


def run_one(server: dict, timeout: float) -> dict:
    sid = server["server_id"]
    scratch = SCRATCH_ROOT / sid.replace("/", "__")
    scratch.mkdir(parents=True, exist_ok=True)
    name = f"mcpaudit-{uuid.uuid4().hex[:12]}"
    command = _compat_command(server["command"])

    cmd = [
        "docker", "run", "--rm", "--name", name,
        "--memory=512m", "--cpus=1", "--pids-limit=256",
        "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "-v", f"{scratch}:/sandbox",
        IMAGE,
        "--server-id", sid,
        "--command", command,
        "--cwd", "/sandbox",
        "--out", "/sandbox/result.json",
    ]

    t0 = time.time()
    try:
        proc = subprocess.run(cmd, env=DOCKER_ENV, timeout=timeout,
                              capture_output=True, text=True)
        stderr_tail = proc.stderr[-1500:] if proc.stderr else ""
    except subprocess.TimeoutExpired:
        # The docker CLI's own process was killed by the timeout, but the
        # container it started keeps running server-side unless force-
        # stopped explicitly. --rm alone does not guarantee that.
        subprocess.run(["docker", "kill", name], env=DOCKER_ENV,
                       capture_output=True, timeout=15)
        result_path = scratch / "result.json"
        if result_path.exists():
            try:
                data = json.loads(result_path.read_text(encoding="utf-8"))
                data["host_note"] = "killed after timeout, but wrote a result"
                return data
            except (json.JSONDecodeError, OSError):
                pass
        return {"server_id": sid, "status": "host_timeout",
                "timeout_s": timeout, "wall_s": round(time.time() - t0, 1)}
    except Exception as e:  # noqa: BLE001
        return {"server_id": sid, "status": "host_error",
                "error": f"{type(e).__name__}: {e}"}

    result_path = scratch / "result.json"
    if result_path.exists():
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
            data["wall_s"] = round(time.time() - t0, 1)
            data["original_command"] = server["command"]
            # Always attach, not just on the failure branches below. When
            # a server fails to launch, run_one.py's own exception message
            # is generic ("Connection closed" from deep inside our MCP
            # client) -- the REAL reason (package not on the registry, a
            # required CLI flag we did not supply, a CLI tool with no bare
            # stdio entrypoint) is only visible in what the launched
            # process itself printed, which is host-side stderr, not
            # something the container's own result.json can see.
            if stderr_tail:
                data["host_stderr_tail"] = stderr_tail
            return data
        except (json.JSONDecodeError, OSError) as e:
            return {"server_id": sid, "status": "unreadable_result",
                   "error": str(e), "stderr_tail": stderr_tail}
    return {"server_id": sid, "status": "no_result_written",
           "returncode": proc.returncode, "stderr_tail": stderr_tail,
           "wall_s": round(time.time() - t0, 1),
           "original_command": server["command"], "command": command}


# Ordered (pattern, reason) pairs; first match wins. Purely diagnostic --
# nothing here changes what gets launched, only how an already-failed
# launch is EXPLAINED, so "every failure explained" (docs/20) does not
# collapse into one opaque "failed" bucket across all 32 servers.
FAILURE_PATTERNS = [
    ("not found in the package registry", "not_published_on_registry"),
    ("No solution found when resolving", "dependency_resolution_failed"),
    ("the following arguments are required", "missing_required_cli_args"),
    ("Commands:\n", "cli_tool_no_bare_stdio_entrypoint"),
    ("ModuleNotFoundError", "python_import_error"),
    ("No matching distribution", "dependency_not_installable"),
    ("EACCES", "permission_denied"),
    ("ENOENT", "file_or_binary_not_found"),
    ("npm error", "npm_install_error"),
]


def classify_failure(row: dict) -> str:
    text = (row.get("host_stderr_tail", "") + row.get("stderr_tail", "")
            + row.get("error", ""))
    for pattern, reason in FAILURE_PATTERNS:
        if pattern in text:
            return reason
    return "unclassified"


def report(rows: list[dict]) -> None:
    n = len(rows)
    print(f"\n{'='*76}")
    print(f"PHASE 1 SCALE RUN  --  {n} runnable-standalone servers")
    print("=" * 76)

    print("\nStatus")
    for k, v in Counter(r.get("status", "?") for r in rows).most_common():
        print(f"  {k:22} {v:4}  ({100*v/n:4.1f}%)")

    failed = [r for r in rows if r.get("status") in
              ("failed", "no_result_written", "unreadable_result")]
    if failed:
        print("\nFailure reasons (of the failed launches)")
        for k, v in Counter(classify_failure(r) for r in failed).most_common():
            print(f"  {k:32} {v:4}")

    ok = [r for r in rows if r.get("status") == "ok" and "honest" in r
          and "tampered" in r]
    print(f"\nUsable trials (both honest and tampered completed): {len(ok)}/{n}")

    # write_errored excludes trials where the WRITE itself came back with
    # the protocol's isError flag set -- the server could not really
    # perform the action here (a missing external dependency, no live
    # session to act on), so nothing about detection or false positives
    # is being measured; counting it either way would attribute an
    # environment limitation to the defense.
    env_broken = [r for r in ok if r["honest"].get("write_errored")
                  or r.get("tampered", {}).get("write_errored")]
    honest_ok = [r for r in ok if "error" not in r["honest"]
                and not r["honest"].get("write_errored")]
    tampered_ok = [r for r in ok if "error" not in r["tampered"]
                   and not r["tampered"].get("write_errored")
                   and r["tampered"].get("attack_landed")]
    if env_broken:
        print(f"\nExcluded as environment-limited (write itself errored, "
              f"not a defense question): {len(env_broken)}")
        print("  ", [r["server_id"] for r in env_broken][:10])

    if honest_ok:
        fp = sum(1 for r in honest_ok if r["honest"]["violations"] > 0)
        print(f"\nFALSE POSITIVES (honest server flagged): {fp}/{len(honest_ok)} "
              f"({100*fp/len(honest_ok):.1f}%)")
        print("  Acceptance target (docs/20): < 5%")
        if fp:
            print("  Flagged:", [r["server_id"] for r in honest_ok
                                  if r["honest"]["violations"] > 0][:10])

    if tampered_ok:
        det = sum(1 for r in tampered_ok if r["tampered"]["violations"] > 0)
        print(f"\nDETECTION (attack landed AND caught): {det}/{len(tampered_ok)} "
              f"({100*det/len(tampered_ok):.1f}%)")
        print("  Acceptance target (docs/20): > 80%")
        missed = [r["server_id"] for r in tampered_ok
                 if r["tampered"]["violations"] == 0]
        if missed:
            print("  Missed:", missed[:10])

    n_launched = sum(1 for r in rows if r.get("status") in
                     ("ok", "no_write_tool_found"))
    print(f"\nServers actually launched: {n_launched}/{n}")
    print("  Acceptance target (docs/20): >= 30")

    print(f"\n{'='*76}")
    print("PER-SERVER")
    print("=" * 76)
    print(f"  {'server':40} {'status':16} {'FP':>4} {'DET':>4} {'wall_s':>7}")
    for r in sorted(rows, key=lambda x: x.get("server_id", "")):
        fp = "-"
        det = "-"
        h = r.get("honest", {})
        t = r.get("tampered", {})
        if r.get("status") == "ok" and "honest" in r and "error" not in h:
            fp = "env" if h.get("write_errored") else (
                "Y" if h["violations"] > 0 else "n")
        if r.get("status") == "ok" and "tampered" in r and "error" not in t:
            if t.get("write_errored"):
                det = "env"
            elif t.get("attack_landed"):
                det = "Y" if t["violations"] > 0 else "n"
        print(f"  {r.get('server_id','?')[:40]:40} "
              f"{r.get('status','?')[:16]:16} {fp:>4} {det:>4} "
              f"{r.get('wall_s','-'):>7}")
    print()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=float, default=180.0,
                    help="hard per-server wall-clock budget, seconds")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    rows: list[dict] = []
    if (args.resume or args.report_only) and args.out.exists():
        rows = json.loads(args.out.read_text(encoding="utf-8"))
        print(f"loaded {len(rows)} existing results")
    if args.report_only:
        report(rows)
        return

    targets = load_targets()
    done = {r["server_id"] for r in rows}
    todo = [t for t in targets if t["server_id"] not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(targets)} runnable-standalone servers; running {len(todo)}\n")

    for i, server in enumerate(todo, 1):
        sid = server["server_id"]
        print(f"  [{i}/{len(todo)}] {sid} ...", flush=True)
        result = run_one(server, args.timeout)
        rows.append(result)
        status = result.get("status", "?")
        extra = ""
        if status == "ok" and "tampered" in result:
            extra = (f" fp={result.get('honest',{}).get('violations','-')} "
                     f"det={result.get('tampered',{}).get('violations','-')}")
        print(f"       -> {status}{extra}")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(rows, indent=1, default=str),
                            encoding="utf-8")

    report(rows)


if __name__ == "__main__":
    main()

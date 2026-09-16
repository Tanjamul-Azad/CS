"""
Runs INSIDE the container, as root: M5 pilot -- a real server, not
touched by M2/M4 mechanism development before now, compared across three
conditions the way `25-research-program.md` section 6 M5 asks for.

SERVER: `io.github.domdomegg/filesystem-mcp`. Previously used exactly
once for M2-mechanism work -- the single-condition capstone combination
in `37`. This is its first use in a MULTI-BASELINE comparison, which is
what M5 actually asks for; stated precisely rather than stretched into a
claim this server was "never seen" by the project at all (it was, in
`29` section 1 and `37`).

SCOPE, stated before any result: M5's full baseline list (`25` section 6)
also names "the project's own auditor" (already measured at 0% true
detection elsewhere -- `results/tables/operating_points.md` -- not
re-run here against this one server, since that number is already
established), "plain container sandbox" (identical to "no defense" here,
since everything in this project already runs inside the same Docker
container regardless of condition -- there is no separate "outside the
container" baseline to compare against), and "MCP confirmation prompts"
(cannot be genuinely tested without a real human in the loop; simulating
one would be exactly the kind of fabricated result this project has
refused to produce throughout -- explicitly NOT attempted here). Two
baselines ARE run live: no defense, and a static least-privilege sandbox
built from plain Unix permissions -- plus this project's own M2
mechanism as the third condition.

Only ARGUMENT-level attacks are used (path diversion, content
substitution) -- not the OS-bypass techniques (symlink, hardlink,
preopened-fd, etc.) `malicious_server.py` uses, because those require a
deliberately adversarial SERVER IMPLEMENTATION, which only the stub
servers provide. A real, unmodified server just does what its own tool
declaration says; we do not control what it does internally, so only the
arguments it is sent can be tampered with here -- consistent with every
other real-server probe in this project (`29`, `37`).

STATIC LEAST-PRIVILEGE BASELINE, built from plain Unix permissions, no
software layer at all: the staging directory is owned by ROOT, mode 0555
(the untrusted server cannot create, delete, or rename ANY entry in it);
the one approved target file is PRE-CREATED, owned by `sandbox`, mode
0600 (the server CAN open and write to this existing file, since file
permissions -- not directory permissions -- govern writing to a file a
process already has access to). Whatever ends up in that file is trusted
directly: no diff, no commit/discard, no software mediation at all. This
is what "declarative permissions alone" looks like when implemented the
cheap, common way -- and its coverage against an attack that targets a
COMPLETELY DIFFERENT absolute path is the specific, honest question this
probe asks.
"""

from __future__ import annotations

import json
import os
import pwd
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, "/app/src")

from mcpmut.live import LiveSession  # noqa: E402
from mcpmut.proxy import TamperingProxy  # noqa: E402

NO_DEFENSE_BASE = Path("/staging_m5_nodef")
LEASTPRIV_BASE = Path("/staging_m5_leastpriv")
M2_STAGING_BASE = Path("/staging_m5_m2")
M2_COMMITTED = Path("/committed_m5_m2")
ESCAPE_PATH = "/tmp/exfil.dat"
SERVER_USER = "sandbox"
CONTENT = "quarterly numbers\n"


def su_command(inner: str) -> str:
    escaped = inner.replace("'", "'\\''")
    return f"su {SERVER_USER} -s /bin/sh -c '{escaped}'"


def snapshot(target: Path) -> str | None:
    return target.read_text(encoding="utf-8", errors="replace") if target.is_file() else None


def escape_snapshot() -> str | None:
    return snapshot(Path(ESCAPE_PATH))


def call_server(stage: Path, tamper: str | None) -> dict:
    approved_path = str(stage / "report.txt")
    cmd = su_command("npx -y filesystem-mcp")
    t0 = time.time()
    error = None
    attack_landed = None
    diverted_field = None
    try:
        with LiveSession(cmd, cwd=str(stage)) as s:
            if tamper == "path":
                proxy = TamperingProxy(inner=s.call, write_tools={"create"},
                                       read_tools={"view"}, level=1)
                result = proxy.call("create", {"path": approved_path, "content": CONTENT})
                plan = proxy.plans[-1] if proxy.plans else None
                attack_landed = bool(plan and plan.active)
                diverted_field = plan.target_field if plan else None
            elif tamper == "content":
                result = s.call("create", {"path": approved_path,
                                           "content": "ATTACKER-CONTROLLED PAYLOAD\n"})
                attack_landed = True
                diverted_field = "content"
            else:
                result = s.call("create", {"path": approved_path, "content": CONTENT})
    except Exception as e:  # noqa: BLE001
        result = None
        error = f"{type(e).__name__}: {e}"
    latency = time.time() - t0
    return {"result": result, "error": error, "attack_landed": attack_landed,
            "diverted_field": diverted_field, "latency_seconds": round(latency, 3)}


def reset_dir(path: Path, uid, gid, mode: int) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    if uid is not None:
        os.chown(path, uid, gid)
    os.chmod(path, mode)


def condition_no_defense(name: str, tamper: str | None) -> dict:
    rec = pwd.getpwnam(SERVER_USER)
    stage = NO_DEFENSE_BASE / name
    reset_dir(stage, rec.pw_uid, rec.pw_gid, 0o777)
    Path(ESCAPE_PATH).unlink(missing_ok=True)

    out = call_server(stage, tamper)
    committed_content = snapshot(stage / "report.txt")
    escape_content = escape_snapshot()
    unauthorized = escape_content is not None or (
        committed_content is not None and tamper == "content" and committed_content != CONTENT)
    return {"condition": "no_defense", **out, "committed_content": committed_content,
            "escape_content": escape_content, "unauthorized_effect": unauthorized,
            "false_block": False}


def condition_least_privilege(name: str, tamper: str | None) -> dict:
    rec = pwd.getpwnam(SERVER_USER)
    stage = LEASTPRIV_BASE / name
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    os.chown(stage, 0, 0)
    os.chmod(stage, 0o555)   # server cannot create/delete/rename entries here
    target = stage / "report.txt"
    target.write_text("", encoding="utf-8")
    os.chown(target, rec.pw_uid, rec.pw_gid)
    os.chmod(target, 0o600)   # server CAN write into this pre-existing file
    Path(ESCAPE_PATH).unlink(missing_ok=True)

    out = call_server(stage, tamper)
    committed_content = snapshot(target)
    if committed_content == "":
        committed_content = None
    escape_content = escape_snapshot()
    unauthorized = escape_content is not None or (
        committed_content is not None and tamper == "content" and committed_content != CONTENT)
    false_block = (tamper is None and committed_content != CONTENT)
    return {"condition": "static_least_privilege", **out, "committed_content": committed_content,
            "escape_content": escape_content, "unauthorized_effect": unauthorized,
            "false_block": false_block}


def condition_m2(name: str, tamper: str | None) -> dict:
    rec = pwd.getpwnam(SERVER_USER)
    stage = M2_STAGING_BASE / name
    reset_dir(stage, rec.pw_uid, rec.pw_gid, 0o700)
    reset_dir(M2_COMMITTED, 0, 0, 0o755)
    Path(ESCAPE_PATH).unlink(missing_ok=True)

    out = call_server(stage, tamper)
    approved_path = stage / "report.txt"
    staged_content = snapshot(approved_path)
    escape_content = escape_snapshot()

    matches = staged_content == CONTENT
    decision = "commit" if (matches and escape_content is None) else "discard"
    committed_content = None
    if decision == "commit":
        (M2_COMMITTED / "report.txt").write_text(staged_content, encoding="utf-8")
        committed_content = staged_content

    unauthorized = escape_content is not None or (
        committed_content is not None and committed_content != CONTENT)
    false_block = (tamper is None and committed_content != CONTENT)
    return {"condition": "m2_mechanism", **out, "committed_content": committed_content,
            "escape_content": escape_content, "unauthorized_effect": unauthorized,
            "false_block": false_block, "decision": decision}


def main() -> None:
    scenarios = [("honest", None), ("path_diversion", "path"), ("content_substitution", "content")]
    rows = []
    for name, tamper in scenarios:
        for fn in (condition_no_defense, condition_least_privilege, condition_m2):
            r = fn(name, tamper)
            r["scenario"] = name
            rows.append(r)
    print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()

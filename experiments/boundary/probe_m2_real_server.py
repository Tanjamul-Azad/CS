"""
Runs INSIDE the container, as root: the capstone integration this
project's own docs kept naming as the next step (`29`, `31`, `34`, `35`,
`36`) -- the M2-proper mediator, combined with a REAL, unmodified,
third-party MCP server for the first time, not the synthetic
`malicious_server.py`/`adaptive_server.py` stubs every other M2 probe
uses.

WHY THIS WASN'T DONE UNTIL NOW. The M3 probes (`docs/29`) launch a real
server and observe what it does, with no OS confinement at all -- that
was the right design for measuring "does the contract-check mechanism
transfer," and it is why `domdomegg/filesystem-mcp` was shown writing
for real to `/tmp/exfil.dat` outside any sandbox. The M2 probes confine a
process with real OS ownership, but only ever launched
`malicious_server.py`, not a real MCP server, because `LiveSession`
(the project's real-MCP-protocol client) has no built-in way to drop
privileges on the subprocess it launches -- `StdioServerParameters` (the
MCP SDK's own launch-parameter type) exposes no `preexec_fn` or uid/gid
option at all. VERIFIED, not assumed: the underlying MCP SDK type was
inspected directly and confirmed to lack this.

THE FIX: wrap the launch command in `su sandbox -s /bin/sh -c '...'`.
`LiveSession` only ever sees a command string; it does not care that the
string itself performs a privilege drop before the real server starts.
Verified live before writing this probe: a real `npx -y filesystem-mcp`
process launched this way answers `tools/list` and `create` calls
normally over stdio, and the file it writes is owned by the `sandbox`
UID, not root -- genuine OS-level confinement of a real, unmodified
third-party process, combined with the real MCP protocol, for the first
time in this project.

SERVER: `io.github.domdomegg/filesystem-mcp`, the same server `29` §1
used -- chosen specifically to close the loop: that experiment showed its
diverted write landing for real, unconfined, outside `/sandbox`. This one
asks whether the M2 mediator's OS-owned staging area plus its
request-shape-then-effect-diff pipeline actually stops that from ever
reaching a trusted committed store.

MEDIATOR: identical logic to `probe_m2.py`'s post-fix `run_m2` --
request-shape check on the arguments actually sent (this tool's schema
declares `additionalProperties: false`, so the SDK itself already refuses
an unlisted argument before the request-shape check would even see one --
itself a finding, not a gap, per `29` §1), then a single read of staging
for the diff, then commit the bytes from that SAME read (never a second,
independent read) into a separate root-owned committed store the server
has no permission on.
"""

from __future__ import annotations

import json
import os
import pwd
import shutil
import sys
from pathlib import Path

sys.path.insert(0, "/app/src")

from mcpmut.live import LiveSession  # noqa: E402
from mcpmut.proxy import TamperingProxy  # noqa: E402

STAGING_BASE = Path("/staging_real")
COMMITTED = Path("/committed_real")
ESCAPE_PATH = "/tmp/exfil.dat"   # TamperingProxy._divert_value's fixed, hardcoded target -- not configurable, verified in src/mcpmut/proxy.py
SERVER_USER = "sandbox"
CONTENT = "quarterly numbers\n"

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"


def observe_paths(paths: list[Path]) -> dict:
    out = {}
    for p in paths:
        out[str(p)] = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None
    return out


def reset_dir(path: Path, uid, gid, mode: int) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    if uid is not None:
        os.chown(path, uid, gid)
    os.chmod(path, mode)


def su_command(inner: str) -> str:
    # LiveSession only ever sees this as a command string; su performs
    # the real privilege drop for whatever runs after -c.
    escaped = inner.replace("'", "'\\''")
    return f"su {SERVER_USER} -s /bin/sh -c '{escaped}'"


def mediate(before: dict, staged_content: str | None, escape_content: str | None,
           approved_path: str) -> dict:
    """probe_m2.py's post-fix mediator logic, applied to a real server's
    real filesystem effect instead of a synthetic scenario's."""
    matches_contract = staged_content == CONTENT
    escape_touched = escape_content is not None

    v = {}
    v["destination"] = FAIL if escape_touched else PASS
    v["content"] = PASS if matches_contract else FAIL
    decision = "commit" if (matches_contract and not escape_touched) else "discard"

    committed_content = None
    if decision == "commit":
        # Commit the bytes from the SAME read used for the diff -- the
        # M2 Commit Invariant (docs/33 section 3), applied here too.
        (COMMITTED / "report.txt").write_text(staged_content, encoding="utf-8")
        committed_content = staged_content

    unauthorized = []
    if escape_touched:
        unauthorized.append("real server wrote to the escape path, outside staging")
    if matches_contract is False and staged_content is not None:
        unauthorized.append("staged content does not match the approved bytes")

    return {"verdicts": v, "decision": decision,
            "committed_content": committed_content,
            "unauthorized_effects": unauthorized}


def run_trial(name: str, tamper: str | None) -> dict:
    """tamper: None (honest), 'path' (TamperingProxy diversion),
    'content' (manual substitution)."""
    rec = pwd.getpwnam(SERVER_USER)
    staging = STAGING_BASE / name
    reset_dir(staging, rec.pw_uid, rec.pw_gid, 0o700)
    reset_dir(COMMITTED, 0, 0, 0o755)
    Path(ESCAPE_PATH).unlink(missing_ok=True)

    approved_path = str(staging / "report.txt")
    cmd = su_command("npx -y filesystem-mcp")

    error = None
    attack_landed = None
    diverted_field = None
    try:
        with LiveSession(cmd, cwd=str(staging)) as s:
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

    staged_content = Path(approved_path).read_text(encoding="utf-8", errors="replace") \
        if Path(approved_path).is_file() else None
    escape_content = Path(ESCAPE_PATH).read_text(encoding="utf-8", errors="replace") \
        if Path(ESCAPE_PATH).is_file() else None

    med = mediate({}, staged_content, escape_content, approved_path)

    return {"scenario": name, "tamper": tamper, "server_error": error,
            "server_response": result, "attack_landed_per_proxy": attack_landed,
            "diverted_field": diverted_field,
            "staged_content": staged_content, "escape_content": escape_content,
            **med}


def main() -> None:
    rows = [
        run_trial("honest", None),
        run_trial("path_diversion", "path"),
        run_trial("content_substitution", "content"),
    ]
    print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()

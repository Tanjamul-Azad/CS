"""
Runs INSIDE the container, as root: M5's SECOND server -- extending the
one-server pilot (`probe_m5_held_out.py`, docs/41) to a second, genuinely
different real server, addressing the honest limitation stated in `30`
section 12 ("M5 is a one-server pilot").

SERVER: `notes-mcp` -- the same PyPI package added to M3 in
`probe_notes.py` (docs/29 section 7). Chosen for M5 specifically because
its destination-diversion attack has a DIFFERENT shape than
`domdomegg/filesystem-mcp`'s: `path` is a RELATIVE filename, so the
diverted write lands as a SIBLING file INSIDE the same directory, not an
absolute escape to `/tmp` (see `probe_notes.py`'s own docstring). This is
the precise condition under which a directory-permission baseline (no
write bit for the untrusted identity) could plausibly stop a
path-diversion attack that `probe_m5_held_out.py`'s absolute-path escape
cannot -- tested here empirically, not assumed from the file's own
comment.

Same three conditions as `probe_m5_held_out.py`: no_defense,
static_least_privilege (plain Unix permissions, no software layer),
m2_mechanism (this project's staging + request-shape + effect-diff +
commit-or-discard). Same scope caveats apply (see that file's docstring):
only argument-level attacks (destination, content), not OS-bypass
techniques; the project's own auditor and "plain container sandbox"
baselines are not re-run here for the same reasons stated there; MCP
confirmation prompts still need a real human, not simulated.

Content attack uses `markdown_content` only (`content_substitution` here
mirrors `markdown_substitution` in `probe_notes.py`) -- kept to ONE
content scenario, not two, to keep this table directly comparable in
shape to `probe_m5_held_out.py`'s three-scenario table rather than
doubling scope for its own sake.
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

NO_DEFENSE_BASE = Path("/staging_m5n_nodef")
LEASTPRIV_BASE = Path("/staging_m5n_leastpriv")
M2_STAGING_BASE = Path("/staging_m5n_m2")
M2_COMMITTED = Path("/committed_m5n_m2")
SERVER_USER = "sandbox"

APPROVED_YAML = "---\ntitle: Q3 Report\n---"
APPROVED_MARKDOWN = "quarterly numbers"
APPROVED_CONTENT = f"{APPROVED_YAML}\n{APPROVED_MARKDOWN}"
ESCAPE_NAME = "attacker-controlled"


def su_command(inner: str) -> str:
    escaped = inner.replace("'", "'\\''")
    return f"su {SERVER_USER} -s /bin/sh -c '{escaped}'"


def snapshot(path: Path) -> str | None:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None


def call_server(stage: Path, tamper: str | None) -> dict:
    cmd = su_command(f"uvx notes-mcp {stage}")
    t0 = time.time()
    error = None
    attack_landed = None
    diverted_field = None
    try:
        with LiveSession(cmd, cwd=str(stage)) as s:
            if tamper == "path":
                proxy = TamperingProxy(inner=s.call, write_tools={"write"},
                                       read_tools=set(), level=1)
                result = proxy.call("write", {"path": "report.md",
                                              "yaml_frontmatter": APPROVED_YAML,
                                              "markdown_content": APPROVED_MARKDOWN})
                plan = proxy.plans[-1] if proxy.plans else None
                attack_landed = bool(plan and plan.active)
                diverted_field = plan.target_field if plan else None
            elif tamper == "content":
                result = s.call("write", {"path": "report.md",
                                          "yaml_frontmatter": APPROVED_YAML,
                                          "markdown_content": "ATTACKER-CONTROLLED PAYLOAD"})
                attack_landed = True
                diverted_field = "markdown_content"
            else:
                result = s.call("write", {"path": "report.md",
                                          "yaml_frontmatter": APPROVED_YAML,
                                          "markdown_content": APPROVED_MARKDOWN})
            errored = s.last_was_error
    except Exception as e:  # noqa: BLE001
        result = None
        errored = None
        error = f"{type(e).__name__}: {e}"
    latency = time.time() - t0
    return {"result": result, "error": error, "server_refused_call": errored,
            "attack_landed": attack_landed, "diverted_field": diverted_field,
            "latency_seconds": round(latency, 3)}


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

    out = call_server(stage, tamper)
    committed_content = snapshot(stage / "report.md")
    escape_content = snapshot(stage / ESCAPE_NAME)
    unauthorized = escape_content is not None or (
        committed_content is not None and tamper == "content"
        and committed_content != APPROVED_CONTENT)
    return {"condition": "no_defense", **out, "committed_content": committed_content,
            "escape_content": escape_content, "unauthorized_effect": unauthorized,
            "false_block": False}


def condition_least_privilege(name: str, tamper: str | None) -> dict:
    """Directory locked 0555, root-owned -- the untrusted identity has NO
    write bit on the directory itself, unlike `probe_m5_held_out.py`'s
    server which only ever escapes to an ABSOLUTE path outside the
    locked directory. Here the diversion is a RELATIVE sibling name
    inside the SAME directory -- so this condition specifically tests
    whether that structural difference changes the outcome, not assumed
    either way before running."""
    rec = pwd.getpwnam(SERVER_USER)
    stage = LEASTPRIV_BASE / name
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    os.chown(stage, 0, 0)
    os.chmod(stage, 0o555)   # server cannot create/delete/rename entries here
    target = stage / "report.md"
    target.write_text("", encoding="utf-8")
    os.chown(target, rec.pw_uid, rec.pw_gid)
    os.chmod(target, 0o600)   # server CAN write into this pre-existing file

    out = call_server(stage, tamper)
    committed_content = snapshot(target)
    if committed_content == "":
        committed_content = None
    escape_content = snapshot(stage / ESCAPE_NAME)
    unauthorized = escape_content is not None or (
        committed_content is not None and tamper == "content"
        and committed_content != APPROVED_CONTENT)
    false_block = (tamper is None and committed_content != APPROVED_CONTENT)
    return {"condition": "static_least_privilege", **out, "committed_content": committed_content,
            "escape_content": escape_content, "unauthorized_effect": unauthorized,
            "false_block": false_block}


def condition_m2(name: str, tamper: str | None) -> dict:
    rec = pwd.getpwnam(SERVER_USER)
    stage = M2_STAGING_BASE / name
    reset_dir(stage, rec.pw_uid, rec.pw_gid, 0o700)
    reset_dir(M2_COMMITTED, 0, 0, 0o755)

    out = call_server(stage, tamper)
    target = stage / "report.md"
    staged_content = snapshot(target)
    escape_content = snapshot(stage / ESCAPE_NAME)

    matches = staged_content == APPROVED_CONTENT
    decision = "commit" if (matches and escape_content is None) else "discard"
    committed_content = None
    if decision == "commit":
        (M2_COMMITTED / "report.md").write_text(staged_content, encoding="utf-8")
        committed_content = staged_content

    unauthorized = escape_content is not None or (
        committed_content is not None and committed_content != APPROVED_CONTENT)
    false_block = (tamper is None and committed_content != APPROVED_CONTENT)
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

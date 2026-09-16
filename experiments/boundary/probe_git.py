"""
Runs INSIDE the container: the fifth real-server datapoint for M3
(docs/29), and the first git-native one. `mcp-server-git` (`uvx
mcp-server-git --repository <path>`, the official Python/uv-published
server -- `docker/Dockerfile` was extended with the `git` system package
specifically to run this, verified live not assumed) exposes git plumbing
as MCP tools: `git_status`, `git_add`, `git_commit`, `git_log`, `git_show`,
`git_diff*`, `git_branch`, `git_checkout`, `git_create_branch`, `git_reset`.
Schema verified live via inspect_server.py.

WHY THIS IS A DIFFERENT SHAPE AGAIN, NOT JUST ANOTHER "EXACT" SERVER.
`git_commit(repo_path: string, message: string)` has no argument for file
CONTENT at all -- unlike every server tested so far, this tool's mutating
call never carries the payload. The payload (what changed) is whatever is
already staged in the working tree, put there by a SEPARATE `git_add`
call (also an MCP tool here) operating on a file this probe wrote through
the filesystem directly, outside any MCP call, exactly as a real agent
would (write a file, then use git tools to stage and commit it). So the
CONTRACT's "content" property here is not file bytes -- it is the commit
MESSAGE, the one thing `git_commit` actually contributes as an argument.

CONTRACT: `repo_path` matches every OTHER probe's `path`-shaped field
almost letter for letter, so `TamperingProxy` diverts it automatically
via its existing `TARGET_FIELDS` vocabulary (`repo_path` contains both
"repo" and "path") -- no manual diversion needed this time, unlike the
memory/sqlite probes.

    L1  destination only    only the approved repo received a new commit
    L2  + structure          the approved repo's HEAD commit count
                              actually advanced (a commit really happened,
                              not just a call that returned)
    L3  + content            the new commit's message exactly matches the
                              approved text

ESCAPE REPO. `TamperingProxy._divert_value` sends any "/"-bearing string
to the fixed `/tmp/exfil.dat`. For the diverted commit to actually land
(rather than erroring "not a git repository," a less informative outcome
than the real external-effect findings in `real_server_probe.py` and
`probe_server_memory.py`), `/tmp/exfil.dat` is initialised as a real git
repository once, at start-up -- so a diverted commit, if the server
performs it, is a genuine, observable external effect, exactly like the
escape FILE in the filesystem probes and the escape ENTITY in the memory
probe.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/app/src")

from mcpmut.live import LiveSession  # noqa: E402
from mcpmut.proxy import TamperingProxy  # noqa: E402

CONTENT = "quarterly numbers\n"
APPROVED_MESSAGE = "quarterly report committed"
ESCAPE_REPO = "/tmp/exfil.dat"

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"


def run_git(repo: str, *args: str) -> str:
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    return r.stdout.strip()


def init_repo(repo: str) -> None:
    Path(repo).mkdir(parents=True, exist_ok=True)
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.email", "probe@test")
    run_git(repo, "config", "user.name", "probe")
    (Path(repo) / "seed.txt").write_text("seed\n", encoding="utf-8")
    run_git(repo, "add", "seed.txt")
    run_git(repo, "commit", "-q", "-m", "seed")


def commit_count(repo: str) -> int:
    out = run_git(repo, "rev-list", "--count", "HEAD")
    return int(out) if out.isdigit() else 0


def last_message(repo: str) -> str | None:
    if commit_count(repo) == 0:
        return None
    return run_git(repo, "log", "-1", "--pretty=%s")


def snapshot(target_repo: str) -> dict:
    return {
        "target_count": commit_count(target_repo),
        "target_message": last_message(target_repo),
        "escape_count": commit_count(ESCAPE_REPO),
    }


def check_properties(rung: str, before: dict, after: dict) -> dict:
    v: dict[str, str] = {}
    escape_changed = after["escape_count"] != before["escape_count"]
    v["destination"] = FAIL if escape_changed else PASS
    v["frame_intact"] = v["destination"]

    if rung == "L1":
        v["structure"] = UNKNOWN
        v["content"] = UNKNOWN
        return v

    v["structure"] = PASS if after["target_count"] > before["target_count"] else FAIL
    if rung == "L2":
        v["content"] = UNKNOWN
        return v

    v["content"] = PASS if after["target_message"] == APPROVED_MESSAGE else FAIL
    return v


def decide(verdicts: dict) -> str:
    return "discard" if FAIL in verdicts.values() else "commit"


def oracle(before: dict, after: dict) -> dict:
    unauthorized = []
    if after["escape_count"] != before["escape_count"]:
        unauthorized.append("escape repo received a commit without approval")
    if after["target_count"] > before["target_count"] and after["target_message"] != APPROVED_MESSAGE:
        unauthorized.append("approved repo's new commit holds an unapproved message")
    authorized = (after["target_count"] > before["target_count"]
                 and after["target_message"] == APPROVED_MESSAGE and not unauthorized)
    return {"authorized_effect": bool(authorized),
            "unauthorized_effect": bool(unauthorized),
            "oracle_findings": unauthorized,
            "no_change": after == before}


def command_for(stage: str) -> str:
    return f"uvx mcp-server-git --repository {stage}"


def prep_target(stage: str) -> None:
    init_repo(stage)
    (Path(stage) / "report.txt").write_text(CONTENT, encoding="utf-8")


def run_honest(stage: str) -> dict:
    with LiveSession(command_for(stage), cwd=stage) as s:
        s.call("git_add", {"repo_path": stage, "files": ["report.txt"]})
        result = s.call("git_commit", {"repo_path": stage, "message": APPROVED_MESSAGE})
        errored = s.last_was_error
    return {"result": result, "attack_landed": None, "diverted_field": None, "server_refused": errored}


def run_path_diversion(stage: str) -> dict:
    with LiveSession(command_for(stage), cwd=stage) as s:
        s.call("git_add", {"repo_path": stage, "files": ["report.txt"]})
        proxy = TamperingProxy(inner=s.call, write_tools={"git_commit"}, read_tools=set(), level=1)
        result = proxy.call("git_commit", {"repo_path": stage, "message": APPROVED_MESSAGE})
        plan = proxy.plans[-1] if proxy.plans else None
        errored = s.last_was_error
    return {"result": result, "attack_landed": bool(plan and plan.active),
            "diverted_field": plan.target_field if plan else None, "server_refused": errored}


def run_message_substitution(stage: str) -> dict:
    with LiveSession(command_for(stage), cwd=stage) as s:
        s.call("git_add", {"repo_path": stage, "files": ["report.txt"]})
        result = s.call("git_commit", {"repo_path": stage, "message": "ATTACKER-CONTROLLED PAYLOAD"})
        errored = s.last_was_error
    return {"result": result, "attack_landed": True, "diverted_field": "message", "server_refused": errored}


SCENARIOS = {"honest": run_honest, "path_diversion": run_path_diversion,
            "message_substitution": run_message_substitution}


def trial(name: str, rung: str) -> dict:
    stage = f"/sandbox/git_{name}_{rung}"
    prep_target(stage)
    before = snapshot(stage)

    try:
        out = SCENARIOS[name](stage)
        error = None
    except Exception as e:  # noqa: BLE001
        out = {"result": None, "attack_landed": None, "diverted_field": None, "server_refused": None}
        error = f"{type(e).__name__}: {e}"

    after = snapshot(stage)
    verdicts = check_properties(rung, before, after)
    decision = decide(verdicts)

    committed = after if decision == "commit" else before
    o = oracle(before, committed)

    return {"scenario": name, "rung": rung, "server_error": error,
            "server_refused_call": out.get("server_refused"),
            "server_response": out.get("result"),
            "attack_landed_per_proxy": out.get("attack_landed"),
            "diverted_field": out.get("diverted_field"),
            "staged_before": before, "staged_after": after,
            "verdicts": verdicts, "decision": decision,
            "committed_state": committed, **o}


def main() -> None:
    init_repo(ESCAPE_REPO)
    rows = [trial(name, rung) for name in SCENARIOS for rung in ("L1", "L2", "L3")]
    print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()

"""
Runs INSIDE the container: the specification-ladder contract mechanism
against a REAL, unmodified, third-party MCP server -- not a stub we wrote.

Every prior test of the contract/staging mechanism used a Python process
WE authored (append_server.py, ladder_server.py, malicious_server.py).
That answers "does our mechanism work against code we control to misbehave
exactly how we specified" -- necessary, not sufficient. This answers the
harder question M3 actually asks: does a contract we did NOT tune for this
server, checked against ITS real declared schema, still confine and
correctly discriminate a real MCP package pulled from npm?

SERVER: io.github.domdomegg/filesystem-mcp (`npx -y filesystem-mcp`).
Chosen because its `create(path, content)` tool is exactly the EXACT
workflow class from docs/27, its schema was inspected live (not assumed),
and it is the same server whose suppressed detection is documented in
docs/24 -- so this closes a loop rather than picking a new example.

THREAT MODEL HERE. We do not control this server's code, so we cannot make
it misbehave internally the way ladder_server.py does. What we DO control,
faithfully to the rest of this project (mcpmut/proxy.py, the whole scale
run), is the ARGUMENTS it is sent -- a compromised or malicious proxy
sitting between the agent and this server. Two attacks:

  path_diversion         via the project's own TamperingProxy (L1), so
                          this is literally the same attack the original
                          1,242-server scale run measured against this
                          exact server (docs/24): diverted_field=path
  content_substitution   the payload is swapped before the call; the
                          destination is untouched

Both are PERMISSION-COMPATIBLE: `create` is called with valid arguments a
schema-conformant client could send; nothing exploits a bug in the server.

CONTRACT, derived from create's real inputSchema (path: string, content:
string, both required, additionalProperties: false -- verified live, not
assumed):

    L1  destination only    only the approved path changed
    L2  + structure          non-empty (no further structure exists for a
                              free-text file; the ladder finding that L2
                              buys nothing on the EXACT class, already
                              measured on our own stub in docs/27, is
                              re-tested here on real code)
    L3  + content            committed bytes equal the approved content

`additionalProperties: false` on this tool's schema means the SDK itself
refuses an unlisted argument -- the "hidden extra field" attack from
docs/27 §4 is inapplicable to a tool declared this way, which is itself a
finding, not a gap in the probe.

WHY THIS DOES NOT CRAWL A STAGING DIRECTORY (first version of this probe
did, and the result was wrong). `create`'s tool description requires an
ABSOLUTE path -- confirmed live, this server does not resolve relative to
its own `cwd`. `TamperingProxy._divert_value` (src/mcpmut/proxy.py), when
it diverts a string containing "/", always substitutes the fixed value
"/tmp/exfil.dat" -- an absolute path with no relation to the staging
directory the honest call's path lives under. Against a REAL, unconfined
process (no OS-level sandboxing in THIS probe -- that is what the separate
docker/boundary/ probe already tests, via a different Linux user and
chmod/chown), a diverted absolute path is written for real, outside
`/sandbox` entirely. A directory crawl scoped to the per-trial staging
directory therefore never observes it: `before == after` inside that
directory regardless of what the server actually did, which silently
manufactured a false "destination=PASS" for an attack that, in truth,
landed. Watching the two paths that are actually in play --  the approved
absolute target and the proxy's known, fixed escape path -- fixes this.

SCOPE THIS PROBE ACTUALLY HAS. Because there is no OS-level mediation
here, "discard" is a bookkeeping decision about what this audit counts as
committed, NOT an undo of a write the real server already made to
/tmp/exfil.dat. That is a real, external side effect this probe detects
but does not roll back -- the same limitation the SAFEFLOW comparison in
docs/26 documents for rollback-of-external-effects in general. Actual
prevention (not just detection) for an unconfined absolute-path escape
requires OS-level enforcement, which is exactly what the separate
docker/boundary/probe.py already measures under a different mechanism
(a different Linux user + chmod/chown, not a contract check). Report this
probe's result as detection at the contract-check layer, not as proof the
external write never happened.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "/app/src")

from mcpmut.live import LiveSession  # noqa: E402
from mcpmut.proxy import TamperingProxy  # noqa: E402

COMMAND = "npx -y filesystem-mcp"
CONTENT = "quarterly numbers\n"
ESCAPE_PATH = "/tmp/exfil.dat"   # TamperingProxy._divert_value's fixed target for any "/"-bearing string

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"


def read_file(path: str) -> str | None:
    p = Path(path)
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None


def snapshot(target_abs: str) -> dict:
    """The only two locations a write from these three scenarios can land:
    the approved target, and the proxy's known, fixed escape path. Not a
    directory crawl -- see module docstring for why a directory crawl
    scoped to the staging dir cannot see an absolute-path escape."""
    return {"target": read_file(target_abs), "escape": read_file(ESCAPE_PATH)}


def check_properties(rung: str, before: dict, after: dict) -> dict:
    v: dict[str, str] = {}
    escape_changed = before["escape"] != after["escape"]
    v["destination"] = FAIL if escape_changed else PASS
    v["frame_intact"] = v["destination"]

    if rung == "L1":
        v["structure"] = UNKNOWN
        v["content"] = UNKNOWN
        return v

    v["structure"] = PASS if after["target"] else FAIL
    if rung == "L2":
        v["content"] = UNKNOWN
        return v

    v["content"] = PASS if after["target"] == CONTENT else FAIL
    return v


def decide(verdicts: dict) -> str:
    if FAIL in verdicts.values():
        return "discard"
    return "commit"          # UNKNOWN_POLICY=commit, same declared choice as docs/27


def oracle(before: dict, after: dict) -> dict:
    """Independent of the contract -- state only, over the same two
    watched locations."""
    unauthorized = []
    if before["escape"] != after["escape"]:
        unauthorized.append("escape path changed without approval")
    if after["target"] not in (None, CONTENT) and before["target"] != after["target"]:
        unauthorized.append("approved file holds unapproved content")
    authorized = after["target"] == CONTENT and not unauthorized
    return {"authorized_effect": bool(authorized),
            "unauthorized_effect": bool(unauthorized),
            "oracle_findings": unauthorized,
            "no_change": after == before}


def run_honest(stage: Path, target_abs: str) -> dict:
    with LiveSession(COMMAND, cwd=str(stage)) as s:
        result = s.call("create", {"path": target_abs, "content": CONTENT})
    return {"result": result, "attack_landed": None, "diverted_field": None}


def run_path_diversion(stage: Path, target_abs: str) -> dict:
    """The proxy this project already validated (mcpmut/proxy.py),
    unmodified, against a real live session -- exactly the mechanism the
    original scale run used against this same server."""
    with LiveSession(COMMAND, cwd=str(stage)) as s:
        proxy = TamperingProxy(inner=s.call, write_tools={"create"},
                               read_tools={"view"}, level=1)
        result = proxy.call("create", {"path": target_abs, "content": CONTENT})
        plan = proxy.plans[-1] if proxy.plans else None
    return {"result": result,
            "attack_landed": bool(plan and plan.active),
            "diverted_field": plan.target_field if plan else None}


def run_content_substitution(stage: Path, target_abs: str) -> dict:
    """Destination untouched, payload swapped before the call -- a
    compromised proxy rewriting the argument, not a server bug."""
    tampered = {"path": target_abs, "content": "ATTACKER-CONTROLLED PAYLOAD\n"}
    with LiveSession(COMMAND, cwd=str(stage)) as s:
        result = s.call("create", tampered)
    return {"result": result, "attack_landed": True, "diverted_field": "content"}


SCENARIOS = {"honest": run_honest, "path_diversion": run_path_diversion,
            "content_substitution": run_content_substitution}


def trial(name: str, rung: str) -> dict:
    stage = Path(f"/sandbox/{name}_{rung}")
    stage.mkdir(parents=True, exist_ok=True)
    target_abs = str(stage / "report.txt")

    Path(ESCAPE_PATH).unlink(missing_ok=True)   # each trial starts from a clean escape slot
    before = snapshot(target_abs)

    try:
        out = SCENARIOS[name](stage, target_abs)
        error = None
    except Exception as e:  # noqa: BLE001
        out = {"result": None, "attack_landed": None, "diverted_field": None}
        error = f"{type(e).__name__}: {e}"

    staged_after = snapshot(target_abs)
    verdicts = check_properties(rung, before, staged_after)
    decision = decide(verdicts)

    committed = staged_after if decision == "commit" else before
    o = oracle(before, committed)

    return {"scenario": name, "rung": rung, "server_error": error,
            "server_response": out.get("result"),
            "attack_landed_per_proxy": out.get("attack_landed"),
            "diverted_field": out.get("diverted_field"),
            "staged_before": before, "staged_after": staged_after,
            "verdicts": verdicts, "decision": decision,
            "committed_state": committed, **o}


def main() -> None:
    rows = [trial(name, rung) for name in SCENARIOS for rung in ("L1", "L2", "L3")]
    print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()

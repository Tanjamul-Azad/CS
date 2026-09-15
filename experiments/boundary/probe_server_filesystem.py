"""
Runs INSIDE the container: the second real-server datapoint for M3
(docs/29). Same EXACT workflow class and the same `path`/`content` tool
shape as `real_server_probe.py`'s target (domdomegg/filesystem-mcp), but a
DIFFERENT, independent implementation: the official reference server
`@modelcontextprotocol/server-filesystem` (`write_file`). The point of
running both is that "same workflow class, same tool shape" does not mean
"same behavior" -- confirmed below.

SCHEMA, verified live (inspect_server.py), not assumed: `write_file(path:
string, content: string)`, both required. No `additionalProperties: false`
here (unlike domdomegg's), and no `read`-tool sibling scoping check either
-- this server instead enforces its OWN boundary: it takes an allowed
directory as a CLI argument at launch and refuses any path that resolves
outside it, independent of any contract this probe applies.

WHAT THIS SERVER'S OWN CHECK ALREADY CATCHES. Verified live: driving this
tool through the project's unmodified TamperingProxy (the same one used
against domdomegg/filesystem-mcp) diverts `path` to the proxy's fixed
escape value `/tmp/exfil.dat`. Against domdomegg/filesystem-mcp that write
landed for real (docs/29). Against THIS server it is refused outright --
`isError=True`, "Access denied - path outside allowed directories" -- the
server's own allowlist check rejects it before any external effect
happens. This is a genuine per-implementation difference in a "same
workflow class" tool, which is exactly the kind of variation M3 exists to
measure. `s.last_was_error` (the SDK's own `is_error`/`isError` field,
read under both spellings -- see docs/24's calibration bug) is recorded
per trial so a refusal is never miscounted as either a successful honest
write or a successful attack.

CONTRACT: identical structure to `real_server_probe.py` (L1 destination /
L2 structure / L3 content), and the same fixed two-location snapshot
(approved target, proxy's known escape path) rather than a directory
crawl, for the same reason documented there.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "/app/src")

from mcpmut.live import LiveSession  # noqa: E402
from mcpmut.proxy import TamperingProxy  # noqa: E402

CONTENT = "quarterly numbers\n"
ESCAPE_PATH = "/tmp/exfil.dat"

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"


def read_file(path: str) -> str | None:
    p = Path(path)
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None


def snapshot(target_abs: str) -> dict:
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
    return "discard" if FAIL in verdicts.values() else "commit"


def oracle(before: dict, after: dict) -> dict:
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


def command_for(stage: Path) -> str:
    return f"npx -y @modelcontextprotocol/server-filesystem {stage}"


def run_honest(stage: Path, target_abs: str) -> dict:
    with LiveSession(command_for(stage), cwd=str(stage)) as s:
        result = s.call("write_file", {"path": target_abs, "content": CONTENT})
        errored = s.last_was_error
    return {"result": result, "attack_landed": None, "diverted_field": None,
            "server_refused": errored}


def run_path_diversion(stage: Path, target_abs: str) -> dict:
    with LiveSession(command_for(stage), cwd=str(stage)) as s:
        proxy = TamperingProxy(inner=s.call, write_tools={"write_file"},
                               read_tools={"read_text_file"}, level=1)
        result = proxy.call("write_file", {"path": target_abs, "content": CONTENT})
        plan = proxy.plans[-1] if proxy.plans else None
        errored = s.last_was_error
    return {"result": result,
            "attack_landed": bool(plan and plan.active),
            "diverted_field": plan.target_field if plan else None,
            "server_refused": errored}


def run_content_substitution(stage: Path, target_abs: str) -> dict:
    tampered = {"path": target_abs, "content": "ATTACKER-CONTROLLED PAYLOAD\n"}
    with LiveSession(command_for(stage), cwd=str(stage)) as s:
        result = s.call("write_file", tampered)
        errored = s.last_was_error
    return {"result": result, "attack_landed": True, "diverted_field": "content",
            "server_refused": errored}


SCENARIOS = {"honest": run_honest, "path_diversion": run_path_diversion,
            "content_substitution": run_content_substitution}


def trial(name: str, rung: str) -> dict:
    stage = Path(f"/sandbox/sf_{name}_{rung}")
    stage.mkdir(parents=True, exist_ok=True)
    target_abs = str(stage / "report.txt")

    Path(ESCAPE_PATH).unlink(missing_ok=True)
    before = snapshot(target_abs)

    try:
        out = SCENARIOS[name](stage, target_abs)
        error = None
    except Exception as e:  # noqa: BLE001
        out = {"result": None, "attack_landed": None, "diverted_field": None,
              "server_refused": None}
        error = f"{type(e).__name__}: {e}"

    staged_after = snapshot(target_abs)
    verdicts = check_properties(rung, before, staged_after)
    decision = decide(verdicts)

    committed = staged_after if decision == "commit" else before
    o = oracle(before, committed)

    return {"scenario": name, "rung": rung, "server_error": error,
            "server_refused_call": out.get("server_refused"),
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

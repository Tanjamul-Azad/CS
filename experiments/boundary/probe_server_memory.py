"""
Runs INSIDE the container: the third real-server datapoint for M3
(docs/29), and the first on a genuinely different workflow shape. The
first two datapoints (domdomegg/filesystem-mcp, @modelcontextprotocol/
server-filesystem) are both "one file, one path, free-text content" --
the EXACT class from docs/27. `@modelcontextprotocol/server-memory` is a
KEYED, STRUCTURED store: `create_entities(entities: [{name, entityType,
observations[]}])` appends typed, named records to a JSON-lines knowledge
graph. Schema verified live (inspect_server.py), not assumed.

WHY THIS ATTACK IS APPLIED MANUALLY, NOT VIA TamperingProxy.
`TamperingProxy._pick_target` (src/mcpmut/proxy.py) only inspects
TOP-LEVEL string-valued arguments. `create_entities`'s only top-level
argument is `entities`, an ARRAY of objects -- not a string -- so
`_pick_target` finds nothing to divert and the proxy forwards the call
honestly, unmodified. This is not a server defense; it is a real, worth-
stating limit of the existing top-level-field-substitution instrument:
it does not reach one level into a nested/structured argument. Rather than
silently working around this by picking a different tool, the identity
("name") and content ("observations") diversions below are applied by
hand, using the SAME diversion primitive TamperingProxy itself uses
(`_divert_value` -- an attacker-controlled value sharing no token with
the original) and the SAME response-laundering primitive (`_substitute`),
so the attack is methodologically the same MITM-proxy tampering used
everywhere else in this project, just reaching one level deeper than the
current automatic instrument can.

STORAGE PATH. The server's default `memory.jsonl` path is relative to
its OWN installed module directory, not to any `cwd` this probe controls
-- confirmed by reading the installed package's `dist/index.js` directly
(`defaultMemoryPath = path.join(dirname(import.meta.url), 'memory.jsonl')`).
It reads `MEMORY_FILE_PATH` from the environment (absolute, or resolved
against that same module directory if relative) -- verified in the same
source read, not assumed. Each trial sets a per-trial-and-rung
`MEMORY_FILE_PATH` for isolation, exactly as the filesystem probes use a
per-trial directory.

LADDER, reinterpreted for a keyed store rather than a path (see docs/24
§5's ENUM/SNAP framing for exactly this class of tool):

    L1  destination (identity) only   the record exists under the
                                        APPROVED name, not a diverted one
    L2  + structure                    entityType and observations are
                                        present and non-empty
    L3  + content                      observations exactly match the
                                        approved list
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, "/app/src")

from mcpmut.live import LiveSession  # noqa: E402
from mcpmut.proxy import _divert_value, _substitute  # noqa: E402

OBSERVATION = "quarterly numbers"
ENTITY_TYPE = "report"

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"


def snapshot(call, target_name: str, escape_name: str) -> dict:
    """SNAP read-back (docs/24 §5): query both the approved identity and
    the known escape identity by name, exactly as an ENUM/keyed-getter
    check would."""
    graph = call("open_nodes", {"names": [target_name, escape_name]})
    by_name = {e["name"]: e for e in graph.get("entities", [])}
    return {"target": by_name.get(target_name), "escape": by_name.get(escape_name)}


def check_properties(rung: str, before: dict, after: dict) -> dict:
    v: dict[str, str] = {}
    escape_changed = before["escape"] != after["escape"]
    v["destination"] = FAIL if escape_changed else PASS
    v["frame_intact"] = v["destination"]

    if rung == "L1":
        v["structure"] = UNKNOWN
        v["content"] = UNKNOWN
        return v

    t = after["target"]
    v["structure"] = PASS if (t and t.get("entityType") and t.get("observations")) else FAIL
    if rung == "L2":
        v["content"] = UNKNOWN
        return v

    v["content"] = PASS if (t and t.get("observations") == [OBSERVATION]) else FAIL
    return v


def decide(verdicts: dict) -> str:
    return "discard" if FAIL in verdicts.values() else "commit"


def oracle(before: dict, after: dict) -> dict:
    unauthorized = []
    if before["escape"] != after["escape"]:
        unauthorized.append("escape identity changed without approval")
    t = after["target"]
    if t is not None and t.get("observations") != [OBSERVATION]:
        unauthorized.append("approved entity holds unapproved observations")
    authorized = bool(t and t.get("observations") == [OBSERVATION]) and not unauthorized
    return {"authorized_effect": bool(authorized),
            "unauthorized_effect": bool(unauthorized),
            "oracle_findings": unauthorized,
            "no_change": after == before}


def command_and_env(stage: Path):
    mem_path = str(stage / "memory.jsonl")
    return "npx -y @modelcontextprotocol/server-memory", {"MEMORY_FILE_PATH": mem_path}


def run_honest(stage: Path, target_name: str, escape_name: str) -> dict:
    cmd, env = command_and_env(stage)
    with LiveSession(cmd, cwd=str(stage), env=env) as s:
        result = s.call("create_entities", {"entities": [
            {"name": target_name, "entityType": ENTITY_TYPE, "observations": [OBSERVATION]}]})
        errored = s.last_was_error
    return {"result": result, "attack_landed": None, "diverted_field": None,
            "server_refused": errored}


def run_name_diversion(stage: Path, target_name: str, escape_name: str) -> dict:
    """Manual analog of path_diversion: the proxy substitutes the entity's
    NAME with `_divert_value`'s standard attacker-controlled value, then
    launders the response with `_substitute` so a passive client sees the
    approved name in the reply -- the same MITM shape TamperingProxy
    applies to a top-level string field, one level deeper."""
    diverted = _divert_value(target_name)
    assert diverted == escape_name, "escape_name must match _divert_value's output"
    cmd, env = command_and_env(stage)
    with LiveSession(cmd, cwd=str(stage), env=env) as s:
        real_result = s.call("create_entities", {"entities": [
            {"name": diverted, "entityType": ENTITY_TYPE, "observations": [OBSERVATION]}]})
        errored = s.last_was_error
    laundered = _substitute(copy.deepcopy(real_result), diverted, target_name)
    return {"result": laundered, "attack_landed": True, "diverted_field": "name",
            "server_refused": errored}


def run_observation_substitution(stage: Path, target_name: str, escape_name: str) -> dict:
    """Content-level tamper: identity untouched, observations swapped."""
    cmd, env = command_and_env(stage)
    with LiveSession(cmd, cwd=str(stage), env=env) as s:
        result = s.call("create_entities", {"entities": [
            {"name": target_name, "entityType": ENTITY_TYPE,
             "observations": ["ATTACKER-CONTROLLED PAYLOAD"]}]})
        errored = s.last_was_error
    return {"result": result, "attack_landed": True, "diverted_field": "observations",
            "server_refused": errored}


SCENARIOS = {"honest": run_honest, "name_diversion": run_name_diversion,
            "observation_substitution": run_observation_substitution}


def trial(name: str, rung: str) -> dict:
    stage = Path(f"/sandbox/mem_{name}_{rung}")
    stage.mkdir(parents=True, exist_ok=True)
    target_name = f"{name}_{rung}_target"
    escape_name = _divert_value(target_name)

    cmd, env = command_and_env(stage)
    try:
        with LiveSession(cmd, cwd=str(stage), env=env) as s:
            before = snapshot(s.call, target_name, escape_name)
    except Exception as e:  # noqa: BLE001
        before = {"target": None, "escape": None}

    try:
        out = SCENARIOS[name](stage, target_name, escape_name)
        error = None
    except Exception as e:  # noqa: BLE001
        out = {"result": None, "attack_landed": None, "diverted_field": None,
              "server_refused": None}
        error = f"{type(e).__name__}: {e}"

    try:
        with LiveSession(cmd, cwd=str(stage), env=env) as s:
            staged_after = snapshot(s.call, target_name, escape_name)
    except Exception as e:  # noqa: BLE001
        staged_after = {"target": None, "escape": None}

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

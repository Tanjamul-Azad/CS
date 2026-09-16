"""
Runs INSIDE the container: the sixth real-server datapoint for M3
(docs/29) -- a REPLICATION, not just another server. `mcp-sqlite-server`
(docs/29 §4) already showed the UNDERSPECIFIED class resists the ladder
almost entirely. This is a SECOND, independent implementation of the same
class -- `mcp-server-sqlite-npx` (`npx -y mcp-server-sqlite-npx <db>`) --
run to answer a sharper question than "does the finding hold on one
server": does it hold across independent implementations of the same
underspecified shape, or was the first result an artifact of that one
package's particular design?

SCHEMA, verified live, genuinely different shape from the first SQLite
server even though the CLASS is the same: `write_query(query: string)`,
`read_query(query: string)`, `create_table(query: string)`. No `db`
argument (the database path is fixed once at launch, via CLI arg) and no
`readonly` toggle -- write access is simply always on for `write_query`.
Still exactly the UNDERSPECIFIED class from docs/27: a single opaque SQL
string carrying destination, structure and content all mixed together,
with no schema-derivable boundary between them -- if anything, less
structure than the first server (no `readonly` flag to even key a
distinction on).

Same design as `probe_sqlite.py`: L1 is the only rung run (L2/L3 are
`N/A`, not `UNKNOWN`, for the identical reason -- no schema-derivable
check exists for those properties on this tool at all). Both attacks are
hand-authored SQL, since no schema-derived proxy could formulate them
without parsing SQL, same as the first server.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "/app/src")

from mcpmut.live import LiveSession  # noqa: E402
from mcpmut.proxy import _divert_value  # noqa: E402

OBSERVATION = "quarterly numbers"

PASS, FAIL, UNKNOWN, NA = "PASS", "FAIL", "UNKNOWN", "N/A"


def _sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "", name)


def read_content(call, name: str) -> str | None:
    """Verified live (not assumed): a match returns
    `[{"content": "..."}]`, no match returns `[]` -- already parsed JSON,
    not text, because LiveSession.call() parses any body that is valid
    JSON."""
    safe = _sanitize(name)
    rows = call("read_query", {"query": f"SELECT content FROM reports WHERE name = '{safe}'"})
    if isinstance(rows, list) and rows:
        return rows[0].get("content")
    return None


def bootstrap(call) -> None:
    call("create_table", {"query": "CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY, name TEXT UNIQUE, content TEXT)"})


def check_properties(before: dict, after: dict) -> dict:
    v: dict[str, str] = {}
    escape_changed = before["escape_content"] != after["escape_content"]
    v["destination"] = FAIL if escape_changed else PASS
    v["frame_intact"] = v["destination"]
    v["structure"] = NA
    v["content"] = NA
    return v


def decide(verdicts: dict) -> str:
    return "discard" if FAIL in verdicts.values() else "commit"


def oracle(before: dict, after: dict) -> dict:
    unauthorized = []
    if before["escape_content"] != after["escape_content"]:
        unauthorized.append("escape row holds content without approval")
    if after["target_content"] not in (None, OBSERVATION):
        unauthorized.append("approved row holds unapproved content")
    authorized = after["target_content"] == OBSERVATION and not unauthorized
    return {"authorized_effect": bool(authorized),
            "unauthorized_effect": bool(unauthorized),
            "oracle_findings": unauthorized,
            "no_change": after == before}


def command_for(stage: Path) -> str:
    return f"npx -y mcp-server-sqlite-npx {stage / 'reports.db'}"


def snapshot(call, target_name: str, escape_name: str) -> dict:
    return {"target_content": read_content(call, target_name),
            "escape_content": read_content(call, escape_name)}


def run_honest(stage: Path, target_name: str, escape_name: str) -> dict:
    with LiveSession(command_for(stage), cwd=str(stage)) as s:
        bootstrap(s.call)
        sql = f"INSERT INTO reports(name, content) VALUES ('{target_name}', '{OBSERVATION}')"
        result = s.call("write_query", {"query": sql})
        errored = s.last_was_error
    return {"result": result, "attack_landed": None, "diverted_field": None, "server_refused": errored}


def run_row_diversion(stage: Path, target_name: str, escape_name: str) -> dict:
    with LiveSession(command_for(stage), cwd=str(stage)) as s:
        bootstrap(s.call)
        sql = f"INSERT INTO reports(name, content) VALUES ('{escape_name}', '{OBSERVATION}')"
        result = s.call("write_query", {"query": sql})
        errored = s.last_was_error
    return {"result": result, "attack_landed": True, "diverted_field": "sql(row identity)", "server_refused": errored}


def run_content_substitution(stage: Path, target_name: str, escape_name: str) -> dict:
    with LiveSession(command_for(stage), cwd=str(stage)) as s:
        bootstrap(s.call)
        sql = f"INSERT INTO reports(name, content) VALUES ('{target_name}', 'ATTACKER-CONTROLLED PAYLOAD')"
        result = s.call("write_query", {"query": sql})
        errored = s.last_was_error
    return {"result": result, "attack_landed": True, "diverted_field": "sql(content)", "server_refused": errored}


SCENARIOS = {"honest": run_honest, "row_diversion": run_row_diversion,
            "content_substitution": run_content_substitution}


def trial(name: str) -> dict:
    stage = Path(f"/sandbox/sqlite2_{name}")
    stage.mkdir(parents=True, exist_ok=True)
    target_name = _sanitize(f"{name}_target")[:20]
    escape_name = _sanitize(_divert_value(target_name))[:20]

    try:
        with LiveSession(command_for(stage), cwd=str(stage)) as s:
            bootstrap(s.call)
            before = snapshot(s.call, target_name, escape_name)
    except Exception:  # noqa: BLE001
        before = {"target_content": None, "escape_content": None}

    try:
        out = SCENARIOS[name](stage, target_name, escape_name)
        error = None
    except Exception as e:  # noqa: BLE001
        out = {"result": None, "attack_landed": None, "diverted_field": None, "server_refused": None}
        error = f"{type(e).__name__}: {e}"

    try:
        with LiveSession(command_for(stage), cwd=str(stage)) as s:
            after = snapshot(s.call, target_name, escape_name)
    except Exception:  # noqa: BLE001
        after = {"target_content": None, "escape_content": None}

    verdicts = check_properties(before, after)
    decision = decide(verdicts)
    committed = after if decision == "commit" else before
    o = oracle(before, committed)

    return {"scenario": name, "rung": "L1", "server_error": error,
            "server_refused_call": out.get("server_refused"),
            "server_response": out.get("result"),
            "attack_landed_per_proxy": out.get("attack_landed"),
            "diverted_field": out.get("diverted_field"),
            "staged_before": before, "staged_after": after,
            "verdicts": verdicts, "decision": decision,
            "committed_state": committed, **o}


def main() -> None:
    rows = [trial(name) for name in SCENARIOS]
    print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()

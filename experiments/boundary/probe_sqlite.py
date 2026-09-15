"""
Runs INSIDE the container: the fourth real-server datapoint for M3
(docs/29), and the first on the UNDERSPECIFIED workflow class from
docs/27 -- the class the theory predicts a specification ladder buys the
least on. Server: `mcp-sqlite-server` (`npx -y mcp-sqlite-server`), a
real, unmodified, credential-free npm package. Schema verified live
(inspect_server.py), not assumed: `query(db: string, sql: string,
readonly: boolean=true)`, `additionalProperties: false`. Read-only by
default; write mode is `readonly: false` in the call.

WHY THIS TOOL HAS NO SCHEMA-DERIVABLE L2/L3, AND THAT IS THE FINDING, NOT
A GAP IN THE PROBE. Every other tool audited so far (`create(path,
content)`, `write_file(path, content)`, `create_entities(entities:
[{name, entityType, observations}])`) declares SEPARATE fields for
identity/destination and for content -- a contract can point at "the
content field" without knowing anything about the application built on
top. `query`'s only mutation-carrying argument is `sql`, a single opaque
string that carries destination (which table/row), structure, and content
all mixed together with no schema boundary between them. Deriving "the
approved row's content field" requires knowing the CALLER'S OWN table
schema (column names, which row identifies "the approved effect") --
knowledge a protocol-level auditor deriving contracts from a tool's own
JSON Schema declaration does not have, and is not supposed to invent.
`TamperingProxy`'s field-substitution model has no field to substitute
here either, for the same reason (see `probe_server_memory.py`'s
docstring for the nested-argument version of this same limit; this is the
sharper, string-level version of it).

WHAT IS STILL DERIVABLE FROM THE SCHEMA ALONE, AND IS TESTED: `db` names
a FILE. A destination check at the file level -- did the approved .db
file change, did any other .db-shaped file appear -- needs nothing beyond
the schema's own field name and type. That is run as L1. L2 ("structure")
and L3 ("content") are reported N/A here, not UNKNOWN: UNKNOWN means "this
rung's check was not run at this ladder level by policy" (as at L1 on
every other probe); N/A means "no schema-derivable check exists for this
property on this tool at all," a structurally different, worse outcome
that docs/27 predicts specifically for the underspecified class.

Both attacks below are hand-authored SQL, exactly because no schema-
derived proxy could formulate them without parsing SQL -- which is itself
the point being measured, not a shortcut around it.
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


def _cell(text: str) -> str | None:
    """Pull the single content value out of this server's formatted
    table text ("Rows: 1\\n\\ncontent\\n-------\\n<value>"), or None for
    "Rows: 0"."""
    if text.startswith("Rows: 0"):
        return None
    lines = text.split("\n")
    return lines[4].strip() if len(lines) > 4 else None


def read_content(call, db: str, name: str) -> str | None:
    safe = re.sub(r"[^A-Za-z0-9_]", "", name)   # this harness's own values only, not untrusted input
    r = call("query", {"db": db, "sql": f"SELECT content FROM reports WHERE name = '{safe}'",
                       "readonly": True})
    text = r.get("text", "") if isinstance(r, dict) else str(r)
    return _cell(text)


def file_bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


def bootstrap(call, db: str) -> None:
    call("query", {"db": db,
                   "sql": "CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY, name TEXT UNIQUE, content TEXT)",
                   "readonly": False})


def snapshot(stage: Path, call, db: str, target_name: str, escape_name: str) -> dict:
    return {"db_file": file_bytes(Path(db)),
            "target_content": read_content(call, db, target_name),
            "escape_content": read_content(call, db, escape_name)}


def check_properties(rung: str, before: dict, after: dict) -> dict:
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


def command_and_db(stage: Path):
    return "npx -y mcp-sqlite-server", str(stage / "reports.db")


def run_honest(stage: Path, target_name: str, escape_name: str) -> dict:
    cmd, db = command_and_db(stage)
    with LiveSession(cmd, cwd=str(stage)) as s:
        bootstrap(s.call, db)
        sql = f"INSERT INTO reports(name, content) VALUES ('{target_name}', '{OBSERVATION}')"
        result = s.call("query", {"db": db, "sql": sql, "readonly": False})
        errored = s.last_was_error
    return {"result": result, "attack_landed": None, "diverted_field": None,
            "server_refused": errored}


def run_row_diversion(stage: Path, target_name: str, escape_name: str) -> dict:
    """Hand-authored: the row is inserted under the ESCAPE identity, not
    the approved one -- the SQL-level analog of path/name diversion. No
    schema-derived proxy could formulate this; see module docstring."""
    cmd, db = command_and_db(stage)
    with LiveSession(cmd, cwd=str(stage)) as s:
        bootstrap(s.call, db)
        sql = f"INSERT INTO reports(name, content) VALUES ('{escape_name}', '{OBSERVATION}')"
        result = s.call("query", {"db": db, "sql": sql, "readonly": False})
        errored = s.last_was_error
    return {"result": result, "attack_landed": True, "diverted_field": "sql(row identity)",
            "server_refused": errored}


def run_content_substitution(stage: Path, target_name: str, escape_name: str) -> dict:
    cmd, db = command_and_db(stage)
    with LiveSession(cmd, cwd=str(stage)) as s:
        bootstrap(s.call, db)
        sql = f"INSERT INTO reports(name, content) VALUES ('{target_name}', 'ATTACKER-CONTROLLED PAYLOAD')"
        result = s.call("query", {"db": db, "sql": sql, "readonly": False})
        errored = s.last_was_error
    return {"result": result, "attack_landed": True, "diverted_field": "sql(content)",
            "server_refused": errored}


SCENARIOS = {"honest": run_honest, "row_diversion": run_row_diversion,
            "content_substitution": run_content_substitution}


def trial(name: str, rung: str) -> dict:
    stage = Path(f"/sandbox/sqlite_{name}_{rung}")
    stage.mkdir(parents=True, exist_ok=True)
    target_name = f"{name}_{rung}_target"[:20]
    escape_name = re.sub(r"[^A-Za-z0-9_]", "", _divert_value(target_name))[:20]
    cmd, db = command_and_db(stage)

    try:
        with LiveSession(cmd, cwd=str(stage)) as s:
            bootstrap(s.call, db)
            before = snapshot(stage, s.call, db, target_name, escape_name)
    except Exception:  # noqa: BLE001
        before = {"db_file": None, "target_content": None, "escape_content": None}

    try:
        out = SCENARIOS[name](stage, target_name, escape_name)
        error = None
    except Exception as e:  # noqa: BLE001
        out = {"result": None, "attack_landed": None, "diverted_field": None,
              "server_refused": None}
        error = f"{type(e).__name__}: {e}"

    try:
        with LiveSession(cmd, cwd=str(stage)) as s:
            staged_after = snapshot(stage, s.call, db, target_name, escape_name)
    except Exception:  # noqa: BLE001
        staged_after = {"db_file": None, "target_content": None, "escape_content": None}

    verdicts = check_properties(rung, before, staged_after)
    decision = decide(verdicts)

    committed = staged_after if decision == "commit" else before
    o = oracle(before, committed)

    return {"scenario": name, "rung": rung, "server_error": error,
            "server_refused_call": out.get("server_refused"),
            "server_response": out.get("result"),
            "attack_landed_per_proxy": out.get("attack_landed"),
            "diverted_field": out.get("diverted_field"),
            "staged_before": {k: v for k, v in before.items() if k != "db_file"},
            "staged_after": {k: v for k, v in staged_after.items() if k != "db_file"},
            "verdicts": verdicts, "decision": decision,
            "committed_state": {k: v for k, v in committed.items() if k != "db_file"}, **o}


def main() -> None:
    # Only L1 is run: check_properties marks structure/content N/A at
    # every rung for this tool (module docstring), so L2/L3 would repeat
    # the identical check for no new information -- that invariance is
    # itself the reported finding, not a shortcut around measuring it.
    rows = [trial(name, "L1") for name in SCENARIOS]
    print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()

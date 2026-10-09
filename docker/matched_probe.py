"""In-container driver for one matched trial.

Launches one frozen server and performs its honest workflow. All tampering is
performed by the interposition shims (selected by MCPGATE_TAMPER in the
environment), so the calls this driver issues are always the approved ones and
the request the server receives is honest. The only request-level variations
are A3 (an unlisted extra field) and A5 (replaying the identical call), which
are protocol-level by definition and cannot be realized by interposition.

The driver never decides security outcomes. It prints the responses and the
paths it observed; the trusted host determines outcomes from its own snapshot
after this process and all descendants have exited.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, "/app/src")
from mcpmut.live import LiveSession  # noqa: E402

ROOT = Path("/sandbox")

# --- third held-out batch (workstream H): servers with no hand-written
# workload fall back to a schema-derived honest write. The call is built here
# from the server's own published input schema, by the same rule the network
# selection uses, before any attack or defense outcome is observed. The
# derivation is a pure function of that schema, so the honest exemplar is
# identical whether it is computed in-container from the live session or
# host-side from the frozen eligibility record (session is None). ---

_WRITE_VERBS = frozenset(
    "create send post add update write set insert publish upload comment reply "
    "submit schedule book save store edit append log remember notify message "
    "invite assign label tag star track ingest record put".split())
_DESTRUCTIVE = frozenset(
    "delete remove destroy drop purge cancel clear reset wipe".split())
_PATH_RE = re.compile(r"(path|file|filename|filepath|dir|directory|output|dest|location)", re.I)
_CONTENT_RE = re.compile(r"(content|body|text|message|description|note|comment|value|"
                         r"data|summary|memo|entry|detail|answer|markdown)", re.I)
_TITLE_RE = re.compile(r"(title|name|label|subject|topic|heading)", re.I)
_TODAY = _dt.date.today().isoformat()


def _schema_type(schema: dict) -> str | None:
    kind = schema.get("type")
    if isinstance(kind, list):
        kind = next((k for k in kind if k != "null"), None)
    return kind


def _value_for(name: str, schema: dict, depth: int = 0):
    """Structural default for one field (ported from network selection)."""
    if depth > 3:
        return None
    if schema.get("enum"):
        return schema["enum"][0]
    for key in ("anyOf", "oneOf"):
        if key in schema:
            options = [s for s in schema[key] if s.get("type") != "null"]
            if options:
                return _value_for(name, options[0], depth + 1)
    kind = _schema_type(schema)
    low = name.lower()
    if kind == "integer":
        return max(1, int(schema.get("minimum", 1)))
    if kind == "number":
        return max(1.0, float(schema.get("minimum", 1)))
    if kind == "boolean":
        return False
    if kind == "array":
        item = _value_for(name.rstrip("s"), schema.get("items") or {"type": "string"}, depth + 1)
        return [] if item is None else [item]
    if kind == "object":
        return _args_for(schema, depth + 1)
    fmt = schema.get("format", "")
    if fmt == "email" or "email" in low:
        return "alice@example.org"
    if fmt in ("uri", "url") or low.endswith("url") or "link" in low:
        return "https://example.org/report"
    if fmt == "date" or low.endswith("date"):
        return _TODAY
    if fmt == "date-time" or "time" in low:
        return f"{_TODAY}T10:00:00Z"
    if low.endswith(("id", "_id", "ids")):
        return "12345"
    if _TITLE_RE.search(low):
        return "Quarterly totals"
    if _CONTENT_RE.search(low) or low in ("query", "prompt"):
        return "Hello team, the Q3 totals are below."
    return "example value"


def _args_for(schema: dict, depth: int = 0) -> dict:
    props = schema.get("properties") or {}
    out = {}
    for name in schema.get("required") or []:
        value = _value_for(name, props.get(name, {}), depth)
        if value is not None:
            out[name] = value
    return out


def _is_string_field(spec: dict) -> bool:
    return _schema_type(spec) in (None, "string") and not spec.get("enum")


def _tokens(name: str) -> set[str]:
    """snake_case and camelCase name split into lowercase word tokens."""
    return set(re.findall(r"[a-z]+", re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()))


def _opaque_field(name: str, spec: dict) -> bool:
    """A field that must not be filled with free marker text (path/url/id)."""
    low = name.lower()
    fmt = spec.get("format", "")
    return bool(_PATH_RE.search(low) or low.endswith(("id", "_id", "ids", "url"))
                or "link" in low or "email" in low or fmt in ("uri", "url", "email"))


def _schema_sequence(tools: list[dict], marker: str, content: str):
    """Pick the first write-like tool and build a marker-bearing honest call.

    A client-area path is placed in any path-like field and the marker content
    in any content- or title-like field, so the honest effect lands under
    /sandbox and is detectable. Everything else takes the schema's structural
    default. A tool with no write verb in its name, or no free-text field to
    carry the marker, raises; the server is then recorded as excluded by the
    honest-workflow step rather than forced into this oracle.
    """
    tool = None
    for candidate in tools:
        name = candidate.get("name", "")
        ann = candidate.get("annotations") or {}
        if ann.get("readOnlyHint") is True or ann.get("destructiveHint") is True:
            continue
        tokens = _tokens(name)
        if tokens & _DESTRUCTIVE:
            continue
        if tokens & _WRITE_VERBS:
            tool = candidate
            break
    if tool is None:
        raise ValueError("no write-like tool in tools/list")
    schema = tool.get("inputSchema") or {}
    props = schema.get("properties") or {}
    required = schema.get("required") or []
    args = _args_for(schema)
    marked = False
    for name, spec in props.items():
        if not _is_string_field(spec):
            continue
        low = name.lower()
        if _PATH_RE.search(low):
            # a "filename" field wants a bare basename (the server joins it to
            # its own client-configured directory); a "path"/"dir" field wants
            # an absolute client-area path
            bare = "name" in low and "path" not in low
            args[name] = "report.txt" if bare else "/sandbox/report.txt"
        elif _CONTENT_RE.search(low):
            args[name] = content
            marked = True
        elif _TITLE_RE.search(low) and name in required:
            args[name] = f"matched report {marker}"
            marked = True
    if not marked:
        # no named content or title field; carry the marker in the first
        # required free-text field that is not a path, url, or identifier
        for name in required:
            spec = props.get(name, {})
            if _is_string_field(spec) and not _opaque_field(name, spec):
                args[name] = content
                marked = True
                break
    if not marked:
        raise ValueError(f"no free-text field to carry the marker in {tool['name']}")
    return [(tool["name"], args)]


def _recorded_tools(server_id: str) -> list[dict]:
    """tools/list recorded at eligibility time, for the host-side exemplar."""
    repo = Path(__file__).resolve().parents[1]
    for rel in ("artifact/results/batch3_eligibility.json",
                "artifact/results/batch2_eligibility.json"):
        path = repo / rel
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data.get("rows", []):
            if (row.get("candidate") or {}).get("id") == server_id:
                return (row.get("probe") or {}).get("tools") or []
    raise ValueError(f"no recorded tools/list for {server_id}")


def workload(server_id: str, session: LiveSession, marker: str, content: str):
    """The approved honest tool sequence for one server.

    Returns a list of (tool, arguments). Setup calls that create a working
    context (an index connection, a project directory) are included because
    they are part of the honest workflow, not the audited effect.
    """
    if server_id == "io.github.Oncorporation/filesystem-server":
        return [("write_file", {"file_path": "/sandbox/report.txt", "content": content})]
    if server_id == "io.github.bytedance/mcp-server-filesystem":
        return [("write_file", {"path": "/sandbox/report.txt", "content": content})]
    if server_id == "io.github.aayoawoyemi/ori-memory":
        return [("ori_add", {"title": content, "type": "insight"})]
    if server_id == "io.github.Octonove/crbro-memory":
        return [
            ("crbro_boot", {}),
            ("crbro_learn", {"type": "fact", "content": content,
                             "topic": "MCPGate Matched"}),
        ]
    if server_id == "ai.smartmemory/compose-mcp":
        return [("add_roadmap_entry", {"code": "MCPGATE-M1", "description": content,
                                       "phase": "Matched"})]
    if server_id == "io.github.DanielGuru/repomemory":
        return [("context_write", {"category": "facts", "filename": "mcpgate-matched",
                                   "content": content, "scope": "repo"})]
    if server_id == "io.github.mrfentmen/document-generator-mcp":
        return [("create_doc", {"title": "MCPGate Matched", "body": content,
                                "filename": "evidence.docx"})]
    # --- second held-out batch (workstream G); written from each server's
    # tools/list schema before any attack or defense outcome was observed ---
    if server_id == "io.github.oborchers/tablestakes":
        return [("create_table", {"file_path": "/sandbox/tables.md",
                                  "content": "| name | value |\n| --- | --- |\n| item | "
                                             + content + " |"})]
    if server_id == "io.github.ionasrobert/tacitus-mcp-server":
        return [("create_note", {"note_id": "matched-report", "content": content})]
    if server_id == "io.github.jackdark425/aigroup-mdtoword-mcp":
        return [("markdown_to_docx", {"filename": "report.docx",
                                      "markdown": "# Report\n\n" + content,
                                      "outputPath": "/sandbox/report.docx"})]
    if server_id == "io.github.praveen-ilangovan/pensieve":
        return [("create_stream", {"name": "research"}),
                ("add_note", {"stream": "research", "text": content})]
    if server_id == "io.github.Srishesh-Archik/dyer-md":
        return [("create_note", {"title": "Matched Report", "content": content})]
    if server_id == "io.github.sfrangulov/minirag-mcp":
        return [("ingest_data", {"data": content, "source": "matched-report"})]
    if server_id == "io.github.Cloto-dev/cpersona":
        return [("store", {"agent_id": "matched-agent",
                           "message": {"role": "user", "content": content}})]
    # third held-out batch (workstream H): no hand-written workload; derive an
    # honest write from the server's published tools/list schema
    tools = session.list_tools() if session is not None else _recorded_tools(server_id)
    return _schema_sequence(tools, marker, content)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-id", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--marker", required=True)
    parser.add_argument("--content", required=True)
    parser.add_argument("--extra-field", default=None,
                        help="A3: add this unlisted field to the last write call")
    parser.add_argument("--replay", type=int, default=1,
                        help="A5: submit the final write call this many times")
    parser.add_argument("--audit", action="store_true",
                        help="MBA: run the response auditor with live read-backs")
    parser.add_argument("--args-json", default=None,
                        help="template runs: JSON object replacing the audited "
                             "(last) call's arguments")
    parser.add_argument("--dump-schema", action="store_true",
                        help="record the input schema of every workload tool")
    parser.add_argument("--check-paths", default=None,
                        help="comma-separated container paths whose existence is "
                             "reported after the server has exited")
    args = parser.parse_args()

    (ROOT / "home").mkdir(parents=True, exist_ok=True)
    env = {"HOME": "/sandbox/home", "PATH": "/usr/local/bin:/usr/bin:/bin"}
    for name in ("NODE_OPTIONS", "PYTHONPATH", "MCPGATE_TAMPER",
                 "MCPGATE_TAMPER_TIER", "MCPGATE_TAMPER_ROOT",
                 "MCPGATE_TAMPER_PAYLOAD", "MCPGATE_TAMPER_SYMLINK",
                 "MCPGATE_TAMPER_MARKER", "MCPGATE_TAMPER_ESCAPE",
                 "MCPGATE_TAMPER_COVERT", "MCPGATE_TAMPER_INJECT_RE"):
        if name in os.environ:
            env[name] = os.environ[name]
    # Honest per-server setup: point servers whose write destination is a
    # client-configured directory at the client-selected /sandbox area, so the
    # audited effect is a client-selected local file (the destination-integrity
    # premise), the same spirit as the `ori init` and `.compose` setup below.
    if args.server_id == "io.github.GigantesHJI/securedact-mcp":
        env["SECUREDACT_SAFE_COPY_DIR"] = "/sandbox"

    row = {"server_id": args.server_id, "command": args.command,
           "marker": args.marker, "calls": []}
    start = time.perf_counter()
    try:
        if args.server_id == "io.github.aayoawoyemi/ori-memory":
            subprocess.run(["ori", "init", "/sandbox"], cwd=ROOT,
                           env={**os.environ, **env}, capture_output=True,
                           text=True, timeout=30, check=False)
        if args.server_id == "ai.smartmemory/compose-mcp":
            (ROOT / ".compose").mkdir(exist_ok=True)
        auditor = None
        with LiveSession(args.command, cwd=ROOT, env=env) as session:
            if args.audit:
                try:
                    from mcpaudit.auditor import Auditor
                    auditor = Auditor.from_mcp_tools(
                        session.list_tools(), server_id=args.server_id)
                    row["auditor_coverage"] = auditor.coverage().summary()
                except Exception as error:  # noqa: BLE001
                    row["auditor_error"] = f"{type(error).__name__}: {error}"
            sequence = workload(args.server_id, session, args.marker, args.content)
            if args.args_json:
                tool, _ = sequence[-1]
                sequence = sequence[:-1] + [(tool, json.loads(args.args_json))]
            if args.dump_schema:
                wanted = {tool for tool, _ in sequence}
                row["tool_schemas"] = {
                    t["name"]: t.get("inputSchema", {})
                    for t in session.list_tools() if t.get("name") in wanted}
            alerts: list[str] = []
            for index, (tool, arguments) in enumerate(sequence):
                is_last = index == len(sequence) - 1
                call_args = dict(arguments)
                if is_last and args.extra_field:
                    call_args[args.extra_field] = "/sandbox/unapproved_via_extra.txt"
                repeats = args.replay if is_last else 1
                for _ in range(repeats):
                    if auditor is not None and is_last:
                        def call_fn(name, arguments, _s=session):
                            value = _s.call(name, arguments, _record_error=False)
                            # record the auditor's own read-backs: a response-level
                            # judge (workstream F) sees exactly this evidence
                            row.setdefault("auditor_calls", []).append(
                                {"tool": name, "arguments": arguments,
                                 "result": str(value)[:2000]})
                            return value
                        try:
                            auditor.before_call(tool, call_args, call_fn)
                            value = session.call(tool, call_args)
                            for alert in auditor.after_call(tool, call_args, value, call_fn):
                                alerts.append({"severity": alert.severity,
                                               "relation": alert.relation,
                                               "detail": alert.detail})
                        except Exception as error:  # noqa: BLE001
                            value = {"auditor_exception": f"{type(error).__name__}: {error}"}
                    else:
                        value = session.call(tool, call_args)
                    row["calls"].append({
                        "tool": tool, "arguments": call_args,
                        "is_error": session.last_was_error, "result": value,
                    })
                    if session.last_was_error and not is_last:
                        raise RuntimeError(f"setup call {tool} errored: {value!r}")
            row["alerts"] = alerts
        row["status"] = "DRIVER_OK"
        if args.check_paths:
            # the session has closed, so the server process has exited
            row["post_exists"] = {p: os.path.exists(p)
                                  for p in args.check_paths.split(",") if p}
    except BaseException as error:  # noqa: BLE001
        row["status"] = "DRIVER_FAILED"
        row["error"] = f"{type(error).__name__}: {error}"
        row["traceback_tail"] = traceback.format_exc()[-2000:]
    row["elapsed_seconds"] = round(time.perf_counter() - start, 6)
    _record_cgroup(row)
    print(json.dumps(row, ensure_ascii=False, sort_keys=True))
    return 0 if row["status"] == "DRIVER_OK" else 1


def _record_cgroup(row):
    """Whole-container CPU and peak memory from cgroup v2 accounting.

    This is reliable across the MCP async-subprocess boundary, unlike
    getrusage on this process, and reflects the full per-invocation cost of the
    server plus the harness inside the container.
    """
    try:
        with open("/sys/fs/cgroup/memory.peak") as handle:
            row["container_peak_mem_bytes"] = int(handle.read().strip())
    except Exception:  # noqa: BLE001
        pass
    try:
        with open("/sys/fs/cgroup/cpu.stat") as handle:
            for line in handle:
                if line.startswith("usage_usec"):
                    row["container_cpu_seconds"] = int(line.split()[1]) / 1e6
                    break
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    raise SystemExit(main())

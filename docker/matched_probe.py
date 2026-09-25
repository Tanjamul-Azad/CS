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
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, "/app/src")
from mcpmut.live import LiveSession  # noqa: E402

ROOT = Path("/sandbox")


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
    raise ValueError(f"no matched workload for {server_id}")


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
    args = parser.parse_args()

    (ROOT / "home").mkdir(parents=True, exist_ok=True)
    env = {"HOME": "/sandbox/home", "PATH": "/usr/local/bin:/usr/bin:/bin"}
    for name in ("NODE_OPTIONS", "PYTHONPATH", "MCPGATE_TAMPER",
                 "MCPGATE_TAMPER_TIER", "MCPGATE_TAMPER_ROOT",
                 "MCPGATE_TAMPER_PAYLOAD", "MCPGATE_TAMPER_SYMLINK",
                 "MCPGATE_TAMPER_MARKER"):
        if name in os.environ:
            env[name] = os.environ[name]

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
                            return _s.call(name, arguments, _record_error=False)
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
    except BaseException as error:  # noqa: BLE001
        row["status"] = "DRIVER_FAILED"
        row["error"] = f"{type(error).__name__}: {error}"
        row["traceback_tail"] = traceback.format_exc()[-2000:]
    row["elapsed_seconds"] = round(time.perf_counter() - start, 6)
    print(json.dumps(row, ensure_ascii=False, sort_keys=True))
    return 0 if row["status"] == "DRIVER_OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())

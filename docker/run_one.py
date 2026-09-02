"""
Runs INSIDE the sandbox container: audit one real, unvetted MCP server.

Launches the server twice (fresh subprocess each time, so state does not
carry over): once honestly, once behind the declaration-driven tampering
proxy at L1. Both trials pick the SAME write tool, chosen by highest
relation degree among tools the auditor can actually check, and synthesize
its arguments from the declared inputSchema alone -- we do not know this
server's semantics, only what it advertises.

Writes one JSON result to --out. Never raises past main(): a broken or
hostile server must produce a result row explaining the failure, not take
down the whole scale run.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, "/app/src")

from mcpaudit import Auditor, Policy  # noqa: E402
from mcpmut.live import LiveSession  # noqa: E402
from mcpmut.proxy import TamperingProxy, attack_landed  # noqa: E402
from mcpmut.synth import synth_args  # noqa: E402
from measure.classify import is_read, is_write  # noqa: E402
from measure.extract import ExtractedTool  # noqa: E402


def _decl(t: dict) -> ExtractedTool:
    schema = t.get("inputSchema") or {}
    props = schema.get("properties", {}) if isinstance(schema, dict) else {}
    return ExtractedTool(name=t["name"], description=t.get("description", ""),
                         input_fields=list(props),
                         annotations=t.get("annotations") or {})


def choose_write_tool(tools: list[dict], auditor: Auditor) -> dict | None:
    """The write tool with the most derivable relations -- the one an
    audit has the best chance of actually being able to check."""
    writes = [t for t in tools if is_write(_decl(t))]
    if not writes:
        return None

    def degree(t: dict) -> int:
        _, deg = auditor._cls(t["name"])
        return deg

    writes.sort(key=degree, reverse=True)
    return writes[0] if degree(writes[0]) > 0 else writes[0]


def one_trial(command: str, cwd: str, tools: list[dict], write_tool: dict,
             args: dict, tampered: bool) -> dict:
    """Launch fresh, run one audited call, return what happened."""
    with LiveSession(command, cwd=cwd) as session:
        server = (TamperingProxy(inner=session.call,
                                 write_tools={t["name"] for t in tools if is_write(_decl(t))},
                                 read_tools={t["name"] for t in tools if is_read(_decl(t))},
                                 level=1)
                  if tampered else session)

        auditor = Auditor.from_mcp_tools(
            tools, server_id="live",
            policy=Policy(**{**Policy.default().__dict__, "audit_budget": 20.0}))

        def call_fn(name, a):
            return server.call(name, a)

        t0 = time.time()
        auditor.before_call(write_tool["name"], args, call_fn=call_fn)
        result = server.call(write_tool["name"], args)

        # The MCP protocol's own isError flag on the WRITE call itself. A
        # server that cannot really perform this action here (no live
        # iTerm2 session, a missing external dependency) often still
        # responds normally but with isError=True -- discarding that and
        # auditing anyway makes an environment limitation look exactly
        # like a defense failure: read-back finds nothing because nothing
        # was ever written, not because anyone hid it. Such a trial
        # measures nothing about the auditor and is excluded rather than
        # silently counted as a violation.
        write_errored = getattr(session, "last_was_error", False)

        alerts = auditor.after_call(write_tool["name"], args, result,
                                    call_fn=call_fn)
        elapsed = time.time() - t0

        violations = [a for a in alerts if a.severity == "violation"]
        out = {
            "elapsed_s": round(elapsed, 3),
            "probes": session.calls,
            "alerts": [str(a) for a in alerts],
            "violations": len(violations),
            "write_errored": write_errored,
        }
        if tampered:
            out["attack_landed"] = attack_landed(server.plans)
            out["diverted_field"] = (server.plans[-1].target_field
                                     if server.plans else None)
        return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server-id", required=True)
    ap.add_argument("--command", required=True)
    ap.add_argument("--cwd", default="/sandbox")
    ap.add_argument("--out", default="/out/result.json")
    args = ap.parse_args()

    result: dict = {"server_id": args.server_id, "command": args.command}

    try:
        t0 = time.time()
        with LiveSession(args.command, cwd=args.cwd) as probe:
            tools = probe.list_tools()
        result["list_tools_s"] = round(time.time() - t0, 3)
        result["tool_count"] = len(tools)

        auditor = Auditor.from_mcp_tools(tools, server_id="live")
        cov = auditor.coverage()
        result["coverage"] = cov.by_class

        write_tool = choose_write_tool(tools, auditor)
        if write_tool is None:
            result["status"] = "no_write_tool_found"
        else:
            result["write_tool"] = write_tool["name"]

            # Fresh arguments PER TRIAL. Both trials share the same mounted
            # sandbox directory across two separate subprocess launches, so
            # reusing one synthesized path/filename here means the honest
            # trial's file is still on disk when the tampered trial reads
            # back -- read_file finds the honest leftover and reports
            # "confirmed" even though the tampered write actually landed
            # somewhere else. That false negative is exactly the kind of
            # instrument bug this project keeps finding by running against
            # real things instead of assuming the harness is neutral.
            schema = write_tool.get("inputSchema") or {}

            try:
                result["honest"] = one_trial(
                    args.command, args.cwd, tools, write_tool,
                    synth_args(schema), tampered=False)
            except Exception as e:  # noqa: BLE001
                result["honest"] = {"error": f"{type(e).__name__}: {e}"}

            try:
                result["tampered"] = one_trial(
                    args.command, args.cwd, tools, write_tool,
                    synth_args(schema), tampered=True)
            except Exception as e:  # noqa: BLE001
                result["tampered"] = {"error": f"{type(e).__name__}: {e}"}

            result["status"] = "ok"

    except Exception as e:  # noqa: BLE001
        result["status"] = "failed"
        result["error"] = f"{type(e).__name__}: {e}"
        result["traceback"] = traceback.format_exc()[-2000:]

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=1, default=str),
                              encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "traceback"},
                     indent=1, default=str))


if __name__ == "__main__":
    main()

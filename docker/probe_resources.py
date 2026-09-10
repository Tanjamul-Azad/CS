"""
Runs INSIDE the sandbox container: ask one real MCP server what it exposes
on BOTH of its observation channels, and change nothing.

WHY THIS EXISTS. Every auditability number this project has published so
far -- the 69.7% A0 share, the class distribution, the live-audit
coverage -- was computed from `tools/list` alone. MCP has a second
channel. `resources/list` and `resources/read` let a client read server
state by URI, and `resources/templates/list` gives the parameterised form
(`file:///{path}`), which is the resource-channel equivalent of a read
tool that takes a key. A `write_file` with no sibling `read_file` tool is
currently scored A0 -- unverifiable at any budget -- even on a server
that publishes the written file as a readable resource. That tool is not
A0, and our headline number does not know it.

So this probe bounds the size of that error before anything else in the
new plan depends on it.

WHAT IT DOES NOT DO. It never calls a tool, never reads a resource body,
and never writes. It asks two list methods and exits. A read-only
capability query against a server that is already known to launch is the
cheapest possible way to answer a question that currently blocks the
E2 hand-labelling codebook (annotators cannot inspect a channel we never
captured).

WHAT ITS RESULT DOES NOT MEAN. A resource read is exactly as forgeable as
a tool response -- this widens the client's observation surface, not its
trust model, and Theorem 1 is untouched. "Resources recover X% of
verifiability" is an instrument-relative statement in precisely the same
way the tools-only number was, and must be written that way.

Writes one JSON result to --out. Never raises past main(): a broken or
hostile server must produce a row explaining the failure, not take down
the sweep.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, "/app/src")

from mcpmut.live import LiveSession  # noqa: E402


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
        with LiveSession(args.command, cwd=args.cwd) as session:
            tools = session.list_tools()
            res = session.list_resources()
        result["elapsed_s"] = round(time.time() - t0, 3)

        # Tools are recorded as names + input fields only. The full
        # declarations are already in the scale-run data; what this sweep
        # adds is the pairing question -- for each write tool, is there
        # anything on the RESOURCE side that could observe its effect --
        # and that needs the tool names next to the resource list, not a
        # second copy of every schema.
        result["tool_count"] = len(tools)
        result["tools"] = [
            {"name": t["name"],
             "input_fields": list((t.get("inputSchema") or {}).get("properties", {})),
             "readOnlyHint": (t.get("annotations") or {}).get("readOnlyHint")}
            for t in tools
        ]
        result["resources"] = res["resources"]
        result["templates"] = res["templates"]
        result["resource_count"] = len(res["resources"])
        result["template_count"] = len(res["templates"])
        result["resources_error"] = res["resources_error"]
        result["templates_error"] = res["templates_error"]
        # The distinction that matters for the paper: a server that
        # ANSWERED and has nothing is a real "no resource channel"
        # observation; one that refused the method is an unsupported
        # capability; one that failed for any other reason is neither and
        # must not be counted as either.
        if res["resources_error"] is None:
            result["resource_channel"] = "present" if res["resources"] or res["templates"] else "empty"
        else:
            result["resource_channel"] = "unsupported"
        result["status"] = "ok"

    except Exception as e:  # noqa: BLE001
        result["status"] = "failed"
        result["error"] = f"{type(e).__name__}: {e}"[:500]
        result["traceback"] = traceback.format_exc()[-1500:]

    Path(args.out).write_text(json.dumps(result, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()

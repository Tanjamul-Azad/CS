"""Inspect one candidate's MCP schema without invoking any tool effect."""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback

sys.path.insert(0, "/app/src")

from mcpmut.live import LiveSession  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-id", required=True)
    parser.add_argument("--command", required=True)
    args = parser.parse_args()

    row: dict[str, object] = {
        "server_id": args.server_id,
        "command": args.command,
        "effect_calls": 0,
    }
    started = time.perf_counter()
    try:
        with LiveSession(args.command, cwd="/sandbox") as session:
            tools = session.list_tools()
        row.update({
            "status": "TOOLS_LIST_OK",
            "tool_count": len(tools),
            "tools": tools,
        })
    except BaseException as error:  # one hostile package must not kill the batch
        row.update({
            "status": "FAILED",
            "error": f"{type(error).__name__}: {error}",
            "traceback_tail": traceback.format_exc()[-2000:],
        })
    row["elapsed_seconds"] = round(time.perf_counter() - started, 6)
    print(json.dumps(row, sort_keys=True, ensure_ascii=False))
    return 0 if row["status"] == "TOOLS_LIST_OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())


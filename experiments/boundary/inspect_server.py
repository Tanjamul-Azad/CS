"""
Runs INSIDE the container. Prints a real server's live tool schemas as
JSON so a probe's contract can be derived from what the server actually
declares, never assumed. Reusable across every real-server candidate in
the M3 sweep (see docs/29).

    python3 /app/boundary/inspect_server.py "npx -y <package> [args...]"
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, "/app/src")

from mcpmut.live import LiveSession  # noqa: E402


def main() -> None:
    command = sys.argv[1]
    with LiveSession(command, cwd="/sandbox") as s:
        tools = s.list_tools()
    print(json.dumps(tools, indent=1, default=str))


if __name__ == "__main__":
    main()

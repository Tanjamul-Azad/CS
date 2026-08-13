"""
mcpaudit CLI -- report what an MCP server actually admits being checked for.

    python -m mcpaudit scan --tools tools.json
    python -m mcpaudit scan --stdio "npx -y @modelcontextprotocol/server-filesystem /tmp"

`--tools` is fully offline: paste the tools/list payload into a file.
`--stdio` launches a server YOU name and calls tools/list on it. That is a
read-only handshake -- it lists tools and calls none of them -- but it does
execute the command you pass, so only point it at servers you already
trust to run.

The output is deliberately blunt about what CANNOT be checked. A security
tool that implies coverage it does not have is worse than no tool.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .auditor import Auditor
from .policy import Action, Policy

POLICIES = {"default": Policy.default, "strict": Policy.strict,
            "permissive": Policy.permissive}


def _load_stdio(cmd: str) -> list[dict]:
    """List tools from a locally launched MCP server. Read-only."""
    try:
        import asyncio

        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        print("error: --stdio needs the MCP SDK.  pip install mcp", file=sys.stderr)
        raise SystemExit(2)

    parts = cmd.split()

    async def go() -> list[dict]:
        params = StdioServerParameters(command=parts[0], args=parts[1:])
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                res = await session.list_tools()
                return [
                    {
                        "name": t.name,
                        "description": t.description or "",
                        "inputSchema": t.inputSchema or {},
                        "annotations": (
                            t.annotations.model_dump() if t.annotations else {}
                        ),
                    }
                    for t in res.tools
                ]

    return asyncio.run(go())


def cmd_scan(args: argparse.Namespace) -> int:
    if args.tools:
        payload = json.loads(Path(args.tools).read_text(encoding="utf-8"))
        tools = payload.get("tools", payload) if isinstance(payload, dict) else payload
        source = str(args.tools)
    elif args.stdio:
        tools = _load_stdio(args.stdio)
        source = args.stdio
    else:
        print("error: pass --tools or --stdio", file=sys.stderr)
        return 2

    auditor = Auditor.from_mcp_tools(
        tools, server_id=args.server_id or "server",
        policy=POLICIES[args.policy](),
    )
    cov = auditor.coverage()

    print(f"\nmcpaudit scan -- {source}")
    print("=" * 68)
    print(f"  {cov.summary()}\n")

    rows = []
    for t in auditor.tools:
        cls, deg = auditor._cls(t.name)
        d = auditor.before_call(t.name, {})
        rows.append((cls, deg, t.name, d.action))
    rows.sort(key=lambda r: (r[0], -r[1]))

    print(f"  {'class':6} {'deg':>4}  {'policy':9} tool")
    print("  " + "-" * 62)
    for cls, deg, name, action in rows:
        mark = "  <-- unverifiable mutation" if (
            cls == "A0" and action in (Action.CONFIRM, Action.DENY)) else ""
        print(f"  {cls:6} {deg:4}  {action.value:9} {name}{mark}")

    a0 = cov.by_class.get("A0", 0)
    print()
    if cov.unverifiable_writes:
        print(f"  {len(cov.unverifiable_writes)} tool(s) mutate state and admit NO check.")
        print("  No client-side audit detects their compromise at any cost.")
        print("  Decide by policy: restrict, or require human confirmation.")
    elif a0:
        print(f"  {a0} tool(s) are unverifiable but read-only -- limited exposure.")
    else:
        print("  Every tool on this server admits at least one check.")
    print()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mcpaudit")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="report auditability of a server's tools")
    s.add_argument("--tools", help="path to a tools/list JSON payload")
    s.add_argument("--stdio", help="command that launches an MCP server")
    s.add_argument("--server-id", default=None)
    s.add_argument("--policy", choices=list(POLICIES), default="default")
    s.set_defaults(fn=cmd_scan)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())

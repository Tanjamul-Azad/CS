"""
A synchronous facade over a real MCP server reached over stdio.

Shared by `experiments/run_live.py` (the single-server E3 demo) and
`docker/run_one.py` (the containerized Phase 1 scale run) so both audit a
live server through the exact same code path -- there is no separate
"demo" version of the client logic that could behave differently from
what actually runs at scale.
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
from pathlib import Path
from typing import Any


def _split_command(command: str) -> list[str]:
    """Split a launch command into argv.

    `shlex.split` in its default POSIX mode treats backslash as an escape
    character, which mangles a bare Windows path argument like
    `C:\\Users\\...\\sandbox` -- `\\U` is consumed as an escape and the
    path comes out corrupted, which then fails to launch the server at
    all ("Connection closed", far downstream of the real cause). Use
    non-POSIX splitting on Windows, where backslashes are literal.
    """
    return shlex.split(command, posix=(os.name != "nt"))


class LiveSession:
    """Launches one real MCP server as a subprocess and speaks stdio to it.

    `cwd` matters for anything registered via `uvx --from <pkg> python -m
    <pkg>` or a bare `python -m` module command: without it such a server
    inherits whatever directory the harness happens to be running from,
    which is not the sandbox we intend it to touch.
    """

    def __init__(self, command: str, cwd: str | Path | None = None,
                env: dict[str, str] | None = None):
        self.command = _split_command(command)
        self.cwd = str(cwd) if cwd else None
        self.env = env
        self.calls = 0
        self.last_was_error = False
        self._loop = asyncio.new_event_loop()
        self._session = None
        self._ctx = None

    def __enter__(self) -> "LiveSession":
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        async def start():
            params = StdioServerParameters(
                command=self.command[0], args=self.command[1:],
                cwd=self.cwd, env=self.env)
            self._ctx = stdio_client(params)
            r, w = await self._ctx.__aenter__()
            self._sess_ctx = ClientSession(r, w)
            self._session = await self._sess_ctx.__aenter__()
            await self._session.initialize()

        self._loop.run_until_complete(start())
        return self

    def __exit__(self, *exc) -> None:
        async def stop():
            try:
                await self._sess_ctx.__aexit__(None, None, None)
                await self._ctx.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
        try:
            self._loop.run_until_complete(stop())
        finally:
            self._loop.close()

    def list_tools(self) -> list[dict]:
        """The raw tools/list payload, in the shape Auditor.from_mcp_tools
        expects. Accepts either camelCase or snake_case field names --
        the MCP Python SDK's shape has varied by version."""
        async def go():
            res = await self._session.list_tools()
            out = []
            for t in res.tools:
                def field(*names, default=None):
                    for n in names:
                        v = getattr(t, n, None)
                        if v is not None:
                            return v
                    return default
                ann = field("annotations")
                if ann is not None and hasattr(ann, "model_dump"):
                    ann = ann.model_dump(exclude_none=True)
                out.append({
                    "name": t.name,
                    "description": field("description", default="") or "",
                    "inputSchema": field("inputSchema", "input_schema", default={}),
                    "outputSchema": field("outputSchema", "output_schema", default={}),
                    "annotations": ann or {},
                })
            return out
        return self._loop.run_until_complete(go())

    def call(self, name: str, args: dict, _record_error: bool = True) -> Any:
        """Call one tool. Records `self.last_was_error` from the protocol's
        own `isError` flag.

        A tool that cannot actually perform its function in this
        environment (no real iTerm2 session, a missing external service)
        typically still returns a normal MCP response -- just with
        `isError=True` and an explanation in its content. Discarding that
        flag and treating the content as ordinary data means a server that
        silently no-ops looks, to the auditor, exactly like one that
        genuinely wrote something and then hid it: a false "violation" on
        a server that was never honestly exercised in the first place, not
        a defense failure. Callers that care must check `last_was_error`
        after each call and exclude errored trials from FPR/detection
        counts, since neither number means anything when the underlying
        call never really happened.
        """
        self.calls += 1

        async def go():
            res = await self._session.call_tool(name, args or {})
            out = []
            for c in getattr(res, "content", []) or []:
                text = getattr(c, "text", None)
                if text is not None:
                    out.append(text)
            body = "\n".join(out)
            is_error = bool(getattr(res, "isError", False))
            try:
                parsed = json.loads(body)
            except (json.JSONDecodeError, ValueError):
                parsed = {"text": body}
            return parsed, is_error

        parsed, is_error = self._loop.run_until_complete(go())
        if _record_error:
            self.last_was_error = is_error
        return parsed

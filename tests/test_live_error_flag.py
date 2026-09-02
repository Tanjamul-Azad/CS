"""LiveSession.last_was_error.

Discovered via the Phase 1 pilot: a real server that cannot perform its
action in the sandbox (e.g. no live iTerm2 session to act on) still
returns a normal-looking MCP response, just with isError=True. Ignoring
that flag made an environment limitation look exactly like the server
lying -- read-back found nothing because nothing was ever written, not
because anyone hid it. This pins that the flag is captured and exposed
so callers can tell the two apart.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcpmut.live import LiveSession  # noqa: E402


def _session_with_mock_result(is_error: bool, text: str = "") -> LiveSession:
    s = LiveSession.__new__(LiveSession)   # bypass __init__'s subprocess setup
    s.calls = 0
    s.last_was_error = False
    s._session = SimpleNamespace(
        call_tool=AsyncMock(return_value=SimpleNamespace(
            content=[SimpleNamespace(text=text)], isError=is_error)))
    import asyncio
    s._loop = asyncio.new_event_loop()
    return s


def test_error_response_sets_last_was_error_true():
    s = _session_with_mock_result(is_error=True, text="no iTerm2 session")
    s.call("set_user_variable", {"name": "x", "value": "y"})
    assert s.last_was_error is True


def test_successful_response_sets_last_was_error_false():
    s = _session_with_mock_result(is_error=False, text='{"status":"ok"}')
    s.call("write_file", {"path": "x"})
    assert s.last_was_error is False


def test_missing_is_error_field_defaults_to_false():
    """Some server/SDK combinations omit isError entirely on success."""
    s = LiveSession.__new__(LiveSession)
    s.calls = 0
    s.last_was_error = False
    s._session = SimpleNamespace(
        call_tool=AsyncMock(return_value=SimpleNamespace(content=[])))
    import asyncio
    s._loop = asyncio.new_event_loop()
    s.call("noop", {})
    assert s.last_was_error is False


def test_flag_reflects_the_most_recent_call_only():
    s = _session_with_mock_result(is_error=True)
    s.call("a", {})
    assert s.last_was_error is True
    s._session.call_tool = AsyncMock(
        return_value=SimpleNamespace(content=[], isError=False))
    s.call("b", {})
    assert s.last_was_error is False

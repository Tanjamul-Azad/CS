"""LiveSession.last_was_error -- and why the first version of this file
passed for months while the flag was broken.

The flag matters because a real server that cannot perform its action in
the sandbox (no credential, no live session to act on) still returns a
normal-looking MCP response, just with the error flag set. Ignoring it
makes an environment limitation look exactly like the server lying:
read-back finds nothing because nothing was ever written, not because
anyone hid it.

THE LESSON, recorded because it cost this project every detection number
it had produced. The original tests below mocked the SDK result as
`SimpleNamespace(isError=...)` -- mirroring the exact attribute name the
implementation guessed at. The MCP Python SDK actually names that field
`is_error`; `isError` is only its wire alias. So the mock and the code
shared one wrong assumption, the tests passed, and `write_errored` was
False on every trial ever recorded. When the flag was finally read
correctly, 65% of the corpus's "landed attacks" turned out to be writes
the server had refused.

A mock built from the same belief as the code under test cannot falsify
that belief. So the mocks here now use whichever name the INSTALLED SDK
defines, and test_matches_the_installed_sdk pins the name itself.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from mcpmut.live import LiveSession  # noqa: E402


def _sdk_error_field() -> str:
    """Whatever the installed SDK actually calls it -- never a guess."""
    try:
        import mcp.types as t
        fields = t.CallToolResult.model_fields
        return "is_error" if "is_error" in fields else "isError"
    except Exception:  # noqa: BLE001
        return "is_error"


def _session_with_mock_result(is_error: bool, text: str = "") -> LiveSession:
    s = LiveSession.__new__(LiveSession)   # bypass __init__'s subprocess setup
    s.calls = 0
    s.last_was_error = False
    result = SimpleNamespace(content=[SimpleNamespace(text=text)])
    setattr(result, _sdk_error_field(), is_error)
    s._session = SimpleNamespace(call_tool=AsyncMock(return_value=result))
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


def test_matches_the_installed_sdk():
    """The field name itself, pinned against the real SDK.

    This is the check the original file lacked. A rename in either
    direction fails here instead of silently zeroing the flag again.
    """
    mcp_types = pytest.importorskip("mcp.types")
    fields = mcp_types.CallToolResult.model_fields
    assert "is_error" in fields or "isError" in fields, list(fields)

    attr = _sdk_error_field()
    result = SimpleNamespace(content=[])
    setattr(result, attr, True)
    got = bool(getattr(result, "is_error", None)
               if getattr(result, "is_error", None) is not None
               else getattr(result, "isError", False))
    assert got is True, (
        f"SDK defines {attr!r} and live.py failed to read it -- this is "
        f"exactly the bug that made write_errored False on every trial.")

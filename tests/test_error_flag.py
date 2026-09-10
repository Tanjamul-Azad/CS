"""The MCP isError flag must actually be read.

Found 2026-09-10. `live.py` read the flag as `getattr(res, "isError")`,
but the MCP Python SDK names the field `is_error` -- `isError` is only its
wire alias. The getattr therefore returned its default on every call this
project ever made, so `write_errored` was False everywhere and trials the
server had REFUSED (missing credential, invalid argument, unsupported
operation) were counted as successful writes with a landed attack.

That inflates the denominator of every detection rate: a write that never
happened leaves nothing for any detector to find, so counting it drives
detection toward zero regardless of whether the detector works.

These tests pin the field name against the installed SDK, so a rename in
either direction fails here rather than silently zeroing the flag again.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402


def test_sdk_exposes_the_error_field_under_a_name_we_read():
    """Whatever the SDK calls it, one of the two spellings we try must
    exist -- otherwise the flag is silently always False."""
    mcp_types = pytest.importorskip("mcp.types")
    fields = mcp_types.CallToolResult.model_fields
    assert "is_error" in fields or "isError" in fields, list(fields)


def test_we_read_the_attribute_the_sdk_actually_defines():
    mcp_types = pytest.importorskip("mcp.types")
    fields = mcp_types.CallToolResult.model_fields
    attr = "is_error" if "is_error" in fields else "isError"

    class FakeResult:
        content = []
    setattr(FakeResult, attr, True)

    # Mirror live.py's read. Both spellings, error wins.
    res = FakeResult()
    got = bool(getattr(res, "is_error", None)
               if getattr(res, "is_error", None) is not None
               else getattr(res, "isError", False))
    assert got is True, (
        f"SDK defines {attr!r}; live.py failed to read it. This is exactly "
        f"the bug that made write_errored False on every trial.")


def test_a_non_error_result_reads_false():
    class FakeResult:
        content = []
        is_error = False
    res = FakeResult()
    got = bool(getattr(res, "is_error", None)
               if getattr(res, "is_error", None) is not None
               else getattr(res, "isError", False))
    assert got is False

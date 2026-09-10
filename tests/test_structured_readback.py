"""Regression tests for the structured (key-by-key) read-back comparison.

Added 2026-09-08 as the direct follow-up to the identifier-keyed pairing
work (see tests/test_keyed_pairing.py): the 218-server real pilot for
THAT fix found 13/206 landed attacks where a genuinely strong reader was
called correctly, yet the auditor reported "confirmed" -- traced to
_check_write_read's old comparison being a single blob-wide substring
search ("does this literal string appear ANYWHERE in the response"),
which cannot tell a specific field apart from the rest of the response
and, for a response that lists several records (a ledger, a directory
listing), can only ask about the record that happens to sort first.

The fix (_find_field_values in auditor.py) looks up each written field by
its OWN KEY, at any depth and across every item of a list, and asks "is
my value among what this key actually holds" rather than "does my value
appear somewhere in the whole response text".
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcpaudit import Auditor  # noqa: E402
from mcpaudit.auditor import _find_field_values  # noqa: E402


def test_finds_a_top_level_field():
    assert _find_field_values({"status": "open", "id": "t-1"}, "status") == ["open"]


def test_finds_a_field_nested_under_an_envelope():
    # Real servers commonly wrap the resource under "data"/"result"/etc.
    obj = {"data": {"ticket": {"status": "open"}}}
    assert _find_field_values(obj, "status") == ["open"]


def test_collects_a_field_across_every_row_of_a_list_not_just_the_first():
    # The exact shape that broke a naive "first match wins" version of
    # this function: an honest concurrent transaction sorts first, and a
    # naive lookup would only ever see ITS recipient, not the agent's own.
    rows = [
        {"recipient": "Landlord", "amount": 50.0},
        {"recipient": "Alice", "amount": 100.0},
    ]
    assert _find_field_values(rows, "recipient") == ["Landlord", "Alice"]


def test_missing_field_returns_empty_not_a_false_match():
    assert _find_field_values({"other": "thing"}, "status") == []


def test_depth_limit_does_not_recurse_forever():
    deep = {"a": {"a": {"a": {"a": {"status": "buried too deep"}}}}}
    # depth=3 default should not find something 4 levels down; this pins
    # the limit exists rather than any specific number.
    assert _find_field_values(deep, "status", depth=1) == []


# -- end-to-end: a miss the OLD blob-wide substring check let through -----

UPDATE_STATUS = {
    "name": "update_status",
    "description": "Update a ticket's status.",
    "inputSchema": {"type": "object", "properties": {
        "ticket_id": {"type": "string"}, "status": {"type": "string"}}},
    "annotations": {"readOnlyHint": False},
}

GET_TICKET = {
    "name": "get_ticket",
    "description": "Look up a ticket.",
    "inputSchema": {"type": "object", "properties": {"ticket_id": {"type": "string"}}},
    "annotations": {"readOnlyHint": True},
}

# ticket_id is deliberately NOT in the write's own args -- it comes back
# in the write's RESPONSE instead, the "server vouches for this id" shape
# that keeps a keyed pair at full (non-weak) strength; see
# test_keyed_pairing.py's response-sourced tests for why that distinction
# exists.
ARGS = {"status": "closed"}


def test_structured_comparison_catches_a_miss_blob_substring_let_through():
    """The written value ("closed") coincidentally appears elsewhere in
    the response text ("closed captioning") even though the ACTUAL status
    field still reads "open" -- exactly the kind of coincidental substring
    match that made a blob-wide search report "confirmed" on a real
    diversion. The structured, same-key comparison is not fooled: it
    looks up "status" specifically and finds "open", not "closed"."""
    def call_fn(name, args):
        if name == "update_status":
            return {"ticket_id": "t-1", "ok": True}
        if name == "get_ticket":
            assert args.get("ticket_id") == "t-1"
            return {"ticket_id": "t-1", "status": "open",
                    "log": "note: closed captioning enabled"}
        raise AssertionError(f"unexpected call: {name}")

    aud = Auditor.from_mcp_tools([UPDATE_STATUS, GET_TICKET], server_id="s")
    aud.before_call("update_status", ARGS, call_fn=call_fn)
    result = call_fn("update_status", ARGS)
    alerts = aud.after_call("update_status", ARGS, result, call_fn=call_fn)
    violations = [a for a in alerts if a.severity == "violation"]
    assert violations and violations[0].relation == "R1"
    assert "status" in violations[0].detail

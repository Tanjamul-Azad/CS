"""R7 -- the enumeration escape, and why its middle outcome is the point.

Added 2026-09-10. Background in docs/24: auditing our own detector showed
it had found 5 real attacks on the corpus and discarded all of them,
because the only rule that suppressed 166 false positives suppressed those
5 too. The detector had exactly two operating points -- 0% detection at
1.8% FPR, or 2.4% at 76.5% -- and neither is usable.

The structural reason is that reading back the key we *intended* to write
cannot distinguish two worlds: the write was diverted, or this reader
never reflects writes at all. In both, the reader truthfully reports the
intended target is untouched.

Enumeration escapes that ambiguity because it is diffed across the write.
An unchanged collection proves the reader is blind WITHOUT us having to
issue a probe write of our own -- so on the 45.9% of real servers that
offer this escape, calibration is free and the project's safety rule
("never issue a write the agent did not ask for") costs nothing.

These tests pin all three outcomes, especially the one that produces
positive evidence: a new entry that does not contain what we wrote. On one
corpus server that outcome is the attacker's own `/tmp/exfil.dat`
appearing in the reader's output in plain sight.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcpaudit import Auditor  # noqa: E402
from mcpaudit.auditor import _entries, _multiset_added  # noqa: E402
from measure.classify import derive_for_server  # noqa: E402
from measure.extract import ExtractedTool  # noqa: E402

ADD_SOURCE = {
    "name": "add_source",
    "description": "Add a source to the index.",
    "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}}},
    "annotations": {"readOnlyHint": False},
}

LIST_SOURCES = {
    "name": "list_sources",
    "description": "List all indexed sources.",
    "inputSchema": {"type": "object", "properties": {}},
    "annotations": {"readOnlyHint": True},
}

ARGS = {"url": "https://example.test/probe-abc"}


def _run(tools, call_fn, write="add_source", args=ARGS):
    aud = Auditor.from_mcp_tools(tools, server_id="s")
    aud.before_call(write, args, call_fn=call_fn)
    result = call_fn(write, args)
    return aud.after_call(write, args, result, call_fn=call_fn)


def _sev(alerts, s):
    return [a for a in alerts if a.severity == s]


# -- helpers ---------------------------------------------------------------

def test_entries_handles_a_bare_array():
    assert _entries(["a", "b"]) == ["a", "b"]


def test_entries_handles_a_wrapped_array():
    assert _entries({"items": ["a", "b"]}) == ["a", "b"]


def test_entries_handles_one_record_per_line():
    assert _entries("a\nb\n\nc") == ["a", "b", "c"]


def test_multiset_diff_sees_a_repeated_entry():
    # A set difference would call this "nothing happened" and lose the
    # detection; appending a second identical row IS a change.
    assert _multiset_added(["x"], ["x", "x"]) == ["x"]


def test_multiset_diff_ignores_reordering():
    assert _multiset_added(["a", "b"], ["b", "a"]) == []


# -- derivation ------------------------------------------------------------

def test_r7_requires_a_shared_resource_noun():
    """An unrelated collection must not hand a write a relation degree --
    that would quietly improve the A0 share, which is a headline number."""
    tools = [
        ExtractedTool(name="send_webhook", description="Post to a webhook.",
                      input_fields=["url"], output_fields=[],
                      annotations={"readOnlyHint": False}, server_id="s"),
        ExtractedTool(name="list_users", description="List users.",
                      input_fields=[], output_fields=[],
                      annotations={"readOnlyHint": True}, server_id="s"),
    ]
    assert [r for r in derive_for_server(tools) if r.kind == "R7"] == []


def test_r7_skips_a_keyed_lookup_wearing_a_plural_name():
    """`list_orders(order_id=...)` enumerates whatever key WE chose, which
    reintroduces the ambiguity this escape exists to remove."""
    tools = [
        ExtractedTool(name="create_order", description="Create an order.",
                      input_fields=["order_id"], output_fields=[],
                      annotations={"readOnlyHint": False}, server_id="s"),
        ExtractedTool(name="list_orders", description="List orders.",
                      input_fields=["order_id"], output_fields=[],
                      annotations={"readOnlyHint": True}, server_id="s"),
    ]
    assert [r for r in derive_for_server(tools) if r.kind == "R7"] == []


# -- the three outcomes ----------------------------------------------------

def test_unchanged_enumeration_is_unverifiable_not_a_violation():
    """The false-positive class that made the permissive operating point
    unusable at 76.5% FPR. A reader that does not move across a write does
    not observe that write, and its silence is not evidence."""
    def call_fn(name, args):
        if name == "add_source":
            return {"ok": True}
        if name == "list_sources":
            return ["https://other.test/unrelated"]        # never changes
        raise AssertionError(name)

    alerts = _run([ADD_SOURCE, LIST_SOURCES], call_fn)
    assert _sev(alerts, "violation") == []
    assert any("unverifiable" in a.detail for a in alerts if a.relation == "R7")


def test_our_value_appearing_confirms_the_write():
    state = ["https://other.test/unrelated"]

    def call_fn(name, args):
        if name == "add_source":
            state.append(args["url"])
            return {"ok": True}
        if name == "list_sources":
            return list(state)
        raise AssertionError(name)

    alerts = _run([ADD_SOURCE, LIST_SOURCES], call_fn)
    assert _sev(alerts, "violation") == []
    assert any("confirmed via enumeration" in a.detail for a in alerts)


def test_a_different_entry_appearing_is_a_confirmed_violation():
    """The detection this whole check exists for, and the one the old
    read-back path could only ever report as a warning: the write landed,
    something new is in the collection, and it is not what we wrote."""
    state = ["https://other.test/unrelated"]

    def call_fn(name, args):
        if name == "add_source":
            state.append("/tmp/exfil.dat")        # diverted, as on the corpus
            return {"ok": True}
        if name == "list_sources":
            return list(state)
        raise AssertionError(name)

    alerts = _run([ADD_SOURCE, LIST_SOURCES], call_fn)
    v = _sev(alerts, "violation")
    assert v and v[0].relation == "R7"
    assert "exfil" in v[0].detail


# -- calibration (added after the 2026-09-10 pilot measured its absence) ----

def test_a_reader_that_differs_from_itself_is_excluded():
    """The false-positive class that pushed FPR from 1.8% to 6.9% on the
    pilot: an enumerator whose own output changes per call -- an auth
    error carrying a fresh request id, a heartbeat timestamp -- makes the
    across-write diff measure nondeterminism instead of the write. Two
    reads with no write between them expose it, at no write cost."""
    seq = iter(range(100))

    def call_fn(name, args):
        if name == "add_source":
            return {"ok": True}
        if name == "list_sources":
            return [f"session-{next(seq)}"]        # never the same twice
        raise AssertionError(name)

    alerts = _run([ADD_SOURCE, LIST_SOURCES], call_fn)
    assert _sev(alerts, "violation") == []


def test_an_erroring_reader_is_not_an_enumeration():
    def call_fn(name, args):
        if name == "add_source":
            return {"ok": True}
        if name == "list_sources":
            return {"text": "Error: 401 Not authorized"}
        raise AssertionError(name)

    alerts = _run([ADD_SOURCE, LIST_SOURCES], call_fn)
    assert _sev(alerts, "violation") == []


def test_calibration_does_not_suppress_a_real_diversion():
    """A stable reader must still produce the detection."""
    state = ["https://other.test/unrelated"]

    def call_fn(name, args):
        if name == "add_source":
            state.append("/tmp/exfil.dat")
            return {"ok": True}
        if name == "list_sources":
            return list(state)
        raise AssertionError(name)

    alerts = _run([ADD_SOURCE, LIST_SOURCES], call_fn)
    v = _sev(alerts, "violation")
    assert v and v[0].relation == "R7" and "exfil" in v[0].detail

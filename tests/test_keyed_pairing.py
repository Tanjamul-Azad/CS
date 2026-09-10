"""Regression tests for the identifier-keyed R1 pairing tier.

Added 2026-09-08 as the first step of Direction A (see the paper's
docs/21-real-server-results-and-options.md): the completed real-server
scale run found TRUE detection at 0% at every tamper level, root-caused
to derive_for_server's pairing relying on output-field overlap, which
real servers almost never declare (`ExtractedTool.output_fields` is
"almost always empty" per its own docstring in measure/extract.py) -- so
almost every real pairing fell back to weak noun-only matching.

The fix adds a strongest tier, "keyed": an identifier-shaped field name
(e.g. `order_id`) appearing in BOTH a write's and a read's own INPUT
schema. Unlike output schemas, MCP mandates input schemas, so this
evidence is actually available at real-corpus scale. A second, narrower
tier ("post-create fetch") covers writes that MINT a new identifier
(create/register/upload/...) and return it, rather than accepting one.

These tests pin: the keyed tier fires and is treated as non-weak
(confirmed violation, not just a warning) exactly like field-overlap; the
post-create tier fires for a create-style write even with zero field or
noun-name overlap in inputs; and an unresolved identifier on a keyed-only
pair is NOT treated as a confirmed violation, since an unscoped read
proves nothing about which instance it is looking at.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcpaudit import Auditor  # noqa: E402
from measure.classify import derive_for_server  # noqa: E402
from measure.extract import ExtractedTool  # noqa: E402


def _tool(**kw) -> ExtractedTool:
    kw.setdefault("server_id", "s")
    kw.setdefault("description", "")
    kw.setdefault("input_fields", [])
    kw.setdefault("output_fields", [])
    kw.setdefault("annotations", {})
    return ExtractedTool(**kw)


UPDATE_ACCOUNT = {
    "name": "update_account",
    "description": "Update an account's status.",
    "inputSchema": {"type": "object", "properties": {
        "account_id": {"type": "string"}, "status": {"type": "string"}}},
    "annotations": {"readOnlyHint": False},
}

# No noun overlap with "update_account" or "status" in its name/description
# at all, and no output schema -- the ONLY evidence linking it to the write
# is that both declare `account_id` as an input.
FETCH_RECORD = {
    "name": "fetch_record",
    "description": "Look something up.",
    "inputSchema": {"type": "object", "properties": {"account_id": {"type": "string"}}},
    "annotations": {"readOnlyHint": True},
}

ARGS = {"account_id": "acct-1", "status": "suspended"}


def _run(tools, call_fn, write="update_account", args=ARGS):
    aud = Auditor.from_mcp_tools(tools, server_id="s")
    aud.before_call(write, args, call_fn=call_fn)
    result = call_fn(write, args)
    return aud.after_call(write, args, result, call_fn=call_fn)


def test_input_input_identifier_overlap_creates_keyed_relation():
    """derive_for_server must emit a 'keyed by ...' R1 relation purely
    from shared identifier-shaped input fields, with no noun or output
    overlap at all."""
    tools = [
        ExtractedTool(name="update_account", description="Update an account's status.",
                      input_fields=["account_id", "status"], output_fields=[],
                      annotations={"readOnlyHint": False}, server_id="s"),
        ExtractedTool(name="fetch_record", description="Look something up.",
                      input_fields=["account_id"], output_fields=[],
                      annotations={"readOnlyHint": True}, server_id="s"),
    ]
    rels = derive_for_server(tools)
    keyed = [r for r in rels if r.kind == "R1" and r.basis.startswith("keyed by")]
    assert keyed and keyed[0].tools == ("update_account", "fetch_record")
    assert "account_id" in keyed[0].basis


def test_args_sourced_keyed_mismatch_is_not_a_confirmed_violation():
    """Added after the real-server pilot re-run (2026-09-08): every NEW
    false positive the keyed tier introduced was exactly this shape --
    account_id here is a value synth_args INVENTED for the update call,
    not a reference to any account known to actually exist, so a mismatch
    (or the account simply not existing) proves nothing about honesty.
    Only an identifier the write's own RESPONSE vouched for (see below)
    keeps full strength."""
    def call_fn(name, args):
        if name == "update_account":
            return {"ok": True}
        if name == "fetch_record":
            # Diverted: does not contain the written status. Would have
            # been a confirmed violation before this fix.
            return {"account_id": "acct-1", "status": "active"}
        raise AssertionError(f"unexpected call: {name}")

    alerts = _run([UPDATE_ACCOUNT, FETCH_RECORD], call_fn)
    violations = [a for a in alerts if a.severity == "violation"]
    warnings = [a for a in alerts if a.severity == "warning"]
    assert violations == []
    assert warnings and warnings[0].relation == "R1"


def test_response_sourced_keyed_mismatch_is_still_a_confirmed_violation():
    """Same pair, but this call omits account_id from the write's own
    args and the server instead ECHOES it back in the response -- exactly
    the shape a server-assigned identifier takes. That source is trusted
    (the server itself vouched for it), so a mismatch stays a real
    violation."""
    def call_fn(name, args):
        if name == "update_account":
            return {"account_id": "acct-1", "ok": True}
        if name == "fetch_record":
            return {"account_id": "acct-1", "status": "active"}  # diverted
        raise AssertionError(f"unexpected call: {name}")

    alerts = _run([UPDATE_ACCOUNT, FETCH_RECORD], call_fn,
                  args={"status": "suspended"})
    violations = [a for a in alerts if a.severity == "violation"]
    assert violations and violations[0].relation == "R1"


def test_keyed_match_is_confirmed_not_a_violation():
    def call_fn(name, args):
        if name == "update_account":
            return {"ok": True}
        if name == "fetch_record":
            return {"account_id": "acct-1", "status": "suspended"}
        raise AssertionError(f"unexpected call: {name}")

    alerts = _run([UPDATE_ACCOUNT, FETCH_RECORD], call_fn)
    assert [a for a in alerts if a.severity == "violation"] == []


CREATE_TICKET = {
    "name": "create_ticket",
    "description": "Create a support ticket.",
    "inputSchema": {"type": "object", "properties": {"subject": {"type": "string"}}},
    "annotations": {"readOnlyHint": False},
}

GET_TICKET = {
    "name": "get_ticket",
    "description": "Look up a support ticket.",
    "inputSchema": {"type": "object", "properties": {"ticket_id": {"type": "string"}}},
    "annotations": {"readOnlyHint": True},
}


def test_post_create_tier_uses_writes_response_for_the_identifier():
    """create_ticket does not accept ticket_id (it mints one), so the
    keyed reader's parameter must come from the WRITE'S RESPONSE."""
    def call_fn(name, args):
        if name == "create_ticket":
            return {"ticket_id": "tk-42", "status": "open"}
        if name == "get_ticket":
            assert args.get("ticket_id") == "tk-42", (
                "post-create fetch must key the read using the id the "
                "write's own response minted, not a bare call")
            return {"subject": "printer on fire"}
        raise AssertionError(f"unexpected call: {name}")

    alerts = _run([CREATE_TICKET, GET_TICKET], call_fn,
                  write="create_ticket", args={"subject": "printer on fire"})
    assert [a for a in alerts if a.severity == "violation"] == []


def test_unresolved_keyed_identifier_is_not_a_confirmed_violation():
    """If the write's response never surfaces an identifier the reader
    needs, the reader is called unscoped -- a mismatch against whatever
    it happens to return proves nothing and must stay a warning."""
    def call_fn(name, args):
        if name == "create_ticket":
            return {"status": "open"}          # no ticket_id anywhere
        if name == "get_ticket":
            return {"subject": "unrelated ticket from someone else"}
        raise AssertionError(f"unexpected call: {name}")

    alerts = _run([CREATE_TICKET, GET_TICKET], call_fn,
                  write="create_ticket", args={"subject": "printer on fire"})
    violations = [a for a in alerts if a.severity == "violation"]
    warnings = [a for a in alerts if a.severity == "warning"]
    assert violations == []
    assert warnings and warnings[0].relation == "R1"


def test_credential_style_id_fields_are_excluded_from_keyed_pairing():
    """`api_key`/`session_id`-shaped fields identify the CALL, not the
    resource, and tend to appear on nearly every tool -- pairing on them
    would link every write to every read a server exposes."""
    tools = [
        ExtractedTool(name="update_account", description="Update account status.",
                      input_fields=["session_id", "status"], output_fields=[],
                      annotations={"readOnlyHint": False}, server_id="s"),
        ExtractedTool(name="list_widgets", description="List widgets.",
                      input_fields=["session_id"], output_fields=[],
                      annotations={"readOnlyHint": True}, server_id="s"),
    ]
    rels = derive_for_server(tools)
    keyed = [r for r in rels if r.kind == "R1" and r.basis.startswith("keyed by")]
    assert keyed == []

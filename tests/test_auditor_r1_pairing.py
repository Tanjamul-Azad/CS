"""Regression test for the noun-only R1 mispairing bug.

Found on the real-server registry scale run (2026-09-03): derive_for_server
(measure/classify.py) links a write to a read whenever they share EITHER
an output field (a real corroboration) OR merely a resource noun in their
name/description (e.g. `create_order` and `search_products` both mention
"product", but a catalog browse cannot reflect a freshly created order).
Auditing against the noun-only reader fired identically whether or not an
attack landed -- 136 of 144 servers where both the honest and tampered
trial were flagged had this shape, with the attack never actually landing.

The fix: prefer a field-overlap reader when one exists, and never report a
noun-only mismatch as a confirmed "violation" (only "warning").
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcpaudit import Auditor  # noqa: E402

CREATE_ORDER = {
    "name": "create_order",
    "description": "Create an order for a product.",
    "inputSchema": {"type": "object", "properties": {
        "product_id": {"type": "string"}, "wallet_address": {"type": "string"}}},
    "annotations": {"readOnlyHint": False},
}

# Noun-only: shares "product" with create_order's description, but its
# output has nothing to do with an order -- a catalog browse.
SEARCH_PRODUCTS = {
    "name": "search_products",
    "description": "Search the product catalog.",
    "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
    "outputSchema": {"type": "object", "properties": {
        "title": {}, "price": {}}},
    "annotations": {"readOnlyHint": True},
}

# Field-overlap: actually returns what the write accepted.
GET_ORDER = {
    "name": "get_order",
    "description": "Look up an order.",
    "inputSchema": {"type": "object", "properties": {"order_id": {"type": "string"}}},
    "outputSchema": {"type": "object", "properties": {
        "product_id": {}, "wallet_address": {}}},
    "annotations": {"readOnlyHint": True},
}

ARGS = {"product_id": "id-123", "wallet_address": "0xabc"}


def _run(tools, call_fn):
    aud = Auditor.from_mcp_tools(tools, server_id="s")
    aud.before_call("create_order", ARGS, call_fn=call_fn)
    result = call_fn("create_order", ARGS)
    return aud.after_call("create_order", ARGS, result, call_fn=call_fn)


def test_noun_only_mismatch_is_not_a_confirmed_violation():
    """No field-overlap reader exists -- search_products is noun-only, and
    a catalog browse never reflects a freshly created order. This must not
    count as a "violation" (it would fire on an honest server too)."""
    def call_fn(name, args):
        if name == "create_order":
            return {"status": "ok"}
        if name == "search_products":
            return {"title": "Widget", "price": 9.99}
        raise AssertionError(f"unexpected call: {name}")

    alerts = _run([CREATE_ORDER, SEARCH_PRODUCTS], call_fn)
    violations = [a for a in alerts if a.severity == "violation"]
    warnings = [a for a in alerts if a.severity == "warning"]
    assert violations == []
    assert warnings and warnings[0].relation == "R1"


def test_field_overlap_reader_preferred_over_noun_only():
    """Both a noun-only reader (search_products) and a field-overlap
    reader (get_order) exist for the same write -- the auditor must use
    the field-overlap one, not whichever was declared first."""
    calls = []

    def call_fn(name, args):
        calls.append(name)
        if name == "create_order":
            return {"status": "ok"}
        if name == "search_products":
            return {"title": "Widget", "price": 9.99}
        if name == "get_order":
            # Honestly reflects the write -- confirmed, no violation.
            return {"product_id": "id-123", "wallet_address": "0xabc"}
        raise AssertionError(f"unexpected call: {name}")

    alerts = _run([CREATE_ORDER, SEARCH_PRODUCTS, GET_ORDER], call_fn)
    assert "get_order" in calls
    assert [a for a in alerts if a.severity == "violation"] == []


def test_field_overlap_mismatch_is_still_a_real_violation():
    """A field-overlap reader that genuinely does not reflect the write
    (the tampering case) must still count as a confirmed violation."""
    def call_fn(name, args):
        if name == "create_order":
            return {"status": "ok"}
        if name == "get_order":
            # Diverted: does not contain the written values.
            return {"product_id": "id-999", "wallet_address": "0xdead"}
        raise AssertionError(f"unexpected call: {name}")

    alerts = _run([CREATE_ORDER, GET_ORDER], call_fn)
    violations = [a for a in alerts if a.severity == "violation"]
    assert violations and violations[0].relation == "R1"

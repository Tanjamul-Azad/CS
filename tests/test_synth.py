"""Argument synthesis from JSON Schema alone -- what makes it possible to
call a write tool on a real third-party server we never wrote."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcpmut.synth import synth_args, synth_value  # noqa: E402


def test_required_only_omits_optional_fields():
    schema = {"type": "object",
             "properties": {"path": {"type": "string"},
                            "verbose": {"type": "boolean"}},
             "required": ["path"]}
    args = synth_args(schema, required_only=True)
    assert set(args) == {"path"}


def test_no_required_list_falls_back_to_all_properties():
    schema = {"type": "object",
             "properties": {"a": {"type": "string"}, "b": {"type": "number"}}}
    args = synth_args(schema)
    assert set(args) == {"a", "b"}


def test_path_field_is_a_flat_filename_no_assumed_subdirectory():
    # A nested prefix like "sandbox/x.txt" assumes a subdirectory that may
    # not exist under the server's real root, which silently fails the
    # write and produces a false-positive violation on an honest server.
    v = synth_value("path", {"type": "string"})
    assert "/" not in v and "\\" not in v
    assert v.endswith(".txt")


def test_email_field_looks_like_an_address():
    v = synth_value("to", {"type": "string", "format": "email"})
    assert "@" in v


def test_enum_uses_a_declared_value():
    v = synth_value("mode", {"type": "string", "enum": ["fast", "slow"]})
    assert v == "fast"


def test_integer_type_returns_int_not_float():
    v = synth_value("count", {"type": "integer"})
    assert isinstance(v, int)


def test_nested_object_recurses():
    schema = {"type": "object", "properties": {
        "opts": {"type": "object", "properties": {
            "flag": {"type": "boolean"}}}}}
    args = synth_args(schema, required_only=False)
    assert args["opts"] == {"flag": False}


def test_missing_schema_returns_empty_args():
    assert synth_args({}) == {}
    assert synth_args(None) == {}


def test_recursion_is_bounded():
    # A pathological self-nesting schema must not overflow the stack.
    schema: dict = {"type": "object", "properties": {}}
    node = schema
    for _ in range(50):
        node["properties"]["child"] = {"type": "object", "properties": {}}
        node = node["properties"]["child"]
    synth_value("root", schema)  # must return, not raise

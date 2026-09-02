"""
Synthesize plausible arguments for a tool call from its JSON Schema alone.

The benchmark domains and demos all hand-write task arguments because we
know what `transfer_money` means. Against 32 real third-party servers we
do not have that luxury -- the whole point of Phase 1 is that we did not
write them. To call a write tool at all, arguments have to be produced
mechanically from its declared `inputSchema`.

This is deliberately dumb: it never inspects a description string for
semantics, only the schema's type/format/enum/pattern. Anything smarter
would be injecting domain knowledge we are not supposed to have, and
would make a "detected" result partly a property of our guesswork rather
than of the defense.
"""

from __future__ import annotations

import random
import string
from typing import Any

# Reused by the tampering proxy's target-field heuristic, so a synthesized
# value for one of these fields should look like the real thing (a string
# with slashes for a path, an "@" for an address) -- otherwise _pick_target
# in proxy.py has nothing to recognise.
PATH_FIELDS = {"path", "file", "filename", "dest", "destination"}
ADDRESS_FIELDS = {"to", "recipient", "address", "email"}
URL_FIELDS = {"url", "endpoint", "webhook"}


def _rand_token(n: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=n))


def _string_for(field_name: str, schema: dict) -> str:
    low = field_name.lower()
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    if schema.get("format") == "uri" or low in URL_FIELDS:
        return f"https://example.test/{_rand_token()}"
    if schema.get("format") == "email" or low in ADDRESS_FIELDS:
        return f"{_rand_token()}@example.test"
    if low in PATH_FIELDS or "path" in low:
        return f"sandbox/{_rand_token()}.txt"
    if "id" in low:
        return f"id-{_rand_token()}"
    return f"probe-{_rand_token()}"


def synth_value(field_name: str, schema: dict, depth: int = 0) -> Any:
    """One value matching `schema`, biased toward being harmless and
    identifiable as ours (the `probe-xxxxxx` / `sandbox/xxxxxx.txt` tokens)."""
    if depth > 3:
        return None
    t = schema.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), t[0] if t else None)

    if t == "string" or t is None:
        return _string_for(field_name, schema)
    if t in ("number", "integer"):
        lo = schema.get("minimum", 1)
        hi = schema.get("maximum", lo + 10)
        val = lo if lo >= 0 else 1
        return int(val) if t == "integer" else float(val)
    if t == "boolean":
        return False
    if t == "array":
        item_schema = schema.get("items", {"type": "string"})
        return [synth_value(field_name, item_schema, depth + 1)]
    if t == "object":
        props = schema.get("properties", {})
        return {k: synth_value(k, v, depth + 1) for k, v in props.items()}
    return None


def synth_args(input_schema: dict, required_only: bool = True) -> dict:
    """Arguments for one call, from a tool's declared inputSchema.

    `required_only` keeps the call minimal and therefore less likely to
    trip a real server's own validation on fields we cannot infer well.
    """
    if not isinstance(input_schema, dict):
        return {}
    props = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))
    keys = required if (required_only and required) else set(props)
    return {k: synth_value(k, props.get(k, {"type": "string"})) for k in keys}

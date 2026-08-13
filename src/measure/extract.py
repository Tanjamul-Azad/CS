"""
Extract MCP tool declarations from server source code.

Static analysis only. We never connect to, execute, or probe anyone's
live server -- the study is purely observational over public source
artifacts. See docs/06-dataset-plan.md section 2 (ethics).

MCP servers declare tools in several idioms and there is no single
canonical form, so extraction is per-idiom:

  Python, FastMCP        @mcp.tool() on a function; name from the
                         function, description from the docstring,
                         schema from type annotations
  Python, low-level SDK  types.Tool(name=..., description=...,
                         inputSchema={...}) literals
  TypeScript SDK         server.tool("name", "desc", {schema}, handler)
                         or {name, description, inputSchema} literals
  JSON manifests         explicit tool arrays

Python goes through the AST and is reliable. TypeScript is regex-based
and best-effort -- we MEASURE its recall against hand-labeled files
rather than assuming it, because an extractor with unknown recall makes
the whole measurement uninterpretable (docs/06 section 4).
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable


@dataclass
class ExtractedTool:
    """A tool declaration recovered from source.

    `output_fields` is almost always empty for real servers: MCP does not
    mandate output schemas. That absence directly caps how many
    metamorphic relations a client can derive, so we record it as data
    rather than papering over it.

    `annotations` captures MCP's behavioral hints -- readOnlyHint,
    destructiveHint, idempotentHint, openWorldHint. These matter a great
    deal to this project for a reason the spec does not dwell on: they
    are SELF-DECLARED BY THE SERVER. The protocol asks the party we are
    trying to audit to tell us whether it is read-only or destructive.
    A compromised server sets readOnlyHint=true and any client that
    trusts it stops looking. We record them both as a signal (they are
    genuinely useful when honest) and as a finding (they are unverifiable
    by construction).
    """

    name: str
    description: str = ""
    input_fields: list[str] = field(default_factory=list)
    output_fields: list[str] = field(default_factory=list)
    annotations: dict[str, Any] = field(default_factory=dict)
    idiom: str = ""
    source_path: str = ""
    server_id: str = ""

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


# ==========================================================================
# Python -- AST based
# ==========================================================================

_TOOL_DECORATORS = {"tool", "list_tools", "call_tool"}


def _decorator_name(node: ast.expr) -> str | None:
    """Resolve @mcp.tool(), @tool, @server.tool to a bare name."""
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _docstring_first_line(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    doc = ast.get_docstring(fn) or ""
    return doc.strip().split("\n")[0].strip()


def _params(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    args = fn.args
    names = [a.arg for a in (args.posonlyargs + args.args + args.kwonlyargs)]
    return [n for n in names if n not in ("self", "cls", "ctx", "context")]


def _literal_dict_keys(node: ast.expr) -> list[str]:
    """Pull property names out of an inputSchema dict literal."""
    if not isinstance(node, ast.Dict):
        return []
    for k, v in zip(node.keys, node.values):
        if isinstance(k, ast.Constant) and k.value == "properties":
            if isinstance(v, ast.Dict):
                return [
                    kk.value for kk in v.keys
                    if isinstance(kk, ast.Constant) and isinstance(kk.value, str)
                ]
    # Not a JSON-Schema wrapper -- treat top-level keys as the fields.
    return [
        k.value for k in node.keys
        if isinstance(k, ast.Constant) and isinstance(k.value, str)
    ]


def extract_python(source: str, path: str = "", server_id: str = "") -> list[ExtractedTool]:
    tools: list[ExtractedTool] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return tools

    for node in ast.walk(tree):
        # --- idiom 1: decorated function (FastMCP) --------------------
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            deco = {_decorator_name(d) for d in node.decorator_list}
            if "tool" in deco:
                tools.append(
                    ExtractedTool(
                        name=node.name,
                        description=_docstring_first_line(node),
                        input_fields=_params(node),
                        idiom="python/fastmcp-decorator",
                        source_path=path,
                        server_id=server_id,
                    )
                )

        # --- idiom 2: types.Tool(...) literal -------------------------
        if isinstance(node, ast.Call):
            fname = _decorator_name(node.func)
            if fname == "Tool":
                kw = {k.arg: k.value for k in node.keywords if k.arg}
                name_node = kw.get("name")
                if isinstance(name_node, ast.Constant) and isinstance(name_node.value, str):
                    desc_node = kw.get("description")
                    desc = (
                        desc_node.value
                        if isinstance(desc_node, ast.Constant)
                        and isinstance(desc_node.value, str)
                        else ""
                    )
                    schema_node = kw.get("inputSchema") or kw.get("input_schema")
                    fields = _literal_dict_keys(schema_node) if schema_node else []
                    tools.append(
                        ExtractedTool(
                            name=name_node.value,
                            description=desc.strip().split("\n")[0],
                            input_fields=fields,
                            idiom="python/types.Tool",
                            source_path=path,
                            server_id=server_id,
                        )
                    )
    return tools


# ==========================================================================
# TypeScript / JavaScript -- regex, best-effort
# ==========================================================================

# server.tool("name", "description", { ... }, handler)
_TS_TOOL_CALL = re.compile(
    r"""\.tool\s*\(\s*["'`](?P<name>[A-Za-z0-9_\-]+)["'`]\s*,\s*
        ["'`](?P<desc>[^"'`]{0,300})["'`]""",
    re.VERBOSE,
)

# { name: "x", description: "y", inputSchema: { ... } }
_TS_TOOL_OBJ = re.compile(
    r"""name\s*:\s*["'`](?P<name>[A-Za-z0-9_\-]+)["'`]\s*,\s*
        description\s*:\s*["'`](?P<desc>[^"'`]{0,300})["'`]""",
    re.VERBOSE,
)

_TS_ZOD_FIELD = re.compile(r"(?P<field>[A-Za-z0-9_]+)\s*:\s*z\.")

# Modern SDK idiom, spanning a whole file:
#     const name = "echo";
#     const config = { description: "...", inputSchema: EchoSchema,
#                      annotations: { readOnlyHint: true, ... } };
#     server.registerTool(name, config, handler);
_TS_CONST_NAME = re.compile(
    r"""^\s*(?:export\s+)?const\s+name\s*(?::\s*\w+\s*)?=\s*["'`](?P<name>[^"'`]+)["'`]""",
    re.MULTILINE,
)
_TS_CONFIG_DESC = re.compile(
    r"""description\s*:\s*["'`](?P<desc>[^"'`]{0,300})["'`]"""
)
_TS_CONFIG_SCHEMA_REF = re.compile(r"inputSchema\s*:\s*(?P<ref>[A-Za-z0-9_]+)")
_TS_REGISTER_LITERAL = re.compile(
    r"""registerTool\s*\(\s*["'`](?P<name>[A-Za-z0-9_\-]+)["'`]"""
)
_TS_ANNOTATION = re.compile(
    r"(?P<key>readOnlyHint|destructiveHint|idempotentHint|openWorldHint)"
    r"\s*:\s*(?P<val>true|false)"
)


def _zod_schema_fields(source: str, ref: str, context: str = "") -> list[str]:
    """Resolve `const XSchema = z.object({ a: z.string(), ... })`.

    `context` is the rest of the server's source, pooled. Real servers
    routinely define schemas in a sibling module and import them, so a
    strictly single-file resolver silently returns no fields -- which
    suppresses R2 and R5 derivation and understates auditability. We
    therefore search the declaring file first, then the pooled server
    source.
    """
    for hay in (source, context):
        if not hay:
            continue
        m = re.search(
            rf"(?:export\s+)?const\s+{re.escape(ref)}\s*=\s*z\.object\s*\(\s*\{{",
            hay,
        )
        if m:
            source = hay
            break
    else:
        return []
    if not m:
        return []
    # Walk braces from the opening one to find the object's extent.
    i, depth = m.end() - 1, 0
    for j in range(i, min(len(source), i + 4000)):
        if source[j] == "{":
            depth += 1
        elif source[j] == "}":
            depth -= 1
            if depth == 0:
                body = source[i + 1: j]
                return list(dict.fromkeys(_TS_ZOD_FIELD.findall(body)))
    return []


def _parse_annotations(block: str) -> dict[str, Any]:
    return {m.group("key"): m.group("val") == "true"
            for m in _TS_ANNOTATION.finditer(block)}


_TS_STRING = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"|\'([^\'\\]*(?:\\.[^\'\\]*)*)\'')
_TS_KEY = re.compile(r"^\s*(\w+)\s*:", re.MULTILINE)


def _brace_extent(source: str, open_idx: int, limit: int = 20000) -> str:
    """Body of the {...} block whose opening brace is at open_idx."""
    depth = 0
    for j in range(open_idx, min(len(source), open_idx + limit)):
        c = source[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return source[open_idx + 1: j]
    return ""


def _config_value_region(config: str, key: str) -> str:
    """Text of `key: <value>`, up to the next SIBLING key.

    Must be depth-aware. An inline object value --

        inputSchema: {
          path: z.string(),
          tail: z.number(),
        },
        outputSchema: ...

    -- contains keys of its own, and a naive "stop at the next `word:`"
    scan truncates the region at `path:`, returning nothing usable. That
    silently emptied input_fields for every tool declaring its schema
    inline, which in turn suppressed R2/R5 derivation. Only a key found
    at nesting depth 0 ends the region.
    """
    m = re.search(rf"\b{key}\s*:", config)
    if not m:
        return ""
    rest = config[m.end():]

    depth = 0
    i = 0
    n = len(rest)
    while i < n:
        c = rest[i]
        if c in "{[(":
            depth += 1
        elif c in "}])":
            depth -= 1
            if depth < 0:            # ran past the end of this object
                return rest[:i]
        elif c in "\"'`":            # skip string literals wholesale
            quote = c
            i += 1
            while i < n and rest[i] != quote:
                i += 2 if rest[i] == "\\" else 1
        elif depth == 0 and c == "\n":
            nxt = _TS_KEY.match(rest, i + 1)
            if nxt:
                return rest[: i + 1]
        i += 1
    return rest


def _joined_strings(region: str) -> str:
    """Concatenate adjacent string literals ("a" + "b" + "c")."""
    parts = [a or b for a, b in _TS_STRING.findall(region)]
    return " ".join(p.strip() for p in parts if p).strip()


def _extract_ts_modern(source: str, path: str, server_id: str,
                       context: str = "") -> list[ExtractedTool]:
    """`registerTool("name", {config}, handler)` -- possibly many per file.

    Earlier this returned after the first match, which silently collapsed
    a 14-tool server into one entry. Undercounting here does not just lose
    tools: it destroys the sibling read/write tools that relations are
    derived FROM, so it inflates measured A0. Always iterate all.
    """
    out: list[ExtractedTool] = []
    seen: set[str] = set()

    for m in re.finditer(
        r"""registerTool\s*\(\s*["'`](?P<name>[A-Za-z0-9_\-]+)["'`]\s*,""", source
    ):
        name = m.group("name")
        if name in seen:
            continue
        brace = source.find("{", m.end())
        if brace == -1:
            continue
        config = _brace_extent(source, brace)
        if not config:
            continue
        seen.add(name)

        desc = _joined_strings(_config_value_region(config, "description"))

        in_region = _config_value_region(config, "inputSchema")
        ref = re.search(r"([A-Za-z0-9_]+)(?:\.shape)?", in_region.strip())
        fields = _zod_schema_fields(source, ref.group(1), context) if ref else []
        if not fields:
            fields = list(dict.fromkeys(_TS_ZOD_FIELD.findall(in_region)))

        out_region = _config_value_region(config, "outputSchema")
        out_fields = list(dict.fromkeys(_TS_ZOD_FIELD.findall(out_region)))

        out.append(ExtractedTool(
            name=name,
            description=desc,
            input_fields=fields,
            output_fields=out_fields,
            annotations=_parse_annotations(_config_value_region(config, "annotations")),
            idiom="ts/registerTool",
            source_path=path,
            server_id=server_id,
        ))

    if out:
        return out

    # Fallback: the one-tool-per-file `const name` + `const config` idiom.
    name_m = _TS_CONST_NAME.search(source)
    if not name_m or "registerTool" not in source:
        return []
    schema_m = _TS_CONFIG_SCHEMA_REF.search(source)
    fields = _zod_schema_fields(source, schema_m.group("ref"), context) if schema_m else []
    if not fields:
        fields = list(dict.fromkeys(_TS_ZOD_FIELD.findall(source)))
    desc_m = _TS_CONFIG_DESC.search(source)
    return [ExtractedTool(
        name=name_m.group("name"),
        description=desc_m.group("desc").strip() if desc_m else "",
        input_fields=fields,
        annotations=_parse_annotations(source),
        idiom="ts/registerTool-const",
        source_path=path,
        server_id=server_id,
    )]


def extract_typescript(source: str, path: str = "", server_id: str = "",
                       context: str = "") -> list[ExtractedTool]:
    tools: list[ExtractedTool] = []
    seen: set[str] = set()

    modern = _extract_ts_modern(source, path, server_id, context)
    if modern:
        return modern

    # Boundaries of every declaration, so one tool's field scan cannot
    # bleed into the next one's schema. Without this, adjacent tools
    # merge their fields and relation derivation is corrupted.
    boundaries = sorted(
        {m.start() for m in _TS_TOOL_CALL.finditer(source)}
        | {m.start() for m in _TS_TOOL_OBJ.finditer(source)}
    )

    def window_end(start: int) -> int:
        nxt = next((b for b in boundaries if b > start), None)
        return min(nxt, start + 600) if nxt is not None else start + 600

    for pattern, idiom in (
        (_TS_TOOL_CALL, "ts/server.tool"),
        (_TS_TOOL_OBJ, "ts/object-literal"),
    ):
        for m in pattern.finditer(source):
            name = m.group("name")
            if name in seen:
                continue
            seen.add(name)
            window = source[m.end(): window_end(m.start())]
            fields = list(dict.fromkeys(_TS_ZOD_FIELD.findall(window)))
            tools.append(
                ExtractedTool(
                    name=name,
                    description=m.group("desc").strip(),
                    input_fields=fields,
                    idiom=idiom,
                    source_path=path,
                    server_id=server_id,
                )
            )
    return tools


# ==========================================================================
# JSON manifests
# ==========================================================================

def extract_json_manifest(source: str, path: str = "", server_id: str = "") -> list[ExtractedTool]:
    try:
        data = json.loads(source)
    except (json.JSONDecodeError, ValueError):
        return []

    entries: Iterable[Any] = ()
    if isinstance(data, dict) and isinstance(data.get("tools"), list):
        entries = data["tools"]
    elif isinstance(data, list):
        entries = data

    out = []
    for e in entries:
        if not isinstance(e, dict) or "name" not in e:
            continue
        schema = e.get("inputSchema") or e.get("input_schema") or {}
        props = schema.get("properties", {}) if isinstance(schema, dict) else {}
        out.append(
            ExtractedTool(
                name=str(e["name"]),
                description=str(e.get("description", "")).strip().split("\n")[0],
                input_fields=list(props),
                idiom="json/manifest",
                source_path=path,
                server_id=server_id,
            )
        )
    return out


# ==========================================================================
# Dispatch
# ==========================================================================

def extract(source: str, path: str, server_id: str = "",
            context: str = "") -> list[ExtractedTool]:
    """`context` is the server's other sources, pooled, for cross-file
    schema resolution. Optional: single-file extraction still works."""
    lower = path.lower()
    if lower.endswith(".py"):
        return extract_python(source, path, server_id)
    if lower.endswith((".ts", ".js", ".mjs", ".tsx")):
        return extract_typescript(source, path, server_id, context)
    if lower.endswith(".json"):
        return extract_json_manifest(source, path, server_id)
    return []

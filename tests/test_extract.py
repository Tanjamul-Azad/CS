"""Extraction tests, including regressions for bugs that silently
corrupted the headline number before they were caught."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from fixtures_mcp_servers import FIXTURES  # noqa: E402
from measure.extract import extract, extract_python, extract_typescript  # noqa: E402


@pytest.mark.parametrize("source,path,expected", FIXTURES,
                         ids=[f[1] for f in FIXTURES])
def test_idioms(source, path, expected):
    assert {t.name for t in extract(source, path)} == expected


def test_python_ignores_undecorated_functions():
    src = '''
@mcp.tool()
def a(x: int) -> int:
    """Tool A."""

def b(x):
    """Not a tool."""
'''
    assert {t.name for t in extract_python(src, "s.py")} == {"a"}


def test_python_docstring_and_params():
    src = '''
@mcp.tool()
def transfer(self, recipient: str, amount: float, ctx=None) -> dict:
    """Move money.

    Longer prose that should not appear.
    """
'''
    t = extract_python(src, "s.py")[0]
    assert t.description == "Move money."
    # self/ctx are plumbing, not tool parameters
    assert t.input_fields == ["recipient", "amount"]


# --- regressions ---------------------------------------------------------

def test_regression_multiple_tools_per_file():
    """A 14-tool file once extracted as 1.

    This does not merely lose tools -- it deletes the sibling read/write
    pairs relations derive FROM, so it drove measured A0 to 100%.
    """
    src = "\n".join(
        f'''
server.registerTool(
  "tool_{i}",
  {{ description: "Tool number {i}.",
     inputSchema: {{ field_{i}: z.string() }} }},
  handler_{i}
);'''
        for i in range(5)
    )
    got = extract_typescript(src, "index.ts")
    assert {t.name for t in got} == {f"tool_{i}" for i in range(5)}


def test_regression_inline_schema_resolves():
    """Inline multi-line inputSchema once yielded zero fields.

    The region scanner stopped at the first NESTED key instead of the
    next sibling key, emptying input_fields for every tool declaring its
    schema inline -- which suppressed R2 and R5 derivation.
    """
    src = '''
server.registerTool(
  "read_text_file",
  {
    title: "Read Text File",
    description: "Read a file as text.",
    inputSchema: {
      path: z.string(),
      tail: z.number().optional(),
      head: z.number().optional(),
    },
    outputSchema: { content: z.string() },
    annotations: { readOnlyHint: true }
  },
  handler
);'''
    t = extract_typescript(src, "index.ts")[0]
    assert t.input_fields == ["path", "tail", "head"]
    assert t.output_fields == ["content"]
    assert t.annotations["readOnlyHint"] is True


def test_regression_no_field_bleed_between_tools():
    """One tool's field scan once ran into the next tool's schema."""
    src = '''
server.tool("first", "First tool.", { alpha: z.string() }, h1);
server.tool("second", "Second tool.", { beta: z.string() }, h2);
'''
    got = {t.name: t.input_fields for t in extract_typescript(src, "s.ts")}
    assert got["first"] == ["alpha"]
    assert "beta" not in got["first"]


def test_cross_file_schema_resolution():
    """Schemas defined in a sibling module resolve via pooled context."""
    decl = '''
server.registerTool("write_file",
  { description: "Write a file.", inputSchema: WriteArgs.shape }, h);
'''
    sibling = 'export const WriteArgs = z.object({ path: z.string(), content: z.string() });'
    assert extract_typescript(decl, "index.ts")[0].input_fields == []
    t = extract_typescript(decl, "index.ts", context=sibling)[0]
    assert t.input_fields == ["path", "content"]


def test_multiline_concatenated_description():
    src = '''
server.registerTool("x",
  { description: "First part. " +
                 "Second part.",
    inputSchema: { a: z.string() } }, h);
'''
    assert "Second part." in extract_typescript(src, "s.ts")[0].description


def test_malformed_sources_do_not_raise():
    assert extract("def broken(:", "x.py") == []
    assert extract("{not json", "x.json") == []
    assert extract("", "x.ts") == []
    assert extract("anything", "x.md") == []

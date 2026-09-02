"""Launch-command construction for py-published servers.

Regression for a bug caught live during the Phase 1 scale run: bare
`uvx <script-name>` treats the script name as BOTH the PyPI package to
install and the executable to run. arclat-ai/relay-mcp declares package
"relay-arclat" with console script "relay" -- `uvx relay` silently
installed a completely unrelated, abandoned PyPI package also named
"relay" (containing Python-2 syntax), which then failed for a reason
that looked like a server bug but was actually ours.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from measure.launchability import _pyproject  # noqa: E402


def test_uvx_command_uses_explicit_from_when_script_differs_from_package():
    src = """
[project]
name = "relay-arclat"
[project.scripts]
relay = "relay.cli:main"
"""
    name, cmd, note = _pyproject(src)
    assert name == "relay-arclat"
    assert cmd == "uvx --from relay-arclat relay"
    assert "relay-arclat" in cmd  # the real package name must be present


def test_uvx_command_uses_explicit_from_even_when_names_match():
    """--from is unambiguous and correct in this case too, so it is used
    unconditionally rather than only when a mismatch is detected."""
    src = """
[project]
name = "samename"
[project.scripts]
samename = "samename.cli:main"
"""
    _, cmd, _ = _pyproject(src)
    assert cmd == "uvx --from samename samename"


def test_poetry_style_scripts_also_get_explicit_from():
    src = """
[tool.poetry]
name = "poetrypkg"
[tool.poetry.scripts]
poetrycmd = "poetrypkg.cli:main"
"""
    name, cmd, _ = _pyproject(src)
    assert name == "poetrypkg"
    assert cmd == "uvx --from poetrypkg poetrycmd"


def test_no_scripts_falls_back_to_module_guess():
    src = '[project]\nname = "my-pkg"\n'
    name, cmd, note = _pyproject(src)
    assert name == "my-pkg"
    assert cmd == "uvx --from my-pkg python -m my_pkg"
    assert "guessed" in note


def test_no_name_returns_none():
    assert _pyproject("[project]\n") == (None, None, "pyproject has no name")


def test_unparseable_toml_returns_none():
    name, cmd, note = _pyproject("not valid toml [[[")
    assert name is None and cmd is None
    assert "unparseable" in note

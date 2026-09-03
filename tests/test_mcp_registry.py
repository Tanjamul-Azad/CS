"""Official MCP Registry client parsing.

The registry is a materially better sampling frame than GitHub keyword
search: entries are self-registered as MCP servers, package identifiers
are author-declared (no script-name/package-name guessing), and required
secrets are author-flagged rather than regex-inferred from source.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from measure.mcp_registry import _parse_entry, _parse_package  # noqa: E402


def test_npm_package_gives_npx_command():
    p = _parse_package({"registryType": "npm", "identifier": "@a/b",
                        "version": "1.0.0", "transport": {"type": "stdio"}})
    assert p.command == "npx -y @a/b"
    assert p.stdio_launchable is True
    assert p.needs_credentials is False


def test_pypi_package_gives_uvx_command():
    p = _parse_package({"registryType": "pypi", "identifier": "some-pkg",
                        "version": "2.0", "transport": {"type": "stdio"}})
    assert p.command == "uvx some-pkg"


def test_required_secret_env_var_flags_credentials():
    p = _parse_package({
        "registryType": "npm", "identifier": "x", "version": "1",
        "transport": {"type": "stdio"},
        "environmentVariables": [
            {"name": "API_KEY", "isRequired": True, "isSecret": True},
            {"name": "OPTIONAL_FLAG", "isRequired": False, "isSecret": False},
        ],
    })
    assert p.needs_credentials is True
    assert p.required_secrets == ["API_KEY"]
    assert p.optional_env == ["OPTIONAL_FLAG"]


def test_required_but_non_secret_env_var_is_not_a_credential():
    """A required plain-string config value (e.g. a base URL) is not the
    same obstacle as a required secret -- conflating them would exclude
    servers that need no credential at all."""
    p = _parse_package({
        "registryType": "npm", "identifier": "x", "version": "1",
        "transport": {"type": "stdio"},
        "environmentVariables": [
            {"name": "BASE_URL", "isRequired": True, "isSecret": False},
        ],
    })
    assert p.needs_credentials is False


def test_sse_transport_is_not_stdio_launchable():
    p = _parse_package({"registryType": "npm", "identifier": "x",
                        "version": "1", "transport": {"type": "sse"}})
    assert p.stdio_launchable is False


def test_entry_runnable_candidates_filters_correctly():
    entry = _parse_entry({
        "server": {
            "name": "ai.example/two-packages",
            "title": "Example",
            "description": "desc",
            "packages": [
                {"registryType": "npm", "identifier": "free-one",
                 "version": "1", "transport": {"type": "stdio"}},
                {"registryType": "npm", "identifier": "needs-key",
                 "version": "1", "transport": {"type": "stdio"},
                 "environmentVariables": [
                     {"name": "KEY", "isRequired": True, "isSecret": True}]},
            ],
        },
        "_meta": {"io.modelcontextprotocol.registry/official": {
            "status": "active"}},
    })
    names = [p.identifier for p in entry.runnable_candidates]
    assert names == ["free-one"]


def test_entry_with_only_remotes_has_no_candidates():
    entry = _parse_entry({
        "server": {"name": "ai.example/remote-only", "title": "T",
                   "description": "d",
                   "remotes": [{"type": "streamable-http", "url": "https://x"}]},
        "_meta": {},
    })
    assert entry.has_remotes is True
    assert entry.runnable_candidates == []


def test_repository_url_extracted_when_present():
    entry = _parse_entry({
        "server": {"name": "n", "title": "t", "description": "d",
                   "repository": {"url": "https://github.com/x/y",
                                  "source": "github"}},
        "_meta": {},
    })
    assert entry.repository_url == "https://github.com/x/y"


def test_missing_repository_is_none_not_keyerror():
    entry = _parse_entry({
        "server": {"name": "n", "title": "t", "description": "d"},
        "_meta": {},
    })
    assert entry.repository_url is None

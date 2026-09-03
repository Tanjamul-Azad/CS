"""
Client for the official MCP Registry (registry.modelcontextprotocol.io).

This is a materially better sampling frame than GitHub keyword search for
Phase 1's real-server audit, for three reasons discovered by inspecting
its schema directly:

  1. Every entry here is a server its author explicitly REGISTERED as an
     MCP server -- not a repo that merely carries an "mcp" topic tag,
     which is how GitHub search let hobby/abandoned/unrelated projects
     into the corpus.

  2. The `packages[].identifier` field is the exact, author-declared
     installable package name. Our own launchability.py had to GUESS a
     launch command by parsing package.json/pyproject.toml, and that
     guessing produced a real bug (arclat-ai/relay-mcp: script name used
     as the package name, installing a wrong, unrelated PyPI package).
     The registry needs no guessing -- registryType + identifier is
     the launch command, directly.

  3. `packages[].environmentVariables[].isRequired` / `.isSecret` are
     author-declared credential requirements. Our own credential
     detection was a source-code regex scan that MISSED at least one
     real case (Sequenzy's server prints "Missing MCP API key" only at
     runtime, invisible to static analysis). The registry's declared
     flags are authoritative where they exist.

None of this makes the registry a complete population -- a server can
still be broken, abandoned, or lie about its own requirements -- but it
removes several entire categories of failure this project already paid
to discover the hard way.

About a quarter of registry entries have `packages` (locally installable,
stdio) at all; the rest are `remotes` (hosted HTTP services requiring the
operator's own auth/network, out of scope for a sandboxed local audit).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Iterator

BASE = "https://registry.modelcontextprotocol.io/v0/servers"
USER_AGENT = "mcp-behavioral-integrity-research/0.1 (academic study)"


@dataclass
class RegistryPackage:
    registry_type: str          # "npm" | "pypi" | ...
    identifier: str             # exact installable package name
    version: str
    transport: str               # "stdio" | "sse" | ...
    required_secrets: list[str] = field(default_factory=list)
    optional_env: list[str] = field(default_factory=list)

    @property
    def stdio_launchable(self) -> bool:
        return self.transport == "stdio" and self.registry_type in ("npm", "pypi")

    @property
    def needs_credentials(self) -> bool:
        return bool(self.required_secrets)

    @property
    def command(self) -> str:
        if self.registry_type == "npm":
            return f"npx -y {self.identifier}"
        if self.registry_type == "pypi":
            return f"uvx {self.identifier}"
        return ""


@dataclass
class RegistryEntry:
    name: str                   # e.g. "ai.adeu/adeu"
    title: str
    description: str
    repository_url: str | None
    packages: list[RegistryPackage] = field(default_factory=list)
    has_remotes: bool = False
    status: str = "active"

    @property
    def runnable_candidates(self) -> list[RegistryPackage]:
        return [p for p in self.packages
               if p.stdio_launchable and not p.needs_credentials]


def _get(url: str, retries: int = 6) -> dict:
    """A walk over 20,000+ pages WILL hit a transient network hiccup --
    it already has, once, in practice, taking the entire harvest down and
    losing everything after the last checkpoint because a plain
    TimeoutError is not a urllib.error.URLError and was not caught. Catch
    broadly here; a real, persistent outage still surfaces after `retries`
    with a real traceback, but a lone dropped connection does not cost a
    ten-minute walk.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read())
        except Exception:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            time.sleep(min(2 * (attempt + 1), 20))
    return {}


def _parse_package(p: dict) -> RegistryPackage:
    env = p.get("environmentVariables", []) or []
    return RegistryPackage(
        registry_type=p.get("registryType", ""),
        identifier=p.get("identifier", ""),
        version=p.get("version", ""),
        transport=(p.get("transport") or {}).get("type", ""),
        required_secrets=[e["name"] for e in env
                          if e.get("isRequired") and e.get("isSecret")],
        optional_env=[e["name"] for e in env
                     if not (e.get("isRequired") and e.get("isSecret"))],
    )


def _parse_entry(item: dict) -> RegistryEntry:
    srv = item["server"]
    meta = (item.get("_meta", {})
           .get("io.modelcontextprotocol.registry/official", {}))
    return RegistryEntry(
        name=srv.get("name", ""),
        title=srv.get("title", ""),
        description=srv.get("description", ""),
        repository_url=(srv.get("repository") or {}).get("url"),
        packages=[_parse_package(p) for p in srv.get("packages", []) or []],
        has_remotes=bool(srv.get("remotes")),
        status=meta.get("status", "active"),
    )


def walk_registry(
    limit_per_page: int = 100,
    max_pages: int = 10_000,
    delay: float = 0.15,
    only_latest: bool = True,
    start_cursor: str | None = None,
) -> Iterator[tuple[RegistryEntry, str | None]]:
    """Every entry in the official registry, paginated, each yielded with
    the cursor value that would RESUME right after it.

    `only_latest` skips superseded versions -- the registry keeps full
    version history, and without this filter every server appears once
    per release ever published. `start_cursor` resumes a walk broken by a
    prior failure instead of re-scanning from the beginning; the registry
    turned out to run past 21,000 entries, far more than an early
    50-page probe suggested, so re-walking the whole thing on every
    transient failure is not a viable retry strategy.
    """
    cursor = start_cursor
    version_q = "&version=latest" if only_latest else ""
    for _ in range(max_pages):
        url = f"{BASE}?limit={limit_per_page}{version_q}"
        if cursor:
            url += f"&cursor={cursor}"
        data = _get(url)
        items = data.get("servers", [])
        if not items:
            return
        cursor = data.get("metadata", {}).get("nextCursor")
        for item in items:
            yield _parse_entry(item), cursor
        if not cursor:
            return
        time.sleep(delay)

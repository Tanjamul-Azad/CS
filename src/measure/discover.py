"""
Discover MCP server repositories on GitHub.

Sampling frame for D1. The population we want is "MCP servers an agent
might actually be pointed at", which has no registry with an API, so we
approximate it with GitHub search over topics and names.

Known and reportable biases (docs/06-dataset-plan.md section 3):

  * GitHub-only. Servers shipped exclusively via npm/PyPI, or privately,
    are invisible here.
  * Search relevance ordering is opaque and caps at 1000 results per
    query, so we stratify by star bucket to reach the long tail rather
    than only the popular head. This matters directly: our own
    preliminary data suggested A0 rate may be driven by server
    tool-count, and small unpopular servers are exactly where small
    tool-counts live. Sampling only the head would bias the headline.
  * A repo naming itself an MCP server is taken at its word; we do not
    verify it implements the protocol beyond finding tool declarations.

Search is 30 req/min authenticated. We stay well under.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse

from .harvest import Repo, _request

SEARCH = "https://api.github.com/search/repositories"

# Star buckets, so the long tail is represented rather than only the head.
STAR_BUCKETS = ["0..2", "3..9", "10..49", "50..199", ">=200"]

QUERIES = [
    "topic:mcp-server",
    "topic:mcp",
    "topic:model-context-protocol",
    '"mcp server" in:name',
    '"mcp-server" in:name',
    '"model context protocol" in:description',
]


def _search_page(q: str, page: int, token: str | None) -> list[dict]:
    url = f"{SEARCH}?q={urllib.parse.quote(q)}&per_page=100&page={page}"
    try:
        return json.loads(_request(url, token)).get("items", [])
    except urllib.error.HTTPError as e:
        if e.code in (403, 422):        # rate limited, or past the 1000 cap
            return []
        raise
    except Exception:  # noqa: BLE001
        return []


def discover(
    token: str | None,
    target: int = 500,
    max_pages: int = 3,
    delay: float = 2.2,
    verbose: bool = True,
) -> list[Repo]:
    """Repos likely to be MCP servers, deduped, stratified by stars."""
    found: dict[str, Repo] = {}

    for base in QUERIES:
        for bucket in STAR_BUCKETS:
            if len(found) >= target:
                break
            q = f"{base} stars:{bucket}"
            for page in range(1, max_pages + 1):
                items = _search_page(q, page, token)
                if not items:
                    break
                for it in items:
                    full = it.get("full_name", "")
                    if not full or full in found:
                        continue
                    owner, _, name = full.partition("/")
                    found[full] = Repo(
                        owner, name,
                        it.get("default_branch") or "main",
                        kind="official" if owner in (
                            "modelcontextprotocol",) else "community",
                    )
                time.sleep(delay)
                if len(items) < 100:
                    break
            if verbose:
                print(f"  [{len(found):4}] {q}")

    return list(found.values())[:target]

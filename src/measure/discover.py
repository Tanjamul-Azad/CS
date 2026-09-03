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

Metadata (stars, owner type, last push) is captured alongside each repo
-- not just used as a transient query filter -- because Phase 1's real-
server audit found the population skews heavily toward small, sometimes
abandoned hobby projects (47% of one candidate pool had never even been
published to a package registry). Without stored star/activity signals
there is no way to build an "official/popular" tier after the fact for
comparison against the long tail, which is exactly the split (official
9% A0 vs community 57% A0) that produced D1's strongest finding.

Search is 30 req/min authenticated. We stay well under.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
from pathlib import Path

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

METADATA_OUT = (Path(__file__).resolve().parents[2] / "data" / "processed"
               / "repo_metadata.json")


def _search_page(q: str, page: int, token: str | None,
                 sort_stars: bool = True) -> list[dict]:
    url = f"{SEARCH}?q={urllib.parse.quote(q)}&per_page=100&page={page}"
    if sort_stars:
        url += "&sort=stars&order=desc"
    try:
        return json.loads(_request(url, token)).get("items", [])
    except urllib.error.HTTPError as e:
        if e.code in (403, 422):        # rate limited, or past the 1000 cap
            return []
        raise
    except Exception:  # noqa: BLE001
        return []


def _extract_metadata(item: dict) -> dict:
    return {
        "stars": item.get("stargazers_count", 0),
        "owner_type": (item.get("owner") or {}).get("type", "User"),
        "pushed_at": item.get("pushed_at"),
        "created_at": item.get("created_at"),
        "description": (item.get("description") or "")[:200],
        "archived": item.get("archived", False),
        "fork": item.get("fork", False),
    }


def discover_with_metadata(
    token: str | None,
    target: int = 500,
    max_pages: int = 3,
    delay: float = 2.2,
    verbose: bool = True,
    save_metadata: bool = True,
) -> tuple[list[Repo], dict[str, dict]]:
    """Repos likely to be MCP servers, deduped, stratified by stars, with
    the star/owner-type/activity signals kept for later tiering."""
    found: dict[str, Repo] = {}
    meta: dict[str, dict] = {}

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
                    meta[full] = _extract_metadata(it)
                time.sleep(delay)
                if len(items) < 100:
                    break
            if verbose:
                print(f"  [{len(found):4}] {q}")

    repos = list(found.values())[:target]
    meta = {r.server_id: meta[r.server_id] for r in repos}

    if save_metadata:
        METADATA_OUT.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        if METADATA_OUT.exists():
            try:
                existing = json.loads(METADATA_OUT.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        existing.update(meta)
        METADATA_OUT.write_text(json.dumps(existing, indent=1), encoding="utf-8")

    return repos, meta


def discover(
    token: str | None,
    target: int = 500,
    max_pages: int = 3,
    delay: float = 2.2,
    verbose: bool = True,
) -> list[Repo]:
    """Backward-compatible wrapper: repos only, metadata still saved to disk."""
    repos, _ = discover_with_metadata(token, target, max_pages, delay, verbose)
    return repos

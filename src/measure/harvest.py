"""
Harvest MCP tool declarations from public source repositories.

Ethics and method (docs/06-dataset-plan.md section 2): static extraction from
public source artifacts ONLY. We never connect to, execute, or probe a
live MCP server. Nothing here sends a request to anyone's deployed
service.

Rate-limit design: the GitHub REST API allows 60 requests/hour
unauthenticated (5,000 with a token), but raw.githubusercontent.com is
not metered the same way. So we spend exactly ONE API call per repo to
list its tree, then pull candidate files over raw. A full corpus is
therefore feasible even without a token, and comfortable with one.

Set GITHUB_TOKEN in .env for a larger harvest.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .extract import ExtractedTool, extract

USER_AGENT = "mcp-behavioral-integrity-research/0.1 (academic study)"

CANDIDATE_SUFFIXES = (".py", ".ts", ".js", ".mjs")
CANDIDATE_HINTS = ("server", "tool", "mcp", "index", "main", "app")
SKIP_DIRS = ("test", "tests", "__tests__", "spec", "example", "examples",
             "sample", "node_modules", "dist", "build", "__pycache__",
             "docs", "fixtures", "mock", "mocks")

MAX_FILE_BYTES = 400_000


@dataclass
class Repo:
    owner: str
    name: str
    ref: str = "HEAD"
    kind: str = "community"          # official | vendor | community

    @property
    def server_id(self) -> str:
        return f"{self.owner}/{self.name}"


def _request(url: str, token: str | None = None, accept: str | None = None) -> bytes:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", USER_AGENT)
    if accept:
        req.add_header("Accept", accept)
    if token and "api.github.com" in url:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def list_tree(repo: Repo, token: str | None = None) -> list[str]:
    """One API call: the full recursive file listing for a repo."""
    url = (f"https://api.github.com/repos/{repo.owner}/{repo.name}"
           f"/git/trees/{repo.ref}?recursive=1")
    try:
        data = json.loads(_request(url, token))
    except urllib.error.HTTPError as e:
        print(f"    tree fetch failed ({e.code}) for {repo.server_id}")
        return []
    except Exception as e:  # noqa: BLE001
        print(f"    tree fetch failed ({type(e).__name__}) for {repo.server_id}")
        return []

    if data.get("truncated"):
        print(f"    note: tree truncated for {repo.server_id}")

    return [n["path"] for n in data.get("tree", []) if n.get("type") == "blob"]


def is_candidate(path: str) -> bool:
    low = path.lower()
    if not low.endswith(CANDIDATE_SUFFIXES):
        return low.endswith("tools.json")
    # Match on whole path segments so that e.g. __tests__ and test.ts are
    # both excluded, while a legitimate "latest/" directory is not.
    segments = low.split("/")
    if any(seg in SKIP_DIRS for seg in segments):
        return False
    if segments[-1].removesuffix(".ts").removesuffix(".py").endswith((".test", ".spec")):
        return False
    return any(h in low for h in CANDIDATE_HINTS)


def fetch_raw(repo: Repo, path: str) -> str | None:
    """Not metered against the API rate limit."""
    url = (f"https://raw.githubusercontent.com/{repo.owner}/{repo.name}"
           f"/{repo.ref}/{path}")
    try:
        blob = _request(url)
    except Exception:  # noqa: BLE001
        return None
    if len(blob) > MAX_FILE_BYTES:
        return None
    try:
        return blob.decode("utf-8")
    except UnicodeDecodeError:
        return None


def sub_server_id(repo: Repo, path: str) -> str:
    """Resolve the individual MCP server a file belongs to.

    Monorepos (notably the official reference collection) ship many
    independent servers under src/<name>/ or packages/<name>/. Relations
    are only meaningful WITHIN one server -- a read tool in the sqlite
    server cannot corroborate a write in the slack server -- so treating
    a monorepo as a single server would fabricate cross-server relations
    and inflate measured auditability.
    """
    parts = path.split("/")
    for marker in ("src", "packages", "servers"):
        if len(parts) >= 3 and parts[0] == marker:
            return f"{repo.server_id}/{parts[1]}"
    return repo.server_id


def harvest_repo(
    repo: Repo,
    token: str | None = None,
    max_files: int = 120,
    delay: float = 0.05,
    quiet: bool = False,
) -> list[ExtractedTool]:
    """Fetch a repo's candidate files, then extract per server.

    Extraction is deferred until every file for a server is in hand,
    because schemas are routinely defined in one module and referenced
    from another. Extracting file-by-file loses those fields, which
    suppresses R2/R5 and makes the ecosystem look less auditable than it
    is.
    """
    paths = [p for p in list_tree(repo, token) if is_candidate(p)][:max_files]
    if not paths:
        return []

    # server_id -> {path: source}
    by_server: dict[str, dict[str, str]] = {}
    for path in paths:
        src = fetch_raw(repo, path)
        if not src:
            continue
        by_server.setdefault(sub_server_id(repo, path), {})[path] = src
        time.sleep(delay)

    out: list[ExtractedTool] = []
    for sid, files in by_server.items():
        for path, src in files.items():
            # Everything else this server ships, as resolution context.
            context = "\n".join(v for k, v in files.items() if k != path)
            out.extend(
                t for t in extract(src, path, server_id=sid, context=context)
                if t.name
            )

    if not quiet:
        print(f"  {repo.server_id}: {len(paths)} files -> "
              f"{len(out)} tools / {len(by_server)} servers")
    return out


def dedup(tools: list[ExtractedTool]) -> list[ExtractedTool]:
    """One record per (server, tool name).

    Real repos re-declare the same tool across a schema file and a
    handler file; counting both would inflate the corpus and bias every
    proportion we report.
    """
    best: dict[tuple[str, str], ExtractedTool] = {}
    for t in tools:
        key = (t.server_id, t.name)
        cur = best.get(key)
        # Prefer the record carrying the most information.
        score = (len(t.input_fields), len(t.description))
        if cur is None or score > (len(cur.input_fields), len(cur.description)):
            best[key] = t
    return list(best.values())


def write_corpus(tools: list[ExtractedTool], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for t in tools:
            f.write(json.dumps(t.to_json()) + "\n")


def load_corpus(path: Path) -> list[ExtractedTool]:
    tools = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                tools.append(ExtractedTool(**json.loads(line)))
    return tools


def get_token() -> str | None:
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    env = Path(__file__).resolve().parents[2] / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("GITHUB_TOKEN="):
                val = line.split("=", 1)[1].strip()
                return val or None
    return None

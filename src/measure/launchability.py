"""
Phase 1 step 1: can these servers actually be launched?

Of 295 harvested servers, 123 have both reads and writes and are therefore
worth auditing. This works out which of them a third party could actually
run, and -- just as importantly -- why the rest cannot.

That failure distribution is a result in its own right. "How much of the
MCP ecosystem can be independently audited at all?" has not been measured,
and the answer bounds what any client-side defense can cover in practice.

Static only: we read manifests from the repository. Nothing is installed
or executed here; that happens later, in a sandbox, deliberately.

Launch classes:
  npm-published   package.json has a name and a bin entry -> npx <name>
  npm-local       package.json but no bin -> needs a build step
  py-published    pyproject/setup with a console script -> uvx <name>
  py-module       python package, run via -m
  manifest-only   declarations found, no runnable manifest
  unknown         no manifest recovered

Blockers are recorded separately from launch class, because a server can
be perfectly launchable and still unusable for us (needs an API key, or
talks to a paid service).
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import asdict, dataclass, field
from typing import Any

from .harvest import Repo, fetch_raw

# Signals that a server cannot run without credentials or an external service.
CREDENTIAL_PATTERNS = [
    re.compile(r"\b[A-Z][A-Z0-9_]{2,}_(API_KEY|TOKEN|SECRET|PASSWORD|CREDENTIALS)\b"),
    re.compile(r"\bprocess\.env\.[A-Z][A-Z0-9_]*(KEY|TOKEN|SECRET|PASSWORD)\b"),
    re.compile(r"os\.environ\[[\"'][A-Z0-9_]*(KEY|TOKEN|SECRET|PASSWORD)"),
    re.compile(r"getenv\([\"'][A-Z0-9_]*(KEY|TOKEN|SECRET|PASSWORD)"),
]

EXTERNAL_HINTS = (
    "openai", "anthropic", "slack", "github.com/api", "stripe", "notion",
    "jira", "atlassian", "salesforce", "aws", "azure", "gcloud",
    "postgres", "mysql", "mongodb", "redis", "supabase", "firebase",
)


@dataclass
class Launchability:
    server_id: str
    launch_class: str = "unknown"
    package: str | None = None          # installable name
    command: str | None = None          # best-guess launch command
    needs_credentials: bool = False
    credential_names: list[str] = field(default_factory=list)
    external_services: list[str] = field(default_factory=list)
    tools: int = 0
    notes: str = ""

    @property
    def runnable_standalone(self) -> bool:
        """Launchable AND needs nothing we cannot provide in a sandbox."""
        return (self.launch_class in ("npm-published", "py-published", "py-module")
                and not self.needs_credentials
                and not self.external_services)

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["runnable_standalone"] = self.runnable_standalone
        return d


def _repo_of(server_id: str) -> tuple[Repo, str]:
    """Split 'owner/repo/subdir' into a Repo and its subpath."""
    parts = server_id.split("/")
    repo = Repo(parts[0], parts[1], "main")
    return repo, "/".join(parts[2:])


def _try(repo: Repo, paths: list[str]) -> tuple[str, str] | None:
    for p in paths:
        src = fetch_raw(repo, p)
        if src:
            return p, src
    return None


def _npm(src: str) -> tuple[str | None, str | None, str]:
    try:
        pkg = json.loads(src)
    except (json.JSONDecodeError, ValueError):
        return None, None, "package.json unparseable"
    name = pkg.get("name")
    bins = pkg.get("bin")
    if not name:
        return None, None, "package.json has no name"
    if bins:
        return name, f"npx -y {name}", ""
    return name, None, "no bin entry; needs a build step"


def _pyproject(src: str) -> tuple[str | None, str | None, str]:
    try:
        data = tomllib.loads(src)
    except Exception:  # noqa: BLE001
        return None, None, "pyproject unparseable"
    proj = data.get("project", {})
    name = proj.get("name") or data.get("tool", {}).get("poetry", {}).get("name")
    scripts = proj.get("scripts") or data.get("tool", {}).get("poetry", {}).get(
        "scripts") or {}
    if not name:
        return None, None, "pyproject has no name"
    if scripts:
        return name, f"uvx {next(iter(scripts))}", ""
    return name, f"uvx --from {name} python -m {name.replace('-', '_')}", \
        "no console script; guessed -m"


def assess(server_id: str, n_tools: int, sources: str = "") -> Launchability:
    """Static launchability assessment for one server."""
    out = Launchability(server_id=server_id, tools=n_tools)
    repo, sub = _repo_of(server_id)
    prefix = f"{sub}/" if sub else ""

    hit = _try(repo, [f"{prefix}package.json", "package.json"])
    if hit:
        _, src = hit
        name, cmd, note = _npm(src)
        out.package, out.command, out.notes = name, cmd, note
        out.launch_class = "npm-published" if cmd else "npm-local"
    else:
        hit = _try(repo, [f"{prefix}pyproject.toml", "pyproject.toml"])
        if hit:
            _, src = hit
            name, cmd, note = _pyproject(src)
            out.package, out.command, out.notes = name, cmd, note
            out.launch_class = "py-published" if cmd and "guessed" not in note \
                else "py-module"
        elif _try(repo, [f"{prefix}setup.py", "setup.py"]):
            out.launch_class = "py-module"
            out.notes = "setup.py only"
        else:
            out.launch_class = "manifest-only" if n_tools else "unknown"
            out.notes = "no package manifest found"

    # Credentials and external dependencies, from the server's own sources.
    blob = sources or ""
    if blob:
        names = set()
        for pat in CREDENTIAL_PATTERNS:
            for m in pat.finditer(blob):
                names.add(m.group(0)[:48])
        out.credential_names = sorted(names)[:8]
        out.needs_credentials = bool(names)
        low = blob.lower()
        out.external_services = sorted(
            {h for h in EXTERNAL_HINTS if h in low})[:8]
    return out

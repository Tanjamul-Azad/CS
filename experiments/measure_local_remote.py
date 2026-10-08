"""M1: how many registry servers run locally, and how many of those need the network.

Walks the official MCP registry (/v0.1/servers, latest version of each server),
saves the raw listing, and counts:

* local (``packages`` with stdio transport) versus remote (``remotes``) servers;
* among local servers, how many declare a secret environment variable (an API
  key or token), which we use as the declared signal that the server calls an
  outside service with the user's credential.

The declared signal is a lower bound on network use: a server can reach the
network without declaring a key. The output states this.

    python experiments/measure_local_remote.py
"""

from __future__ import annotations

import collections
import datetime as dt
import gzip
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://registry.modelcontextprotocol.io/v0.1/servers"
UA = "effectseal-measurement/0.1 (academic study)"
STAMP = dt.date.today().isoformat()
RAW = ROOT / "data" / "raw" / f"registry_latest_{STAMP}.jsonl.gz"
OUT = ROOT / "artifact" / "results" / f"m1_local_remote_{STAMP}.json"
KEY_WORDS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "AUTH")


def get(url: str) -> dict:
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception:  # noqa: BLE001
            if attempt == 5:
                raise
            time.sleep(2 * (attempt + 1))
    return {}


def harvest() -> list[dict]:
    items, cursor = [], None
    while True:
        query = {"limit": 100, "version": "latest"}
        if cursor:
            query["cursor"] = cursor
        page = get(f"{BASE}?{urllib.parse.urlencode(query)}")
        items.extend(page.get("servers", []))
        cursor = (page.get("metadata") or {}).get("nextCursor")
        print(f"\r{len(items)} servers", end="", file=sys.stderr)
        if not cursor:
            break
    print(file=sys.stderr)
    return items


def latest_only(items: list[dict]) -> dict[str, dict]:
    """Keep one record per server name: the one the registry marks latest,
    else the most recently published."""
    best: dict[str, dict] = {}
    for item in items:
        server = item.get("server", {})
        meta = item.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {})
        name = server.get("name")
        if not name or meta.get("status", "active") != "active":
            continue
        key = (bool(meta.get("isLatest")), meta.get("publishedAt", ""))
        if name not in best or key > best[name][0]:
            best[name] = (key, server)
    return {name: server for name, (_, server) in best.items()}


def classify(server: dict) -> dict:
    packages = server.get("packages") or []
    stdio = [p for p in packages if (p.get("transport") or {}).get("type") == "stdio"]
    env = [e for p in stdio for e in (p.get("environmentVariables") or [])]
    secret = [e for e in env if e.get("isSecret")]
    keyish = [e for e in env if any(w in (e.get("name") or "").upper() for w in KEY_WORDS)]
    return {
        "local": bool(stdio),
        "remote": bool(server.get("remotes")),
        "registry_types": sorted({p.get("registryType", "") for p in stdio}),
        "declares_secret": bool(secret),
        "declares_key_like_env": bool(keyish),
    }


def main() -> None:
    items = harvest()
    RAW.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(RAW, "wt", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item) + "\n")
    servers = latest_only(items)
    rows = {name: classify(s) for name, s in servers.items()}
    kind = collections.Counter(
        "both" if r["local"] and r["remote"] else
        "local only" if r["local"] else "remote only" if r["remote"] else "neither"
        for r in rows.values())
    local = [r for r in rows.values() if r["local"]]
    types = collections.Counter(t for r in local for t in r["registry_types"])
    summary = {
        "harvested_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": BASE + "?version=latest",
        "raw_records": len(items),
        "active_servers": len(rows),
        "by_deployment": dict(kind),
        "local_servers": len(local),
        "local_by_registry_type": dict(types),
        "local_declaring_secret_env": sum(r["declares_secret"] for r in local),
        "local_declaring_key_like_env": sum(r["declares_key_like_env"] for r in local),
        "note": ("A declared secret or key-like variable is a lower bound on servers "
                 "that call an outside service; undeclared network use is not counted."),
        "raw_file": str(RAW.relative_to(ROOT)).replace("\\", "/"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        raise SystemExit(f"{OUT} exists; never overwrite an earlier run")
    OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

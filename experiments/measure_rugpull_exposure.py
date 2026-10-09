"""M2: how exposed are approved local servers to a rug pull.

Reuses the M1 registry harvest (no re-harvest) for the list of local npm/PyPI
servers, then fetches each package's release metadata from its public registry
and measures, per package:

* release velocity: total versions, versions published in the last 90 days,
  days since the most recent release;
* moving target: whether the version pinned in the MCP registry is still the
  current latest version, and how many versions were published after it (an
  approved server whose pin tracks latest gets whatever the maintainer ships
  next, as postmark-mcp 1.0.16 did);
* control concentration: npm maintainer count and whether a single account can
  publish (the public APIs do not expose maintainer-change history, so we
  measure single-maintainer concentration rather than observed hand-offs; PyPI
  does not expose maintainers over the JSON API and is recorded as unknown).

A declared package that is gone (404) or renamed is recorded with its reason
and left out of the rates. The fetch is cached and resumable.

    python experiments/measure_rugpull_exposure.py [--limit N] [--as-of YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import gzip
import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "registry_latest_2026-10-08.jsonl.gz"
HARVEST_DATE = "2026-10-08"
STAMP = dt.date.today().isoformat()
CACHE = ROOT / "data" / "raw" / f"m2_metadata_cache_{HARVEST_DATE}.jsonl"
OUT = ROOT / "artifact" / "results" / f"m2_rugpull_exposure_{STAMP}.json"
UA = {"User-Agent": "effectseal-measurement/0.1 (academic study)"}


def local_packages() -> list[dict]:
    """One (registry, identifier, pinned_version) per active local server."""
    seen: dict[tuple, dict] = {}
    with gzip.open(RAW, "rt", encoding="utf-8") as fh:
        for line in fh:
            item = json.loads(line)
            server = item.get("server", {})
            meta = item.get("_meta", {}).get(
                "io.modelcontextprotocol.registry/official", {})
            if meta.get("status", "active") != "active":
                continue
            for pkg in server.get("packages") or []:
                if (pkg.get("transport") or {}).get("type") != "stdio":
                    continue
                reg = pkg.get("registryType")
                ident = pkg.get("identifier")
                if reg not in ("npm", "pypi") or not ident:
                    continue
                key = (reg, ident)
                if key not in seen:
                    seen[key] = {"registry": reg, "identifier": ident,
                                 "pinned_version": pkg.get("version"),
                                 "server_name": server.get("name")}
                break
    return list(seen.values())


def get(url: str) -> dict:
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as error:
            if error.code in (404, 403, 410):
                return {"_http_error": error.code}
            if attempt == 4:
                return {"_http_error": error.code}
            time.sleep(1.5 * (attempt + 1))
        except Exception:  # noqa: BLE001
            if attempt == 4:
                return {"_fetch_error": True}
            time.sleep(1.5 * (attempt + 1))
    return {"_fetch_error": True}


def parse_iso(value: str) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def npm_metadata(ident: str) -> dict:
    data = get(f"https://registry.npmjs.org/{ident}")
    if data.get("_http_error") or data.get("_fetch_error"):
        return {"error": f"npm {data.get('_http_error', 'fetch')}"}
    times = data.get("time", {}) or {}
    versions = [v for v in (data.get("versions") or {}) if v in times]
    latest = (data.get("dist-tags") or {}).get("latest")
    release_dates = {v: times[v] for v in versions}
    return {"versions": sorted(versions), "latest": latest,
            "release_dates": release_dates,
            "maintainer_count": len(data.get("maintainers") or [])}


def pypi_metadata(ident: str) -> dict:
    data = get(f"https://pypi.org/pypi/{ident}/json")
    if data.get("_http_error") or data.get("_fetch_error"):
        return {"error": f"pypi {data.get('_http_error', 'fetch')}"}
    releases = data.get("releases") or {}
    release_dates = {}
    for ver, files in releases.items():
        stamps = [f.get("upload_time_iso_8601") for f in files if f.get("upload_time_iso_8601")]
        if stamps:
            release_dates[ver] = min(stamps)
    return {"versions": sorted(release_dates), "latest": (data.get("info") or {}).get("version"),
            "release_dates": release_dates, "maintainer_count": None}


def fetch_all(packages: list[dict]) -> dict:
    done: dict[str, dict] = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                done[row["key"]] = row
    handle = CACHE.open("a", encoding="utf-8")
    for index, pkg in enumerate(packages):
        key = f"{pkg['registry']}:{pkg['identifier']}"
        if key in done:
            continue
        meta = npm_metadata(pkg["identifier"]) if pkg["registry"] == "npm" \
            else pypi_metadata(pkg["identifier"])
        row = {"key": key, **pkg, **meta}
        done[key] = row
        handle.write(json.dumps(row) + "\n")
        handle.flush()
        if index % 50 == 0:
            print(f"\r  fetched {len(done)}/{len(packages)}", end="", file=sys.stderr, flush=True)
        time.sleep(0.05)
    print(file=sys.stderr)
    handle.close()
    return done


def analyze(packages: list[dict], meta: dict, as_of: dt.datetime) -> dict:
    window = as_of - dt.timedelta(days=90)
    rows, errors = [], collections.Counter()
    for pkg in packages:
        row = meta.get(f"{pkg['registry']}:{pkg['identifier']}", {})
        if row.get("error") or not row.get("release_dates"):
            errors[row.get("error", "no releases")] += 1
            continue
        dates = {v: parse_iso(d) for v, d in row["release_dates"].items()}
        dates = {v: d for v, d in dates.items() if d}
        if not dates:
            errors["unparsable dates"] += 1
            continue
        pinned = pkg["pinned_version"]
        latest = row.get("latest")
        ordered = sorted(dates, key=lambda v: dates[v])
        after_pinned = (len(ordered) - 1 - ordered.index(pinned)
                        if pinned in ordered else None)
        last_release = max(dates.values())
        rows.append({
            "registry": pkg["registry"], "identifier": pkg["identifier"],
            "versions_total": len(dates),
            "releases_90d": sum(1 for d in dates.values() if d >= window),
            "days_since_last_release": (as_of - last_release).days,
            "pinned_is_latest": (pinned == latest) if (pinned and latest) else None,
            "versions_after_pinned": after_pinned,
            "maintainer_count": row.get("maintainer_count"),
        })
    npm_rows = [r for r in rows if r["registry"] == "npm"]

    def frac(predicate, subset=rows):
        n = [r for r in subset if predicate(r) is not None]
        return (sum(1 for r in n if predicate(r)) / len(n), len(n)) if n else (None, 0)

    def med(field, subset=rows):
        vals = [r[field] for r in subset if r[field] is not None]
        return statistics.median(vals) if vals else None

    pin_latest_rate, pin_latest_n = frac(lambda r: r["pinned_is_latest"])
    moved_rate, moved_n = frac(lambda r: (r["versions_after_pinned"] or 0) > 0
                               if r["versions_after_pinned"] is not None else None)
    single_rate, single_n = frac(lambda r: r["maintainer_count"] == 1, npm_rows)
    return {
        "as_of": as_of.date().isoformat(),
        "window_days": 90,
        "packages_considered": len(packages),
        "packages_measured": len(rows),
        "fetch_errors": dict(errors),
        "by_registry": dict(collections.Counter(r["registry"] for r in rows)),
        "released_in_last_90d_frac": frac(lambda r: r["releases_90d"] > 0)[0],
        "median_versions_total": med("versions_total"),
        "median_releases_90d": med("releases_90d"),
        "median_days_since_last_release": med("days_since_last_release"),
        "pinned_is_latest_frac": pin_latest_rate,
        "pinned_is_latest_n": pin_latest_n,
        "versions_published_after_pin_frac": moved_rate,
        "versions_published_after_pin_n": moved_n,
        "npm_single_maintainer_frac": single_rate,
        "npm_single_maintainer_n": single_n,
        "note": ("pinned_is_latest: the version approved in the MCP registry is "
                 "still the current latest, so an approved launch tracking latest "
                 "would adopt the maintainer's next release unreviewed. Maintainer "
                 "hand-off history is not exposed by the public APIs; we report "
                 "npm single-maintainer concentration instead, and PyPI maintainer "
                 "count is unknown."),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0,
                        help="measure only the first N packages (smoke test)")
    parser.add_argument("--as-of", default=HARVEST_DATE)
    args = parser.parse_args()
    as_of = parse_iso(args.as_of + "T00:00:00+00:00")
    packages = local_packages()
    if args.limit:
        packages = packages[:args.limit]
    print(f"{len(packages)} local npm/PyPI packages to measure", flush=True)
    meta = fetch_all(packages)
    summary = analyze(packages, meta, as_of)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists() and not args.limit:
        raise SystemExit(f"{OUT} exists; never overwrite an earlier run")
    if not args.limit:
        OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

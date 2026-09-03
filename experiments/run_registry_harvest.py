"""
Walk the ENTIRE official MCP Registry and build a Phase 1 candidate pool.

Replaces GitHub keyword search as the primary sampling frame for the
real-server audit. The registry is authoritative where GitHub search was
inferential: every entry here is something its author explicitly
registered as an MCP server, the package identifier is exact (no more
script-name-vs-package-name guessing), and required-secret environment
variables are author-declared rather than regex-guessed from source.

Writes two files:
  data/processed/registry_all.json        every entry seen, for the record
  data/processed/registry_candidates.json  the runnable-without-credentials
                                            stdio subset, directly usable
                                            by run_scale.py

    python experiments/run_registry_harvest.py
    python experiments/run_registry_harvest.py --max-pages 500
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from measure.mcp_registry import walk_registry  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ALL_OUT = ROOT / "data" / "processed" / "registry_all.json"
CAND_OUT = ROOT / "data" / "processed" / "registry_candidates.json"
STATE_OUT = ROOT / "data" / "processed" / "registry_harvest_state.json"


def to_row(entry) -> dict:
    return {
        "name": entry.name,
        "title": entry.title,
        "description": entry.description,
        "repository_url": entry.repository_url,
        "status": entry.status,
        "has_remotes": entry.has_remotes,
        "packages": [
            {"registry_type": p.registry_type, "identifier": p.identifier,
             "version": p.version, "transport": p.transport,
             "required_secrets": p.required_secrets,
             "optional_env": p.optional_env,
             "command": p.command,
             "runnable_standalone": p.stdio_launchable and not p.needs_credentials}
            for p in entry.packages
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=10_000)
    ap.add_argument("--limit-per-page", type=int, default=100)
    ap.add_argument("--resume", action="store_true",
                    help="continue from the last saved cursor and data "
                         "instead of starting over -- a walk over 20,000+ "
                         "entries WILL hit a transient network failure")
    ap.add_argument("--restart", action="store_true",
                    help="explicitly discard any saved progress and start "
                         "from the beginning")
    args = ap.parse_args()

    all_rows: list[dict] = []
    candidates: list[dict] = []
    start_cursor = None
    if args.resume and not args.restart and STATE_OUT.exists():
        state = json.loads(STATE_OUT.read_text(encoding="utf-8"))
        start_cursor = state.get("cursor")
        if ALL_OUT.exists():
            all_rows = json.loads(ALL_OUT.read_text(encoding="utf-8"))
        if CAND_OUT.exists():
            candidates = json.loads(CAND_OUT.read_text(encoding="utf-8"))
        print(f"resuming from cursor={start_cursor!r}: "
              f"{len(all_rows)} entries, {len(candidates)} candidates "
              "already saved\n")
    else:
        print("Walking the official MCP registry from the start...\n")

    t0 = time.time()
    i = len(all_rows)
    last_cursor = start_cursor

    def checkpoint() -> None:
        ALL_OUT.parent.mkdir(parents=True, exist_ok=True)
        ALL_OUT.write_text(json.dumps(all_rows, indent=1), encoding="utf-8")
        CAND_OUT.write_text(json.dumps(candidates, indent=1), encoding="utf-8")
        STATE_OUT.write_text(json.dumps({"cursor": last_cursor}), encoding="utf-8")

    try:
        for entry, cursor in walk_registry(limit_per_page=args.limit_per_page,
                                           max_pages=args.max_pages,
                                           start_cursor=start_cursor):
            i += 1
            last_cursor = cursor
            row = to_row(entry)
            all_rows.append(row)
            for p in row["packages"]:
                if p["runnable_standalone"]:
                    # A registry entry can list more than one installable
                    # package (an npm build and a PyPI build of the same
                    # server) -- 48 out of ~6,200 candidates did, in
                    # practice. Using entry.name alone as server_id would
                    # give both the same scratch directory and the same
                    # dedup key downstream, so the second variant is
                    # silently skipped forever and, if run concurrently,
                    # the two could race on the same directory.
                    sid = (entry.name if len(row["packages"]) == 1
                          else f"{entry.name}#{p['registry_type']}")
                    candidates.append({
                        "server_id": sid,
                        "title": entry.title,
                        "description": entry.description,
                        "repository_url": entry.repository_url,
                        "registry_type": p["registry_type"],
                        "identifier": p["identifier"],
                        "command": p["command"],
                        "optional_env": p["optional_env"],
                    })
            if i % 500 == 0:
                elapsed = time.time() - t0
                print(f"  {i} entries, {len(candidates)} candidates so far "
                      f"({elapsed:.0f}s elapsed)")
                checkpoint()
    except KeyboardInterrupt:
        pass
    finally:
        checkpoint()

    print(f"\n{'='*70}")
    print(f"REGISTRY HARVEST COMPLETE  --  {time.time()-t0:.0f}s")
    print("=" * 70)
    print(f"  total entries:              {len(all_rows)}")
    print(f"  runnable-without-cred pkgs: {len(candidates)}")

    by_type = Counter(c["registry_type"] for c in candidates)
    print(f"\n  by registry type: {dict(by_type)}")

    with_remotes = sum(1 for r in all_rows if r["has_remotes"])
    with_pkgs = sum(1 for r in all_rows if r["packages"])
    print(f"  entries with remotes (hosted, out of scope): {with_remotes}")
    print(f"  entries with any package:                    {with_pkgs}")

    print(f"\nwrote {ALL_OUT.relative_to(ROOT)}")
    print(f"wrote {CAND_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

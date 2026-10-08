"""Named, well-known MCP servers under network-effect admission (RQ-N headline).

The matched evaluation (network_matched_eval.py) draws servers by an unbiased
registry shuffle, so the servers are obscure. This driver runs the same
machinery on a curated set of recognizable servers, as the headline
demonstration: the official GitHub MCP server, and others added as their test
modes allow. Each server is pinned, run on honest test calls with unseen
arguments behind the EffectSeal-N gate, and its captured honest requests are
transformed into the eight attack families (Table N-A1..N-A8), scored against
the request template and a destination-only policy.

Attacks are transformations of recorded honest requests; no server is modified.

    python experiments/network_named_demo.py [--only github]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

import network_matched_eval as M  # noqa: E402
import network_select_servers as SEL  # noqa: E402

STAMP = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
OUT = ROOT / "artifact" / "results" / f"network_named_{STAMP}"

# Each entry is a prebuilt image (no install step) plus the honest exemplar.
NAMED = {
    "github": {
        "name": "github/github-mcp-server",
        "image": "ghcr.io/github/github-mcp-server:latest",
        "env_names": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
        "extra_env": {"GITHUB_TOOLSETS": "all"},
        "tool": "add_issue_comment",
        "args": {"owner": "octo-org", "repo": "demo-project", "issue_number": 42,
                 "body": "Thanks for the report, the fix is on the way."},
    },
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="run just this named server")
    parser.add_argument("--calls", type=int, default=12)
    a = parser.parse_args()
    OUT.mkdir(parents=True)
    rng = random.Random(20261008)
    work = Path(tempfile.mkdtemp(prefix="es-named-"))
    results = []
    todo = {a.only: NAMED[a.only]} if a.only else NAMED
    with SEL.GenericBroker(work) as broker:
        for key, spec in todo.items():
            print(f"evaluating {spec['name']}", flush=True)
            try:
                r = M.evaluate(broker, spec, a.calls, rng)
            except Exception as exc:  # noqa: BLE001
                r = {"name": spec["name"], "qualified": False, "reason": f"{type(exc).__name__}: {exc}"}
            r["key"] = key
            results.append(r)
            print("  ", {k: r.get(k) for k in ("qualified", "slack_bits", "honest", "reason")}, flush=True)
            (OUT / "results.jsonl").open("a", encoding="utf-8").write(json.dumps(r) + "\n")
    (OUT / "summary.json").write_text(json.dumps(M.summarize(results), indent=2), encoding="utf-8")
    (OUT / "meta.json").write_text(json.dumps(
        {"servers": {k: {kk: v[kk] for kk in ("name", "image", "tool")} for k, v in todo.items()},
         "seed": 20261008, "calls": a.calls,
         "finished": dt.datetime.now(dt.timezone.utc).isoformat()}, indent=2), encoding="utf-8")
    print(json.dumps(M.summarize(results), indent=2))


if __name__ == "__main__":
    main()

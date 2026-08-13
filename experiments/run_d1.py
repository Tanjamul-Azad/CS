"""
D1 full harvest: discover MCP servers at scale, extract, classify.

Produces the paper's headline measurement. Static extraction from public
source only -- no live server is ever contacted.

Checkpoints after every repo, so a long run survives interruption and
resumes where it stopped. Re-running with the same --out continues.

    python experiments/run_d1.py --target 500
    python experiments/run_d1.py --target 500 --resume
    python experiments/run_d1.py --report-only
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from measure.discover import discover  # noqa: E402
from measure.extract import ExtractedTool  # noqa: E402
from measure.harvest import (  # noqa: E402
    Repo,
    dedup,
    get_token,
    harvest_repo,
    load_corpus,
    write_corpus,
)
from measure.report import report  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "d1_corpus.jsonl"
STATE = ROOT / "data" / "processed" / "d1_state.json"


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"done": [], "repos": []}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=500)
    ap.add_argument("--max-files", type=int, default=40)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    if args.report_only:
        report(load_corpus(args.out))
        return

    token = get_token()
    if not token:
        print("WARNING: no GITHUB_TOKEN -- 60 req/hr. Add it to .env.")

    state = load_state()
    tools: list[ExtractedTool] = []
    if args.resume and args.out.exists():
        tools = load_corpus(args.out)
        print(f"resuming: {len(tools)} tools, {len(state['done'])} repos done")

    if not state.get("repos"):
        print("discovering MCP server repositories...")
        repos = discover(token, target=args.target)
        state["repos"] = [[r.owner, r.name, r.ref, r.kind] for r in repos]
        save_state(state)
    repos = [Repo(*r) for r in state["repos"]]

    done = set(state["done"])
    todo = [r for r in repos if r.server_id not in done]
    print(f"\nharvesting {len(todo)} repos "
          f"({len(done)} already done)\n")

    t0 = time.time()
    for i, repo in enumerate(todo, 1):
        try:
            got = harvest_repo(repo, token, max_files=args.max_files, quiet=True)
        except Exception as e:  # noqa: BLE001
            print(f"  [{i}/{len(todo)}] {repo.server_id}: FAILED ({type(e).__name__})")
            got = []
        tools.extend(got)
        done.add(repo.server_id)
        state["done"] = sorted(done)

        if got:
            print(f"  [{i}/{len(todo)}] {repo.server_id}: {len(got)} tools")
        if i % 10 == 0 or i == len(todo):
            write_corpus(dedup(tools), args.out)
            save_state(state)
            rate = i / max(time.time() - t0, 1)
            eta = (len(todo) - i) / max(rate, 1e-6) / 60
            print(f"       ... checkpoint: {len(dedup(tools))} tools, "
                  f"ETA {eta:.0f} min")

    tools = dedup(tools)
    write_corpus(tools, args.out)
    save_state(state)
    print(f"\nharvest complete in {(time.time()-t0)/60:.1f} min")
    report(tools)


if __name__ == "__main__":
    main()

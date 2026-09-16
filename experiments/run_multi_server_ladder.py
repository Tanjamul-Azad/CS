"""
M3 sweep, run 2: five real, independent, unmodified third-party MCP
servers, not one. Extends `run_real_server_ladder.py` (which ran only
`real_server_probe.py`, docs/29) to also run the four servers added
after that write-up: an official reference implementation of the same
EXACT-class tool (server-filesystem), a keyed/structured store
(server-memory), an underspecified SQL tool (mcp-sqlite-server), and a
git-native tool with no content argument at all (mcp-server-git).

    python experiments/run_multi_server_ladder.py

Each probe runs INSIDE the project container exactly as
`run_real_server_ladder.py` already does; see each probe script's own
docstring for that server's schema, threat model, and ladder semantics.
This is still not the >=10-server sweep M3 specifies -- five servers
across three workflow classes plus one git-native shape (docs/27), not
ten within one. Report it as exactly that.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "multi_server_ladder.json"
IMAGE = "mcpaudit-runner:latest"
DOCKER_ENV = {**os.environ, "MSYS_NO_PATHCONV": "1", "MSYS2_ARG_CONV_EXCL": "*"}

PROBES = {
    "domdomegg/filesystem-mcp": ("/app/boundary/real_server_probe.py", 180),
    "@modelcontextprotocol/server-filesystem": ("/app/boundary/probe_server_filesystem.py", 180),
    "@modelcontextprotocol/server-memory": ("/app/boundary/probe_server_memory.py", 420),
    "mcp-sqlite-server": ("/app/boundary/probe_sqlite.py", 180),
    "mcp-server-git": ("/app/boundary/probe_git.py", 180),
}


def run_one(server: str, script: str, timeout: int) -> list[dict]:
    cmd = ["docker", "run", "--rm",
           "--memory=512m", "--cpus=1", "--pids-limit=256",
           "--security-opt=no-new-privileges",
           "--entrypoint", "python3", IMAGE, script]
    print(f"  running {server} ({script}) ...", file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          env=DOCKER_ENV)
    if proc.returncode != 0:
        print(f"    FAILED: {proc.stderr[-2000:]}", file=sys.stderr)
        return [{"scenario": "<probe crashed>", "rung": "-", "server": server,
                "server_error": proc.stderr[-2000:]}]
    rows = json.loads(proc.stdout)
    for r in rows:
        r["server"] = server
    return rows


def report(rows: list[dict]) -> None:
    print("=" * 100)
    print("M3 -- MULTI-SERVER SWEEP (4 real, unmodified, third-party MCP servers)")
    print("=" * 100)
    by_server: dict[str, list[dict]] = {}
    for r in rows:
        by_server.setdefault(r["server"], []).append(r)

    for server, srows in by_server.items():
        print(f"\n{server}")
        print("-" * 100)
        for r in srows:
            v = r.get("verdicts", {})
            landed = r.get("attack_landed_per_proxy")
            refused = r.get("server_refused_call")
            print(f"  {r['scenario']:<24}{r['rung']:<4}"
                  f" landed={'-' if landed is None else str(landed):<6}"
                  f" refused={'-' if refused is None else str(refused):<6}"
                  f" dest={v.get('destination','-'):<6} content={v.get('content','-'):<6}"
                  f" decision={r.get('decision','-'):<8}"
                  f" oracle={'compromised' if r.get('unauthorized_effect') else 'clean'}")
            if r.get("server_error"):
                print(f"      (error: {str(r['server_error'])[:150]})")

    print("\n" + "=" * 100)
    print("  Five real, unmodified, third-party servers across three workflow classes")
    print("  (docs/27): EXACT (x2 independent implementations), CONSTRAINED/keyed,")
    print("  CONSTRAINED/git-native, UNDERSPECIFIED/SQL. This is still not the")
    print("  >=10-server sweep M3 specifies.")


def main() -> None:
    all_rows: list[dict] = []
    for server, (script, timeout) in PROBES.items():
        all_rows.extend(run_one(server, script, timeout))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(all_rows, indent=1), encoding="utf-8")
    report(all_rows)
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

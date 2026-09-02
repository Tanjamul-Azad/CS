"""
E3: audit a REAL MCP server, end to end.

Everything before this used servers we wrote. This drives the official
filesystem reference server over stdio -- unmodified, real declarations,
real effects on a real disk -- and asks two questions the simulator
cannot answer:

  1. Does relation derivation work on declarations we did not write?
     Does the auditor's read-back actually find the write?
  2. Does it stay quiet on an honest server? (false positives)

Then it interposes a TAMPERING PROXY between the auditor and the real
server. The proxy is the L1 adversary: it diverts the write to a
different path and reports the path that was requested. The server behind
it is genuine and behaves correctly -- only the proxy lies. That is the
honest way to test detection against declarations we did not author.

Everything happens inside a sandbox directory passed on the command line.

    python experiments/run_live.py --sandbox /path/to/scratch
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcpaudit import Auditor, Policy  # noqa: E402
from mcpaudit.cli import _load_stdio  # noqa: E402
from mcpmut.live import LiveSession  # noqa: E402
from mcpmut.proxy import TamperingProxy, attack_landed  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

TARGET = "report.txt"
DIVERTED = "exfil.txt"
CONTENT = "quarterly figures"


def make_proxy(session: LiveSession, tools: list[dict], level: int):
    """The generic, declaration-driven proxy in front of a real server.

    Note this is the SAME TamperingProxy used against the benchmark -- it
    is not specialised to the filesystem server. The write/read partition
    is derived from the live declarations, so the adversary is built from
    exactly what the defense sees, and detection here is not
    self-evaluation.
    """
    from measure.classify import is_read, is_write
    from measure.extract import ExtractedTool

    def klass(t):
        return ExtractedTool(name=t["name"], description=t.get("description", ""),
                             annotations=t.get("annotations", {}))
    writes = {t["name"] for t in tools if is_write(klass(t))}
    reads = {t["name"] for t in tools if is_read(klass(t))}
    return TamperingProxy(inner=lambda n, a: session.call(n, a),
                          write_tools=writes, read_tools=reads, level=level)


def audit_write(server, tools: list[dict], label: str) -> dict:
    auditor = Auditor.from_mcp_tools(
        tools, server_id="live",
        policy=Policy(**{**Policy.default().__dict__, "audit_budget": 50.0}))

    args = {"path": TARGET, "content": CONTENT}
    probes = {"n": 0}

    def probe(name, a):
        probes["n"] += 1
        return server.call(name, a)

    t0 = time.time()
    auditor.before_call("write_file", args, call_fn=probe)
    result = server.call("write_file", args)
    alerts = auditor.after_call("write_file", args, result, call_fn=probe)
    elapsed = time.time() - t0

    violations = [a for a in alerts if a.severity == "violation"]
    print(f"\n  {label}")
    print(f"    probes={probes['n']}  wall={elapsed:.2f}s  "
          f"alerts={len(alerts)}  violations={len(violations)}")
    for a in alerts:
        print(f"      {a}")
    return {"label": label, "probes": probes["n"], "seconds": elapsed,
            "violations": len(violations),
            "detail": [str(a) for a in violations]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sandbox", required=True,
                    help="directory the server is allowed to touch")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "experiments" / "results" / "live.json")
    args = ap.parse_args()

    sandbox = Path(args.sandbox)
    sandbox.mkdir(parents=True, exist_ok=True)
    for f in (TARGET, DIVERTED):
        (sandbox / f).unlink(missing_ok=True)

    cmd = f"npx -y @modelcontextprotocol/server-filesystem {sandbox}"

    print("=" * 74)
    print("E3  LIVE MCP SERVER  --  official filesystem reference server")
    print("=" * 74)
    print(f"  sandbox: {sandbox}")

    tools = _load_stdio(cmd)
    auditor = Auditor.from_mcp_tools(tools, server_id="live")
    cov = auditor.coverage()
    print(f"\n  declarations: {cov.summary()}")
    print(f"  relations derived: {len(auditor.relations)}")
    print(f"  readers for write_file: {auditor._readers.get('write_file', [])}")

    rows = []
    with LiveSession(cmd) as s:
        rows.append(audit_write(s, tools, "HONEST real server"))
        honest_files = sorted(p.name for p in sandbox.iterdir())

    for f in (TARGET, DIVERTED):
        (sandbox / f).unlink(missing_ok=True)

    with LiveSession(cmd) as s:
        proxy = make_proxy(s, tools, level=1)
        rows.append(audit_write(proxy, tools,
                                "TAMPERED (generic L1 proxy, declaration-driven)"))
        rows[-1]["attack_landed"] = attack_landed(proxy.plans)
        rows[-1]["diverted_to"] = (proxy.plans[-1].diverted_value
                                   if proxy.plans else None)
        tampered_files = sorted(p.name for p in sandbox.iterdir())

    print("\n" + "=" * 74)
    print("GROUND TRUTH ON DISK")
    print("=" * 74)
    print(f"  after honest run   : {honest_files}")
    print(f"  after tampered run : {tampered_files}")
    print(f"  proxy diverted the write to: {rows[1].get('diverted_to')}")
    print(f"  attack actually landed on disk: {rows[1].get('attack_landed')}")

    print("\n" + "=" * 74)
    fp = rows[0]["violations"]
    det = rows[1]["violations"]
    print(f"  false positives on the honest server : {fp}")
    print(f"  violations against the tampering proxy: {det}")
    if fp == 0 and det > 0:
        print("\n  Detection works against declarations we did not author,")
        print("  with no false alarm on the genuine server.")
    elif fp:
        print("\n  FALSE ALARM on an honest server -- investigate before claiming.")
    else:
        print("\n  MISSED the diversion. Inspect the derived relations above.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        {"tools": len(tools), "coverage": cov.by_class, "runs": rows,
         "honest_files": honest_files, "tampered_files": tampered_files},
        indent=1), encoding="utf-8")
    print(f"\n  wrote {args.out.relative_to(ROOT)}\n")


if __name__ == "__main__":
    main()

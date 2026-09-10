"""
M-feas -- can a per-call authorization actually be expressed as filesystem,
network and process restrictions?

The research program (docs/25) proposes moving enforcement from a trusted
per-effect executor to a shared mediation boundary, on the reasoning that
a boundary needs no tool-specific knowledge. That reasoning is a
HYPOTHESIS and this script is the first cheap test of it.

The objection it exists to answer: a boundary observes syscalls and
packets, not meaning. It can see a connection to an SMTP host; it cannot
see whether the recipient is the one the user approved. It can see a write
to an allowed path; whether the bytes are the approved bytes is a
different enforcement problem, and under TLS the payload is not visible at
all. So the real question is not "does a boundary generalise" but:

    what fraction of real write-tool arguments can a shared
    filesystem/network/process policy constrain, and what fraction
    needs an application-level adapter that understands the operation?

This measures an UPPER BOUND, and the bound is loose in one direction on
purpose. It reads declarations only -- argument names and types from
tools/list -- so it asks what a boundary could constrain IN PRINCIPLE. A
tool whose argument is called `path` is counted as filesystem-expressible
even though the enforcement still has to survive symlinks, renames,
partial writes and TOCTOU. Real coverage cannot be higher than this and
will very likely be lower.

    python experiments/run_boundary_feasibility.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from measure.classify import WRITE_VERBS  # noqa: E402

SOURCE = ROOT / "data" / "processed" / "resource_sweep.json"
OUT = ROOT / "data" / "processed" / "boundary_feasibility.json"

# An argument a filesystem policy can name. A path is the one thing
# Landlock-style enforcement constrains directly and well.
FS_TOKENS = {"path", "file", "filename", "filepath", "dir", "directory",
             "folder", "dest", "destination", "src", "source", "location",
             "output", "input", "target_path", "workspace", "root"}

# An argument a network policy can name -- but only at host granularity.
# Allowing a host allows every recipient reachable through it, which is
# exactly the gap this measurement exists to size.
NET_TOKENS = {"url", "uri", "endpoint", "host", "hostname", "domain",
              "server", "address", "webhook", "api_url", "base_url", "port"}

PROC_TOKENS = {"command", "cmd", "args", "argv", "executable", "binary",
               "script", "shell", "program"}

# Arguments that decide the effect's identity but that NO boundary policy
# can adjudicate, because the meaning is inside the payload or inside a
# remote service's own namespace. These are the adapter cases.
OPAQUE_TOKENS = {
    # payload -- content correctness is not a boundary property
    "content", "body", "text", "data", "payload", "message", "value",
    # remote namespace -- the boundary sees a host, not which record
    "to", "recipient", "cc", "bcc", "email", "channel", "chat_id",
    "repo", "repository", "branch", "issue", "pull_request", "table",
    "collection", "database", "bucket", "key", "id", "user", "account",
    # quantities -- an allowance, not a boundary restriction
    "amount", "quantity", "count", "limit", "price",
}


def token_class(field: str) -> str:
    f = field.strip().lower().replace("-", "_")
    parts = set(f.split("_")) | {f}
    if parts & FS_TOKENS:
        return "filesystem"
    if parts & NET_TOKENS:
        return "network"
    if parts & PROC_TOKENS:
        return "process"
    if parts & OPAQUE_TOKENS:
        return "opaque"
    if f.endswith("_id") or f.endswith("_key"):
        return "opaque"
    return "unclassified"


def verb(name: str) -> str:
    return name.replace("-", "_").split("_")[0].lower()


def main() -> None:
    if not SOURCE.exists():
        print(f"missing {SOURCE}; run experiments/run_resource_sweep.py first")
        return
    rows = [r for r in json.loads(SOURCE.read_text(encoding="utf-8"))
            if r.get("status") == "ok"]

    tools, per_tool = 0, []
    field_classes: Counter = Counter()
    for r in rows:
        for t in r.get("tools", []):
            if t.get("readOnlyHint") is True or verb(t["name"]) not in WRITE_VERBS:
                continue
            fields = list(t.get("input_fields") or [])
            tools += 1
            classes = [token_class(f) for f in fields]
            field_classes.update(classes)
            boundary = {c for c in classes if c in
                        ("filesystem", "network", "process")}
            opaque = [f for f, c in zip(fields, classes) if c == "opaque"]
            per_tool.append({
                "server_id": r["server_id"], "tool": t["name"],
                "fields": fields, "classes": classes,
                "boundary_kinds": sorted(boundary),
                "opaque_fields": opaque,
                # The decisive category. A tool is fully boundary-
                # expressible only if NOTHING about its effect identity
                # lives somewhere a boundary cannot adjudicate.
                "fully_boundary": bool(fields) and not opaque and bool(boundary),
                "needs_adapter": bool(opaque),
                "no_args": not fields,
            })

    n = len(per_tool) or 1
    full = sum(1 for t in per_tool if t["fully_boundary"])
    adapter = sum(1 for t in per_tool if t["needs_adapter"])
    noargs = sum(1 for t in per_tool if t["no_args"])
    partial = sum(1 for t in per_tool
                  if t["boundary_kinds"] and t["needs_adapter"])

    print("=" * 70)
    print("BOUNDARY FEASIBILITY -- upper bound from declarations alone")
    print("=" * 70)
    print(f"\nwrite tools examined: {n}   (servers: {len(rows)})\n")
    print(f"  fully boundary-expressible      {full:>5}  {100*full/n:>5.1f}%")
    print(f"    -- every argument is a path, host or command\n")
    print(f"  needs an application adapter    {adapter:>5}  {100*adapter/n:>5.1f}%")
    print(f"    -- at least one argument decides the effect somewhere")
    print(f"       a boundary cannot adjudicate (payload, recipient,")
    print(f"       remote record id, quantity)\n")
    print(f"    of those, PARTLY constrainable {partial:>5}  {100*partial/n:>5.1f}%")
    print(f"    -- a boundary narrows it, but cannot fully authorize it\n")
    print(f"  no declared arguments           {noargs:>5}  {100*noargs/n:>5.1f}%")

    print("\nargument kinds across all write tools")
    tot = sum(field_classes.values()) or 1
    for k, v in field_classes.most_common():
        print(f"  {k:<16} {v:>6}  {100*v/tot:>5.1f}%")

    print("\nmost common arguments a boundary cannot adjudicate")
    opaque_names: Counter = Counter()
    for t in per_tool:
        opaque_names.update(f.lower() for f in t["opaque_fields"])
    for k, v in opaque_names.most_common(12):
        print(f"  {k:<20} {v:>5}")

    OUT.write_text(json.dumps(per_tool, indent=1), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    print("\nUPPER BOUND. Declarations only: a field named `path` counts as")
    print("filesystem-expressible without the enforcement having to survive")
    print("symlinks, renames, partial writes or TOCTOU. Real coverage cannot")
    print("exceed this and will very likely be lower.")


if __name__ == "__main__":
    main()

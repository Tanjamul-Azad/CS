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

This is a HEURISTIC ESTIMATE, not a bound in either direction, and an
earlier version of this docstring wrongly called it an upper bound. It
reads argument NAMES from declarations, so it errs both ways: an
unrecognised name can hide a genuinely enforceable tool, and a recognised
one can be wrong about what the argument means -- `file_id` reads as a
path and is a remote handle. Required-vs-optional fields, real semantics,
and whether a contract needs to constrain a given field at all are not
considered, and enforcement would still have to survive symlinks,
renames, partial writes and TOCTOU.

Every category below therefore needs a human-validated sample before any
of it is quoted. That audit is separate from the A0-A3 labelling, which
validates a different classifier.

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


# Names that read as boundary vocabulary but plausibly denote something a
# boundary cannot adjudicate. `file_id` is a remote object handle, not a
# path; `email_address` is a recipient, not a host to connect to. Guessing
# either way biases the headline, so they get their own category and are
# excluded from the candidate count rather than silently resolved.
AMBIGUOUS_PATTERNS = (
    ("file", "id"), ("file", "key"), ("document", "id"), ("doc", "id"),
    ("email", "address"), ("email", "id"), ("mail", "address"),
    ("source", "id"), ("target", "id"), ("dest", "id"),
)


def token_class(field: str) -> str:
    f = field.strip().lower().replace("-", "_")
    parts = set(f.split("_")) | {f}
    for a, b in AMBIGUOUS_PATTERNS:
        if a in parts and b in parts:
            return "ambiguous"
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
        print(f"MISSING INPUT: {SOURCE}\n"
              f"  Raw traces are gitignored (large, regenerable). Produce it "
              f"with:\n    python experiments/run_resource_sweep.py\n"
              f"  (~1 hour, needs Docker). See results/README.md.")
        # Exit non-zero: a missing input must not look like a clean run.
        sys.exit(2)
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
            unknown = [f for f, c in zip(fields, classes)
                       if c == "unclassified"]
            ambiguous = [f for f, c in zip(fields, classes) if c == "ambiguous"]
            per_tool.append({
                "server_id": r["server_id"], "tool": t["name"],
                "fields": fields, "classes": classes,
                "boundary_kinds": sorted(boundary),
                "opaque_fields": opaque,
                "unknown_fields": unknown,
                "ambiguous_fields": ambiguous,
                # A CANDIDATE, not a verdict. Every argument must fall in a
                # recognised boundary category -- an earlier version asked
                # only that no argument be recognisably opaque, which let
                # a tool with arguments (path, mystery_option) count as
                # "fully boundary-expressible" on the strength of one
                # recognised field and one the vocabulary simply did not
                # know. That is a definition error, not a conservative
                # estimate, and it inflated the headline number.
                "boundary_candidate": bool(classes) and all(
                    c in ("filesystem", "network", "process") for c in classes),
                "has_opaque": bool(opaque),
                "has_unknown": bool(unknown),
                "has_ambiguous": bool(ambiguous),
                "no_args": not fields,
            })

    n = len(per_tool) or 1
    cand = sum(1 for t in per_tool if t["boundary_candidate"])
    opaque_t = sum(1 for t in per_tool if t["has_opaque"])
    unknown_t = sum(1 for t in per_tool
                    if t["has_unknown"] and not t["has_opaque"])
    ambig_t = sum(1 for t in per_tool if t["has_ambiguous"])
    noargs = sum(1 for t in per_tool if t["no_args"])
    partial = sum(1 for t in per_tool
                  if t["boundary_kinds"] and t["has_opaque"])

    print("=" * 70)
    print("BOUNDARY FEASIBILITY -- heuristic estimate from declarations")
    print("=" * 70)
    print(f"\nwrite tools examined: {n}   (servers: {len(rows)})\n")
    print(f"  boundary CANDIDATE              {cand:>5}  {100*cand/n:>5.1f}%")
    print(f"    -- every argument falls in a recognised boundary category.")
    print(f"       A candidate, not a verdict: enforceability still has to")
    print(f"       survive symlinks, renames, partial writes and TOCTOU.\n")
    print(f"  has a recognisably opaque arg   {opaque_t:>5}  {100*opaque_t/n:>5.1f}%")
    print(f"    -- payload, recipient, remote record id or quantity.")
    print(f"       Suggests an adapter; does not prove one is unavoidable,")
    print(f"       which needs the field's real semantics and whether the")
    print(f"       contract must constrain it at all.\n")
    print(f"    of those, boundary narrows it  {partial:>5}  {100*partial/n:>5.1f}%\n")
    print(f"  unclassified arg, none opaque    {unknown_t:>5}  {100*unknown_t/n:>5.1f}%")
    print(f"    -- has at least one argument outside the vocabulary and no")
    print(f"       recognisably opaque one. NOT 'entirely unclassified': such")
    print(f"       a tool may also carry recognised boundary fields.\n")
    print(f"  has an ambiguous arg            {ambig_t:>5}  {100*ambig_t/n:>5.1f}%")
    print(f"    -- file_id, email_address: reads as boundary vocabulary but")
    print(f"       may denote a remote handle or a recipient\n")
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
    print("\nHEURISTIC ESTIMATE -- not a validated enforceability rate and")
    print("not a mathematical bound. It reads argument NAMES from")
    print("declarations, so it errs in BOTH directions: an unrecognised name")
    print("can hide a genuinely enforceable tool, and a recognised one can be")
    print("wrong about what the argument means. Required-vs-optional fields,")
    print("real semantics, and whether a contract needs to constrain a given")
    print("field at all are not considered. Treat these as estimates until a")
    print("human-validated sample per category exists -- a separate audit")
    print("from the A0-A3 labelling, which does not validate this classifier.")


if __name__ == "__main__":
    main()

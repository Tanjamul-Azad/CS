"""
Runs as the untrusted `sandbox` user, launched by `probe_m2_corner_cases.py`.

Not an adversary -- these are all HONEST behaviours. The question is
whether the M2-proper mediator (`probe_m2.py`) still correctly commits an
honest effect when that effect is shaped in ways a single "write one file"
scenario never exercises: docs/25 section 5 names "one invocation != one
syscall" by name ("an honest file save may be several writes plus a
rename") as a failure mode to attack directly rather than assume away.
This is that attack, run against real code rather than left as an
unverified claim.

Protocol: same one-JSON-object-per-line shape as the other servers here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def handle(msg: dict) -> dict:
    scenario = msg["scenario"]
    root = Path(msg["root"])
    content = msg["args"]["content"]
    target = root / msg["args"]["path"]

    if scenario == "temp_write_rename":
        # The single most common real save pattern: write to a temp name,
        # fsync/close, then atomically rename into place. Two filesystem
        # operations, one logical save.
        tmp = root / (msg["args"]["path"] + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.rename(target)
        return {"proposal": {"operation": msg["op"], "arguments": dict(msg["args"])},
                "protocol_error": False, "attempted": ["write temp, then rename into place"]}

    if scenario == "empty_content":
        target.write_text("", encoding="utf-8")
        return {"proposal": {"operation": msg["op"], "arguments": {**msg["args"], "content": ""}},
                "protocol_error": False, "attempted": ["wrote zero-byte file"]}

    if scenario == "large_content":
        target.write_text(content, encoding="utf-8")
        return {"proposal": {"operation": msg["op"], "arguments": dict(msg["args"])},
                "protocol_error": False, "attempted": [f"wrote {len(content)} bytes"]}

    if scenario == "write_then_overwrite":
        # Two honest writes to the SAME path in one invocation -- the
        # final state is what should be checked, not an intermediate one.
        target.write_text("draft, not final", encoding="utf-8")
        target.write_text(content, encoding="utf-8")
        return {"proposal": {"operation": msg["op"], "arguments": dict(msg["args"])},
                "protocol_error": False, "attempted": ["wrote a draft, then overwrote with final content"]}

    return {"proposal": None, "protocol_error": True,
            "attempted": [f"unknown corner-case scenario: {scenario}"]}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            out = handle(json.loads(line))
        except Exception as e:  # noqa: BLE001
            out = {"proposal": None, "protocol_error": True,
                   "attempted": [f"server crashed: {type(e).__name__}: {e}"]}
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

"""
Runs INSIDE the container: the seventh real-server datapoint for M3
(docs/29) -- the first with content assembled from TWO separate
arguments, not one.

SERVER: `notes-mcp` (PyPI, `uvx notes-mcp <notes-dir>` -- the second
uv-launched server in this sweep after `mcp-server-git`, `29` §5).
Schema verified live, not assumed: `write(path: string, yaml_frontmatter:
string, markdown_content: string)`, all required, `additionalProperties:
false`. Verified live, not assumed, what the server actually does with
two content-carrying arguments: it writes ONE file whose bytes are
`f"{yaml_frontmatter}\\n{markdown_content}"` -- confirmed by inspecting
the real written file, not the source code alone. `yaml_frontmatter`
must itself match `---\\n...\\n---` or the call is refused (also
confirmed live, not assumed from the tool's description).

WHY THIS MATTERS FOR THE LADDER, not just as a new server for its own
sake: every prior server's "content" rung checked ONE field. Here the
approved effect is only fully specified by TWO independent fields, and
an attacker could tamper EITHER while leaving the other untouched. This
tests whether a content check built the natural way -- comparing the
WHOLE resulting file against the exact expected bytes -- correctly
catches tampering in either half, or only the half it happens to have
been written to check.

CONTRACT: `path` matches the `path`/`repo` vocabulary `TamperingProxy`
already recognizes, so destination diversion is automatic, same as every
other probe in this sweep. Two independent content attacks are
hand-tested: `yaml_frontmatter` tampered alone, `markdown_content`
tampered alone -- neither via TamperingProxy, since the field to divert
here is chosen deliberately per scenario, not automatically.

    L1  destination only    only the approved path received a write
    L2  + structure          the file is non-empty
    L3  + content            file bytes exactly equal
                              f"{approved_yaml}\\n{approved_markdown}"
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "/app/src")

from mcpmut.live import LiveSession  # noqa: E402
from mcpmut.proxy import TamperingProxy  # noqa: E402

APPROVED_YAML = "---\ntitle: Q3 Report\n---"
APPROVED_MARKDOWN = "quarterly numbers"
APPROVED_CONTENT = f"{APPROVED_YAML}\n{APPROVED_MARKDOWN}"

# NOT /tmp/exfil.dat here. `path` is passed as a RELATIVE filename
# ("report.md", no "/"), so TamperingProxy._divert_value falls through to
# its generic string fallback ("attacker-controlled") rather than the
# absolute-path branch every other probe in this sweep observes --
# verified live before writing this probe, not assumed from the other
# servers' behavior. Since this server resolves paths relative to its own
# configured notes directory, the diverted write lands INSIDE the same
# staging directory as a sibling file, not escaping to /tmp at all -- a
# real, different containment outcome from domdomegg/filesystem-mcp's
# absolute-path diversion (docs/29 section 1), caused entirely by this
# tool's own schema using relative rather than absolute paths.
ESCAPE_NAME = "attacker-controlled"

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"


def read_file(path: str) -> str | None:
    p = Path(path)
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None


def snapshot(target_abs: str, stage: Path) -> dict:
    return {"target": read_file(target_abs), "escape": read_file(str(stage / ESCAPE_NAME))}


def check_properties(rung: str, before: dict, after: dict) -> dict:
    v: dict[str, str] = {}
    escape_changed = before["escape"] != after["escape"]
    v["destination"] = FAIL if escape_changed else PASS
    v["frame_intact"] = v["destination"]

    if rung == "L1":
        v["structure"] = UNKNOWN
        v["content"] = UNKNOWN
        return v

    v["structure"] = PASS if after["target"] else FAIL
    if rung == "L2":
        v["content"] = UNKNOWN
        return v

    v["content"] = PASS if after["target"] == APPROVED_CONTENT else FAIL
    return v


def decide(verdicts: dict) -> str:
    return "discard" if FAIL in verdicts.values() else "commit"


def oracle(before: dict, after: dict) -> dict:
    unauthorized = []
    if before["escape"] != after["escape"]:
        unauthorized.append("escape path changed without approval")
    if after["target"] not in (None, APPROVED_CONTENT) and before["target"] != after["target"]:
        unauthorized.append("approved file holds unapproved content")
    authorized = after["target"] == APPROVED_CONTENT and not unauthorized
    return {"authorized_effect": bool(authorized),
            "unauthorized_effect": bool(unauthorized),
            "oracle_findings": unauthorized,
            "no_change": after == before}


def command_for(stage: Path) -> str:
    return f"uvx notes-mcp {stage}"


def run_honest(stage: Path, target_abs: str) -> dict:
    with LiveSession(command_for(stage), cwd=str(stage)) as s:
        result = s.call("write", {"path": "report.md", "yaml_frontmatter": APPROVED_YAML,
                                  "markdown_content": APPROVED_MARKDOWN})
        errored = s.last_was_error
    return {"result": result, "attack_landed": None, "diverted_field": None, "server_refused": errored}


def run_path_diversion(stage: Path, target_abs: str) -> dict:
    with LiveSession(command_for(stage), cwd=str(stage)) as s:
        proxy = TamperingProxy(inner=s.call, write_tools={"write"}, read_tools=set(), level=1)
        result = proxy.call("write", {"path": "report.md", "yaml_frontmatter": APPROVED_YAML,
                                      "markdown_content": APPROVED_MARKDOWN})
        plan = proxy.plans[-1] if proxy.plans else None
        errored = s.last_was_error
    return {"result": result, "attack_landed": bool(plan and plan.active),
            "diverted_field": plan.target_field if plan else None, "server_refused": errored}


def run_yaml_substitution(stage: Path, target_abs: str) -> dict:
    """Content attack #1: tamper the frontmatter half only."""
    tampered_yaml = "---\ntitle: ATTACKER-CONTROLLED\n---"
    with LiveSession(command_for(stage), cwd=str(stage)) as s:
        result = s.call("write", {"path": "report.md", "yaml_frontmatter": tampered_yaml,
                                  "markdown_content": APPROVED_MARKDOWN})
        errored = s.last_was_error
    return {"result": result, "attack_landed": True, "diverted_field": "yaml_frontmatter",
            "server_refused": errored}


def run_markdown_substitution(stage: Path, target_abs: str) -> dict:
    """Content attack #2: tamper the body half only."""
    with LiveSession(command_for(stage), cwd=str(stage)) as s:
        result = s.call("write", {"path": "report.md", "yaml_frontmatter": APPROVED_YAML,
                                  "markdown_content": "ATTACKER-CONTROLLED PAYLOAD"})
        errored = s.last_was_error
    return {"result": result, "attack_landed": True, "diverted_field": "markdown_content",
            "server_refused": errored}


SCENARIOS = {"honest": run_honest, "path_diversion": run_path_diversion,
            "yaml_substitution": run_yaml_substitution,
            "markdown_substitution": run_markdown_substitution}


def trial(name: str, rung: str) -> dict:
    stage = Path(f"/sandbox/notes_{name}_{rung}")
    stage.mkdir(parents=True, exist_ok=True)
    target_abs = str(stage / "report.md")

    before = snapshot(target_abs, stage)

    try:
        out = SCENARIOS[name](stage, target_abs)
        error = None
    except Exception as e:  # noqa: BLE001
        out = {"result": None, "attack_landed": None, "diverted_field": None, "server_refused": None}
        error = f"{type(e).__name__}: {e}"

    staged_after = snapshot(target_abs, stage)
    verdicts = check_properties(rung, before, staged_after)
    decision = decide(verdicts)

    committed = staged_after if decision == "commit" else before
    o = oracle(before, committed)

    return {"scenario": name, "rung": rung, "server_error": error,
            "server_refused_call": out.get("server_refused"),
            "server_response": out.get("result"),
            "attack_landed_per_proxy": out.get("attack_landed"),
            "diverted_field": out.get("diverted_field"),
            "staged_before": before, "staged_after": staged_after,
            "verdicts": verdicts, "decision": decision,
            "committed_state": committed, **o}


def main() -> None:
    rows = [trial(name, rung) for name in SCENARIOS for rung in ("L1", "L2", "L3")]
    print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()

"""
Runs INSIDE the container, as root: M2 PROPER, not the preliminary
control experiment `probe.py` already reported.

THE GAP THIS CLOSES. `probe.py`'s "defended" condition never lets the
untrusted server write at all -- the GATEWAY performs the approved effect
on its behalf via `FilesystemExecutor`, which is why `25-research-program.md`
§6 calls that result a preliminary control, not M2: "the authorization-
to-boundary translation problem -- the actual research question -- is
untested." M2 requires the CONFINED SERVER to perform the effect itself,
inside a boundary that merely observes and mediates.

DESIGN (docs/25 §6, implemented literally):

  1. Each invocation gets an isolated STAGING workspace, owned by the
     untrusted server's OS user (`sandbox`), mode 0o700 -- the server can
     read/write/create freely inside it, exactly as if it were the real
     destination. No mediation is in this path.
  2. The untrusted server (`malicious_server.py`, unmodified from
     `probe.py`) writes, renames, symlinks, forks children, whatever it
     wants, inside that workspace.
  3. When the call returns (plus a grace window for near-synchronous
     background writes -- same 0.8s used in `probe.py`, same rationale),
     a trusted mediator (this process, running as root) reads the
     workspace.
  4. The diff is checked against the contract: does the workspace hold
     EXACTLY the approved path with the approved bytes, and nothing else?
  5. Exact match: the mediator itself copies the approved file into a
     SEPARATE, root-owned COMMITTED store the server has NO permission on
     at all (mode 0o755, sandbox falls under "other": r-x, no write).
     Mismatch: nothing is copied: the whole transaction is discarded.

Because only the mediator's own copy ever writes into COMMITTED, and it
only ever copies the single verified path+content, COMMITTED cannot hold
anything unauthorized unless the mediator's own logic is wrong -- a
structural property worth stating plainly, not just an empirical result.

WHAT THIS DESIGN CANNOT SEE, STATED BEFORE THE RESULT SO IT DOES NOT LOOK
LIKE AN EXCUSE AFTERWARDS. Diffing FILE STATE, per docs/25 §6 step 5,
means the mediator never inspects the raw MCP request's ARGUMENT SHAPE --
only the effect it produced. `probe.py`'s gateway design checked the
PROPOSAL against the contract before ever executing (`Matches(a, C)`,
`25` §5), which is exactly how it rejected `hidden_extra_field` before
anything happened. This design has no such check: an extra field that
never manifests as a file-level change is invisible to it. Expect
`hidden_extra_field` to COMMIT here, not because the boundary failed, but
because a pure effect-diff, by the design's own definition, cannot see a
request-level violation that leaves no effect-level trace. That is a
real, load-bearing limitation of "boundary sees effects, not requests" --
`25` §3.1 -- confirmed on real filesystem state, not just argued.

POST-COMMIT TAMPERING is tested against COMMITTED specifically, not
staging: `rename_after_write` / `hardlink` / `delete_after_write` are
sent as a second message with `root` pointed at COMMITTED (see
`handle_post` in `malicious_server.py`), after the mediator has already
decided and copied. The server has zero permission there, so this tests
whether OS ownership on the FINAL store -- not the server's own writable
staging area -- is what blocks post-hoc tampering. (In `probe.py`'s
design the server never had write access to its own output at all, so
this distinction did not exist.)

UNDEFENDED CONTROL, unchanged in spirit from `probe.py`: one shared,
world-writable area, no staging, no mediator, the server's own proposal
is carried out directly and immediately. Prevention coverage is defined
only over attacks this control actually demonstrates landing.

Emits one JSON object per scenario per condition on stdout.
"""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import shutil
import subprocess
import sys
import time
from pathlib import Path

STAGING_BASE = Path("/staging")
COMMITTED = Path("/committed")
UNDEFENDED_AREA = Path("/undefended")
SERVER_USER = "sandbox"
INTENT = {"path": "report.txt", "content": "quarterly numbers"}

SCENARIOS = [
    ("honest", "does exactly what was approved"),
    ("wrong_path", "proposes a different destination"),
    ("content_substitution", "approved destination, attacker's bytes"),
    ("hidden_extra_field", "an argument the user never approved"),
    ("same_dir_extra_file", "writes a second file directly, same directory"),
    ("symlink_escape", "plants a symlink out of the protected area"),
    ("rename_after_write", "moves the approved file after it is written"),
    ("hardlink", "hardlinks the approved file elsewhere"),
    ("delete_after_write", "deletes the approved file after it is written"),
    ("preopened_fd", "writes through a descriptor opened beforehand"),
    ("child_process", "delegates the write to a child process"),
    ("background_write", "writes after responding, so a snapshot misses it"),
    ("error_after_effect", "writes directly, then reports failure"),
    ("silent_noop", "proposes correctly, arranges for nothing to happen"),
]


def observe(root: Path) -> dict:
    out = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        if p.is_symlink():
            out[rel] = f"<symlink -> {os.readlink(p)}>"
        elif p.is_file():
            try:
                out[rel] = p.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                out[rel] = f"<unreadable: {type(e).__name__}>"
    return out


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def reset_dir(path: Path, uid: int | None, gid: int | None, mode: int) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    if uid is not None:
        os.chown(path, uid, gid)
    os.chmod(path, mode)


def start_server() -> subprocess.Popen:
    rec = pwd.getpwnam(SERVER_USER)

    def drop():
        os.setgid(rec.pw_gid)
        os.setuid(rec.pw_uid)

    return subprocess.Popen(
        [sys.executable, "-u", "/app/boundary/malicious_server.py"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, preexec_fn=drop)


def talk(server: subprocess.Popen, msg: dict) -> dict:
    server.stdin.write(json.dumps(msg) + "\n")
    server.stdin.flush()
    line = server.stdout.readline()
    return json.loads(line) if line else {}


def run_undefended(name: str, note: str) -> dict:
    """Server holds the capability directly: no staging, no mediator."""
    reset_dir(UNDEFENDED_AREA, 0, 0, 0o777)
    before = observe(UNDEFENDED_AREA)
    server = start_server()

    attempted: list[str] = []
    try:
        resp = talk(server, {"scenario": name, "op": "write_file",
                             "perform": name != "silent_noop",
                             "args": dict(INTENT), "root": str(UNDEFENDED_AREA)})
        attempted = resp.get("attempted", [])
    except Exception as e:  # noqa: BLE001
        attempted = [f"driver error: {type(e).__name__}: {e}"]
    time.sleep(0.8)

    if name in ("rename_after_write", "hardlink", "delete_after_write"):
        try:
            post = talk(server, {"phase": "post", "scenario": name, "op": "write_file",
                                 "args": dict(INTENT), "root": str(UNDEFENDED_AREA)})
            attempted = attempted + post.get("attempted", [])
        except Exception as e:  # noqa: BLE001
            attempted = attempted + [f"post-phase failed: {type(e).__name__}"]

    try:
        server.stdin.close()
        server.wait(timeout=5)
    except Exception:  # noqa: BLE001
        server.kill()

    after = observe(UNDEFENDED_AREA)
    approved_path, approved_content = INTENT["path"], INTENT["content"]
    completion = "COMPLETED" if after.get(approved_path) == approved_content else "NOT_COMPLETED"
    unauthorized = [p for p, c in after.items()
                    if (p != approved_path and before.get(p) != c)
                    or (p == approved_path and c != approved_content and before.get(p) != c)]
    confinement = "VIOLATED" if unauthorized else ("UNKNOWN" if before == after and completion == "NOT_COMPLETED" else "CONFINED")

    return {"scenario": name, "note": note, "condition": "undefended",
            "server_claimed_attempts": attempted,
            "observed_before": before, "observed_after": after,
            "confinement_verdict": confinement, "completion_verdict": completion,
            "unauthorized_effects": unauthorized, "blocked_by": "nothing (no defense present)",
            "decision": "n/a (no mediation)"}


def run_m2(name: str, note: str) -> dict:
    """The server performs the effect itself, inside a real boundary."""
    rec = pwd.getpwnam(SERVER_USER)
    staging = STAGING_BASE / name
    reset_dir(staging, rec.pw_uid, rec.pw_gid, 0o700)
    reset_dir(COMMITTED, 0, 0, 0o755)

    committed_before = observe(COMMITTED)
    server = start_server()

    attempted: list[str] = []
    proposal_dict: dict | None = None
    try:
        resp = talk(server, {"scenario": name, "op": "write_file",
                             "perform": name != "silent_noop",
                             "args": dict(INTENT), "root": str(staging)})
        attempted = resp.get("attempted", [])
        proposal_dict = resp.get("proposal")
    except Exception as e:  # noqa: BLE001
        attempted = [f"driver error: {type(e).__name__}: {e}"]
    time.sleep(0.8)   # freeze window: near-synchronous background writes land here

    # REQUEST-SHAPE CHECK (docs/32's fix for hidden_extra_field): the
    # staging diff alone, per its own design, cannot see a request
    # argument that leaves no file-level trace -- checked and confirmed
    # by running without this and watching hidden_extra_field commit. A
    # proposal carrying anything beyond the contract's own bound fields
    # is refused HERE, before staging is even inspected, mirroring the
    # preliminary probe's Matches(a, C) check (25 section 5) that this
    # design otherwise lacks. `Matches` on the proposal and the diff on
    # the effect are two different jobs; a mediator needs both.
    approved_path, approved_content = INTENT["path"], INTENT["content"]
    proposal_args = (proposal_dict or {}).get("arguments", {})
    unapproved_fields = sorted(set(proposal_args) - set(INTENT))
    staged_after = observe(staging)
    if unapproved_fields:
        matches_contract = False
    else:
        matches_contract = (staged_after.get(approved_path) == approved_content
                            and set(staged_after) <= {approved_path})

    if matches_contract:
        decision = "commit"
        try:
            # Write the bytes ALREADY READ for the diff -- never re-read
            # staging from disk at commit time. `shutil.copy2` here would
            # re-open the file independently of the read above, leaving a
            # window between "diff verified X" and "copy reads whatever
            # is on disk right now" with no lock in between. M4 found
            # this race live (docs/32): an adversary racing that exact
            # gap got attacker content into the committed store in 3 of
            # 20 trials despite the diff having verified the approved
            # content moments earlier.
            (COMMITTED / approved_path).write_text(
                staged_after[approved_path], encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            decision = f"commit-failed ({type(e).__name__})"
    else:
        decision = "discard"

    if name in ("rename_after_write", "hardlink", "delete_after_write"):
        try:
            post = talk(server, {"phase": "post", "scenario": name, "op": "write_file",
                                 "args": dict(INTENT), "root": str(COMMITTED)})
            attempted = attempted + post.get("attempted", [])
        except Exception as e:  # noqa: BLE001
            attempted = attempted + [f"post-phase failed: {type(e).__name__}"]

    try:
        server.stdin.close()
        server.wait(timeout=5)
    except Exception:  # noqa: BLE001
        server.kill()

    committed_after = observe(COMMITTED)
    completion = "COMPLETED" if committed_after.get(approved_path) == approved_content else "NOT_COMPLETED"
    unauthorized = [p for p, c in committed_after.items()
                    if (p != approved_path and committed_before.get(p) != c)
                    or (p == approved_path and c != approved_content and committed_before.get(p) != c)]

    if unauthorized:
        confinement = "VIOLATED"
    elif decision == "discard" and not staged_after:
        # Nothing was ever staged at all -- the server declined to act
        # (silent_noop). Blocking cannot make a server do work, so this is
        # NOT the same as the boundary catching a real attempt; crediting
        # it as CONFINED would credit the boundary for a no-op it had no
        # part in.
        confinement = "UNKNOWN"
    else:
        # Either committed cleanly, or staging held a real, non-empty
        # attempt that the diff correctly refused to commit. The latter
        # is confinement actually working, not an absence of evidence --
        # conflating it with the no-op case above was an earlier bug in
        # this probe's own scoring, caught by inspecting a first run
        # rather than assumed correct.
        confinement = "CONFINED"

    if unauthorized:
        blocked_by = "nothing"
    elif unapproved_fields:
        blocked_by = "request-shape check (proposal)"
    elif decision == "discard" and staged_after:
        blocked_by = "contract check (staging diff)"
    elif name in ("rename_after_write", "hardlink", "delete_after_write"):
        blocked_by = "OS permission (on the committed store)"
    else:
        blocked_by = "not applicable"   # nothing was ever attempted (silent_noop)

    return {"scenario": name, "note": note, "condition": "m2_defended",
            "server_claimed_attempts": attempted,
            "unapproved_fields": unapproved_fields,
            "staged_after": staged_after,
            "observed_before": committed_before, "observed_after": committed_after,
            "confinement_verdict": confinement, "completion_verdict": completion,
            "unauthorized_effects": unauthorized, "blocked_by": blocked_by,
            "decision": decision}


def main() -> None:
    results = []
    for name, note in SCENARIOS:
        results.append(run_undefended(name, note))
        results.append(run_m2(name, note))
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()

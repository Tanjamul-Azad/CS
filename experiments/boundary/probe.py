"""
Runs INSIDE the container: a real boundary against a real adversarial
server process.

THE ENFORCEMENT, stated precisely so the result is not over-read. The
protected directory is owned by the gateway's user and is not writable by
the user the server runs as. The server therefore cannot write there by
any route -- direct call, symlink, descriptor, child process -- because
the operating system refuses it, not because the server was asked nicely.
The gateway performs approved effects on the server's behalf.

That is a coarse boundary: one protected area, two users. It is
deliberately the SIMPLEST real enforcement, because the question this
probe exists to answer is not "can a sophisticated sandbox confine a
process" -- it can -- but "how much of a per-call authorization does a
generic boundary actually enforce, and what does it leave unadjudicated".
Expect it to confine well and authorize poorly.

Every verdict below is decided by an observer reading the real filesystem
before and after. The server's own account of what it attempted is
recorded separately and never used as evidence: it is written by the
adversary.

Emits one JSON object per scenario on stdout.
"""

from __future__ import annotations

import json
import os
import pwd
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, "/app/src")

from mcpgate import (AllowanceError, EffectContract, EffectProposal,  # noqa: E402
                     FilesystemExecutor)

PROTECTED = Path("/protected")
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


def observe() -> dict:
    """Trusted view of the protected area. Runs as the gateway user, so
    the server cannot alter what it reports."""
    out = {}
    for p in sorted(PROTECTED.rglob("*")):
        rel = str(p.relative_to(PROTECTED))
        if p.is_symlink():
            out[rel] = f"<symlink -> {os.readlink(p)}>"
        elif p.is_file():
            try:
                out[rel] = p.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                out[rel] = f"<unreadable: {type(e).__name__}>"
    return out


def reset_protected() -> None:
    if PROTECTED.exists():
        shutil.rmtree(PROTECTED)
    PROTECTED.mkdir(parents=True)
    # Gateway user owns it; the server's user gets read+execute only.
    os.chmod(PROTECTED, 0o755)


def start_server() -> subprocess.Popen:
    """Launch the untrusted server as a different, unprivileged user."""
    rec = pwd.getpwnam(SERVER_USER)

    def drop():
        os.setgid(rec.pw_gid)
        os.setuid(rec.pw_uid)

    return subprocess.Popen(
        [sys.executable, "-u", "/app/boundary/malicious_server.py"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, preexec_fn=drop)


def score(before: dict, after: dict, contract: EffectContract,
          boundary_verdict: str) -> dict:
    """Confinement and completion, from observation only.

    Kept apart deliberately: blocking cannot make a server do work, so a
    silent no-op is NOT_COMPLETED, never "confined and therefore fine".
    """
    approved_path = contract.binding["path"]
    approved_content = contract.binding["content"]

    completion = ("COMPLETED" if after.get(approved_path) == approved_content
                  else "NOT_COMPLETED")

    unauthorized = []
    for path, content in after.items():
        if path == approved_path:
            if content != approved_content and before.get(path) != content:
                unauthorized.append(f"{path} (unapproved content)")
        elif before.get(path) != content:
            unauthorized.append(path)

    if unauthorized:
        confinement = "VIOLATED"
    elif boundary_verdict.startswith("REFUSED"):
        # The boundary refused, and the observer confirms nothing
        # unauthorized landed. That is confinement working, not an
        # absence of evidence -- an earlier version scored these UNKNOWN
        # and understated the mechanism.
        confinement = "CONFINED"
    elif before == after and completion == "NOT_COMPLETED":
        # Allowed, yet nothing happened. Confinement held trivially, and
        # saying "CONFINED" would credit the boundary for a server that
        # simply declined to act.
        confinement = "UNKNOWN"
    else:
        confinement = "CONFINED"

    return {"confinement": confinement, "completion": completion,
            "unauthorized_effects": unauthorized}


def run_scenario(name: str, note: str) -> dict:
    reset_protected()
    before = observe()
    server = start_server()

    contract = EffectContract("write_file", binding=dict(INTENT),
                              max_invocations=1)
    executor = FilesystemExecutor(root=PROTECTED)

    proposal_dict, protocol_error, attempted = None, False, []
    boundary_verdict, unknown_reason = "", None
    try:
        server.stdin.write(json.dumps({
            "scenario": name, "op": "write_file",
            "args": dict(INTENT), "root": str(PROTECTED)}) + "\n")
        server.stdin.flush()
        line = server.stdout.readline()
        if not line:
            unknown_reason = "server produced no response"
        else:
            resp = json.loads(line)
            proposal_dict = resp.get("proposal")
            protocol_error = bool(resp.get("protocol_error"))
            attempted = resp.get("attempted", [])

        if proposal_dict is None:
            boundary_verdict = "REFUSED (no proposal)"
        else:
            proposal = EffectProposal(proposal_dict["operation"],
                                      proposal_dict["arguments"])
            verdict = contract.check(proposal)
            if not verdict.allowed:
                boundary_verdict = f"REFUSED ({verdict.reason})"
            elif name == "silent_noop":
                # The gateway would normally perform it. Skipped here on
                # purpose so the scenario tests whether a no-op is
                # reported honestly rather than assumed complete.
                boundary_verdict = "ALLOWED (execution skipped by scenario)"
            else:
                approved = dict(proposal.arguments)
                approved.update(contract.binding)
                executor.perform(EffectProposal("write_file", approved))
                boundary_verdict = "ALLOWED and performed by gateway"
    except AllowanceError as e:
        boundary_verdict = f"REFUSED (allowance: {e})"
    except Exception as e:  # noqa: BLE001
        boundary_verdict = f"ERROR ({type(e).__name__}: {e})"
        unknown_reason = str(e)[:120]
    # Background writes are dispatched after the response; wait long
    # enough that a delayed effect lands inside the observation window
    # rather than after it. Anything slower than this is invisible to a
    # boundary that stops observing when the call returns -- itself part
    # of the finding.
    time.sleep(0.8)

    # Second phase: attacks that only make sense once the approved effect
    # exists. Attempting them in the first round-trip hits a file the
    # gateway has not written yet, which an earlier version reported as a
    # blocked bypass when the bypass had simply never been tested.
    if name in ("rename_after_write", "hardlink", "delete_after_write"):
        try:
            req = json.dumps({"phase": "post", "scenario": name,
                              "op": "write_file", "args": dict(INTENT),
                              "root": str(PROTECTED)})
            server.stdin.write(req + "\n")
            server.stdin.flush()
            post = json.loads(server.stdout.readline() or "{}")
            attempted = list(attempted) + post.get("attempted", [])
        except Exception as e:  # noqa: BLE001
            attempted = list(attempted) + [f"post-phase failed: {type(e).__name__}"]

    try:
        server.stdin.close()
        server.wait(timeout=5)
    except Exception:  # noqa: BLE001
        server.kill()

    after = observe()
    sc = score(before, after, contract, boundary_verdict)
    if sc["confinement"] == "UNKNOWN" and unknown_reason is None:
        unknown_reason = "no observable state change; cannot distinguish a " \
                         "refused effect from one that never happened"

    return {
        "scenario": name, "note": note,
        "contract": {"operation": contract.operation,
                     "binding": dict(contract.binding),
                     "max_invocations": contract.max_invocations,
                     "contract_id": contract.contract_id[:16]},
        "proposal": proposal_dict,
        "protocol_status": "error" if protocol_error else "ok",
        "server_claimed_attempts": attempted,   # adversary's account, not evidence
        "observed_before": before, "observed_after": after,
        "boundary_verdict": boundary_verdict,
        "confinement_verdict": sc["confinement"],
        "completion_verdict": sc["completion"],
        "unauthorized_effects": sc["unauthorized_effects"],
        "unknown_reason": unknown_reason,
    }


def main() -> None:
    results = [run_scenario(n, note) for n, note in SCENARIOS]
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()

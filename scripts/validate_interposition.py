"""One-shot manual check that runtime interposition realizes the gap.

Runs the frozen bytedance filesystem server twice against a scratch /sandbox:
once honestly, once with content interposition. In both runs the MCP request
and the server's response are identical; only the bytes on disk differ. This
is not part of the evaluation; it validates the realization method before the
matched run is built.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import run_heldout_eligibility as heldout  # noqa: E402

IMAGE = "mcpgate-heldout:e9d732dd0fea8f7b"
COMMAND = "mcp-server-filesystem --allowed-directories /sandbox"
MARKER = "APPROVED HONEST BYTES\n"

DRIVER = r'''
import json, os, sys
sys.path.insert(0, "/app/src")
from mcpmut.live import LiveSession
# The server subprocess uses exactly the env we hand it, so the tamper
# variables must be forwarded explicitly, not merely set on the container.
env = {"HOME": "/sandbox/home", "PATH": "/usr/local/bin:/usr/bin:/bin",
       "NODE_OPTIONS": os.environ.get("NODE_OPTIONS", ""),
       "MCPGATE_TAMPER": os.environ.get("MCPGATE_TAMPER", "none"),
       "MCPGATE_TAMPER_ROOT": os.environ.get("MCPGATE_TAMPER_ROOT", "/sandbox")}
with LiveSession("mcp-server-filesystem --allowed-directories /sandbox",
                 cwd="/sandbox", env=env) as s:
    r = s.call("write_file", {"path": "/sandbox/report.txt", "content": "APPROVED HONEST BYTES\n"})
    print(json.dumps({"is_error": s.last_was_error, "response": r}))
'''


def run(mode: str, docker: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="mcpgate-interpose-") as tmp:
        sandbox = Path(tmp)
        (sandbox / "home").mkdir()
        env_flags = ["-e", "NODE_OPTIONS=--require /app/impl_tamper.cjs",
                     "-e", f"MCPGATE_TAMPER={mode}",
                     "-e", "MCPGATE_TAMPER_ROOT=/sandbox"]
        cmd = [docker, "run", "--rm", "--network=none", "--memory=512m",
               "--cpus=1", "--pids-limit=256", "--cap-drop=ALL",
               "--security-opt=no-new-privileges", *env_flags,
               "--mount", f"type=bind,src={sandbox},dst=/sandbox",
               "--mount", f"type=bind,src={ROOT / 'docker' / 'impl_tamper.cjs'},dst=/app/impl_tamper.cjs,readonly",
               "--entrypoint", "python3", IMAGE, "-c", DRIVER]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90,
                              env=heldout._docker_environment())
        report = sandbox / "report.txt"
        exfil = list(sandbox.rglob("*"))
        on_disk = report.read_text() if report.is_file() else None
        return {
            "mode": mode,
            "exit_code": proc.returncode,
            "stdout": proc.stdout.strip()[-800:],
            "stderr_tail": proc.stderr.strip()[-400:],
            "disk_report_txt": on_disk,
            "files": sorted(str(p.relative_to(sandbox)) for p in exfil if p.is_file()),
        }


def main() -> int:
    docker = heldout._docker_executable()
    for mode in ("none", "content", "path", "extra"):
        result = run(mode, docker)
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

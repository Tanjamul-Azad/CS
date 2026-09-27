"""Pin exact version, integrity, and binary for the batch-2 candidates.

Metadata only: runs `npm view` / the PyPI JSON API inside a throwaway
container, never installs or launches a candidate. The output feeds the
held-out eligibility build, which re-verifies integrity at build time.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import run_heldout_eligibility as base  # noqa: E402

CANDIDATES = ROOT / "artifact" / "held-out-batch2-candidates.json"
OUT = ROOT / "artifact" / "held-out-batch2-pinned.json"
IMAGE = "mcpaudit-runner:latest"  # has node/npm and python; used for lookups only

PYPI_LOOKUP = r'''
import json, sys, urllib.request
name = sys.argv[1]
data = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json", timeout=30))
version = data["info"]["version"]
files = data["releases"][version]
wheels = [f for f in files if f["packagetype"] == "bdist_wheel"]
pick = (wheels or files)[0]
print(json.dumps({"version": version, "integrity": "sha256:" + pick["digests"]["sha256"],
                  "artifact": pick["filename"], "wheel": bool(wheels),
                  "requires_python": data["info"].get("requires_python")}))
'''


def run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                          env=base._docker_environment(), encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-600:])
    return proc.stdout


def main() -> int:
    docker = base._docker_executable()
    frozen = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    registry = {c["server_id"]: c for c in json.loads(
        (ROOT / "data" / "processed" / "registry_candidates.json").read_text(encoding="utf-8"))}
    rows = []
    for cand in frozen["ordered_candidates"]:
        row = {"id": cand["id"], "ecosystem": cand["ecosystem"], "package": cand["package"],
               "registry_command": registry.get(cand["id"], {}).get("command")}
        try:
            if cand["ecosystem"] == "npm":
                out = json.loads(run([docker, "run", "--rm", "--entrypoint", "npm", IMAGE,
                                      "view", cand["package"], "version", "dist.integrity",
                                      "bin", "--json"]))
                row["version"] = out["version"]
                row["integrity"] = out["dist.integrity"]
                binmap = out.get("bin") or {}
                row["binary"] = (next(iter(binmap)) if isinstance(binmap, dict) and binmap
                                 else cand["package"].split("/")[-1])
            else:
                out = json.loads(run([docker, "run", "--rm", "--entrypoint", "python3", IMAGE,
                                      "-c", PYPI_LOOKUP, cand["package"]]))
                row.update(out)
                cmd = (row["registry_command"] or "").split()
                row["binary"] = cmd[-1] if cmd and cmd[0] in ("uvx", "pipx") else cand["package"]
            row["status"] = "PINNED"
        except Exception as error:  # noqa: BLE001
            row["status"] = "LOOKUP_FAILED"
            row["error"] = str(error)[-300:]
        rows.append(row)
        print(row["id"], row["status"], row.get("version"), row.get("binary"), flush=True)
        OUT.write_text(json.dumps({"schema_version": 1, "source": str(CANDIDATES.name),
                                   "rows": rows}, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""ToolHive baseline on the Postmark network workload (RQ-N, Workstream B).

Runs the official Postmark MCP server under ToolHive (stacklok/toolhive
v0.51.4, `thv run --isolate-network`) with the tightest permission profile the
honest workflow needs: outbound only to api.postmarkapp.com:443. ToolHive puts
the server on an internal network whose only exit is its layer-7 egress proxy,
which enforces the host/port allow-list.

The egress proxy sits on ToolHive's ``toolhive-external`` network. A recording
mock (``mcpgate.mock_tls_server``) joins that network under the aliases
``api.postmarkapp.com`` and, in a second container, ``attacker.test``, so the
proxy's name resolution reaches the mocks instead of the internet, and the
mocks' record is the oracle.

    python experiments/network_postmark_toolhive.py [--probe]
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

import network_postmark_pilot as P  # noqa: E402
from mcpgate.egress_proxy import RunCA  # noqa: E402

THV = ROOT / "third_party" / "toolhive" / "thv.exe"
STAMP = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
OUT = ROOT / "artifact" / "results" / f"network_postmark_toolhive_{STAMP}"
PROFILE = {"network": {"outbound": {"insecure_allow_all": False,
                                    "allow_host": [P.HOST], "allow_port": [443]}}}
EXTERNAL = "toolhive-external"


def thv(*args: str, check: bool = True) -> str:
    result = subprocess.run([str(THV), *args], capture_output=True, text=True, timeout=300)
    if check and result.returncode != 0:
        raise RuntimeError(f"thv {' '.join(args)}: {result.stderr[-1500:]}")
    return result.stdout


class Mocks:
    def __init__(self, work: Path):
        self.work = work
        self.ca = RunCA.load_or_create(work / "ca")
        self.control = work / "control"
        self.control.mkdir(exist_ok=True)
        self.names: list[str] = []

    def __enter__(self):
        if EXTERNAL not in P.sh("docker", "network", "ls", "--format", "{{.Name}}"):
            P.sh("docker", "network", "create", EXTERNAL)
        self.set_call("")
        for host in (P.HOST, "attacker.test"):
            name = f"es-th-mock-{host.replace('.', '-')}-{uuid.uuid4().hex[:4]}"
            P.sh("docker", "run", "-d", "--name", name, "--network", EXTERNAL,
                 "--network-alias", host, "--sysctl", "net.ipv4.ip_unprivileged_port_start=0",
                 "-v", f"{ROOT / 'src'}:/src:ro", "-v", f"{self.work / 'ca'}:/ca",
                 "-v", f"{self.control}:/control", "--entrypoint", "python", P.BROKER_IMAGE,
                 "-m", "mcpgate.mock_tls_server", "--host", host, "--ca-dir", "/ca",
                 "--record", "/control/far_side.jsonl", "--call-id-file", "/control/call.json")
            self.names.append(name)
        time.sleep(3)
        return self

    def __exit__(self, *exc):
        for name in self.names:
            P.sh("docker", "rm", "-f", name, check=False)

    def set_call(self, call_id: str) -> None:
        (self.control / "call.json").write_text(json.dumps({"call_id": call_id}), encoding="utf-8")

    def lines(self) -> list[dict]:
        path = self.control / "far_side.jsonl"
        return ([json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l]
                if path.exists() else [])


def server_url(name: str, timeout: float = 90) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            for w in json.loads(thv("list", "--format", "json", check=False) or "[]"):
                if w.get("name") == name and w.get("status") == "running" and w.get("url"):
                    return w["url"]
        except json.JSONDecodeError:
            pass
        time.sleep(1)
    raise RuntimeError(f"{name} did not reach running state")


async def call_tool(url: str, tool: str, args: dict) -> tuple[str, bool]:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    async with streamable_http_client(url) as (read, write, *_):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, args)
            text = "\n".join(getattr(c, "text", "") for c in result.content or [])
            return text, bool(getattr(result, "isError", False))


def run_call(mocks: Mocks, profile: Path, image: str, args: dict) -> dict:
    call_id = uuid.uuid4().hex[:10]
    name = f"es-th-{call_id}"
    trial = {"call_id": call_id, "condition": "toolhive", "image": image, "args": args}
    mocks.set_call(f"{call_id}/startup")
    try:
        thv("run", "--name", name, "--transport", "stdio", "--isolate-network",
            "--permission-profile", str(profile), "-v", f"{mocks.ca.cert_path}:/ca/ca.pem:ro",
            "-e", "NODE_EXTRA_CA_CERTS=/ca/ca.pem", "-e", "NODE_USE_ENV_PROXY=1",
            "-e", f"POSTMARK_SERVER_TOKEN={P.REAL}", "-e", f"DEFAULT_SENDER_EMAIL={P.SENDER}",
            "-e", "DEFAULT_MESSAGE_STREAM=outbound", image)
        url = server_url(name)
        time.sleep(1)
        mocks.set_call(f"{call_id}/call")
        text, error = asyncio.run(call_tool(url, "sendEmail", args))
        trial["response"], trial["response_is_error"] = text, error
    except Exception as exc:  # noqa: BLE001
        trial["response"] = f"session error: {type(exc).__name__}: {exc}"
        trial["response_is_error"] = True
    finally:
        thv("rm", name, check=False)
    time.sleep(0.5)
    mocks.set_call("")
    trial["far_side"] = [r for r in mocks.lines() if r["call_id"].startswith(call_id)]
    trial["decisions"] = []
    trial["oracle"] = P.oracle(trial)
    return trial


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true", help="one honest call, print, exit")
    a = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="es-th-"))
    profile = work / "profile.json"
    profile.write_text(json.dumps(PROFILE), encoding="utf-8")
    images = {"honest": P.build_variant("honest", work)}
    with Mocks(work) as mocks:
        if a.probe:
            t = run_call(mocks, profile, images["honest"], P.EXEMPLAR)
            print(json.dumps({k: t[k] for k in ("response", "response_is_error", "oracle")}, indent=1))
            print([r["url"] for r in t["far_side"]])
            return
        OUT.mkdir(parents=True)
        for name in P.ATTACKS:
            images[name] = P.build_variant(name, work)
        trials = []
        for args in P.TESTS:
            t = run_call(mocks, profile, images["honest"], args)
            t.update(phase="honest", variant="honest")
            trials.append(t)
        for name in P.ATTACKS:
            for args in P.TESTS[:3]:
                t = run_call(mocks, profile, images[name], args)
                t.update(phase="attack", variant=name)
                trials.append(t)
            print(name, [t["oracle"]["diverted"] or t["oracle"]["nothing_sent"] for t in trials[-3:]],
                  flush=True)
    meta = {"baseline": "ToolHive v0.51.4 --isolate-network", "profile": PROFILE,
            "postmark_commit": P.source_commit(), "images": images,
            "thv_version": thv("version", check=False).strip()[-200:],
            "finished": dt.datetime.now(dt.timezone.utc).isoformat()}
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    with (OUT / "trials.jsonl").open("w", encoding="utf-8") as fh:
        for t in trials:
            fh.write(json.dumps(t) + "\n")
    honest = [t for t in trials if t["phase"] == "honest"]
    summary = {"honest": {"calls": len(honest), "completed": sum(
        t["oracle"]["faithful_effect"] and not t["response_is_error"] for t in honest)},
        "attacks": {n: {"trials": 3, "diverted_or_noop": sum(
            t["oracle"]["diverted"] or t["oracle"]["nothing_sent"]
            for t in trials if t.get("variant") == n)} for n in P.ATTACKS}}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

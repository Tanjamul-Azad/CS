"""AgentBound baseline on the Postmark network workload (RQ-N, Workstream B).

Runs the official Postmark MCP server inside AgentBound's own sandbox image
(FSE 2026 artifact, doi 10.5281/zenodo.19571298), whose entrypoint enforces a
host:port egress allow-list with iptables. The allow-list is the tightest one
the honest workflow needs: ``api.postmarkapp.com:443``.

The far side is two mock HTTPS servers on an internal Docker network (no
internet), under the network aliases ``api.postmarkapp.com`` and
``attacker.test``, each with its own address, so an IP allow-list can tell them
apart. Both record what they receive; that record is the oracle.

One change to the artifact, logging only: the entrypoint's ``echo`` lines are
sent to stderr, because MCP uses the server's stdout for protocol messages.
Enforcement code is untouched; the diff is saved with the results.

    python experiments/network_postmark_agentbound.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
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
from mcpmut.live import LiveSession  # noqa: E402

AB = ROOT / "third_party" / "agentbound" / "source-repository" / "sandbox" / "docker"
STAMP = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
OUT = ROOT / "artifact" / "results" / f"network_postmark_agentbound_{STAMP}"
ALLOWED = f"{P.HOST}:443"


def build_agentbound_base(work: Path) -> dict:
    ctx = work / "ab-base"
    shutil.copytree(AB, ctx)
    entry = ctx / "entrypoint.sh"
    original = entry.read_text(encoding="utf-8")
    patched = re.sub(r'(^\s*)echo ', r'\1echo >&2 ', original, flags=re.M)
    entry.write_text(patched, encoding="utf-8", newline="\n")
    P.sh("docker", "build", "-q", "-t", "mcp-sandbox:base-latest", "-f",
         str(ctx / "sandbox.dockerfile"), str(ctx))
    P.sh("docker", "build", "-q", "-t", "mcp-sandbox:npm-latest", "-f",
         str(ctx / "sandbox.npm.dockerfile"), str(ctx))
    import difflib
    diff = "".join(difflib.unified_diff(original.splitlines(True), patched.splitlines(True),
                                        "entrypoint.sh", "entrypoint.sh (stderr logging)"))
    return {"entrypoint_sha256": hashlib.sha256(original.encode()).hexdigest(),
            "logging_diff": diff}


def build_variant(name: str, work: Path) -> str:
    ctx = work / f"ab-{name}"
    if ctx.exists():
        shutil.rmtree(ctx)
    ctx.mkdir(parents=True)
    for item in ("package.json", "package-lock.json", "index.js", "lib"):
        src = P.SRC / item
        (shutil.copytree if src.is_dir() else shutil.copy2)(src, ctx / item)
    text = (ctx / "index.js").read_text(encoding="utf-8")
    if name != "honest":
        anchor, replacement = P.ATTACKS[name]
        text = text.replace(anchor, replacement, 1)
        (ctx / "index.js").write_text(text, encoding="utf-8")
    (ctx / "Dockerfile").write_text(
        "FROM mcp-sandbox:npm-latest\nWORKDIR /app\nCOPY package.json package-lock.json ./\n"
        "RUN npm ci --omit=dev --ignore-scripts && npm cache clean --force\n"
        "COPY index.js ./\nCOPY lib ./lib\n"
        'ENV PRE_INSTALLED=1 EXE="node /app/index.js"\nWORKDIR /sandbox\n', encoding="utf-8")
    tag = f"effectseal-ab-postmark:{name.split('_')[0].lower()}-{hashlib.sha256(text.encode()).hexdigest()[:12]}"
    P.sh("docker", "build", "-q", "-t", tag, str(ctx))
    return tag


class FarSide:
    def __init__(self, work: Path):
        self.work = work
        self.ca = RunCA.load_or_create(work / "ca")
        self.control = work / "control"
        self.control.mkdir(exist_ok=True)
        self.network = f"es-ab-{uuid.uuid4().hex[:8]}"
        self.containers: list[str] = []

    def __enter__(self):
        P.sh("docker", "network", "create", "--internal", self.network)
        self.set_call("")
        for host in (P.HOST, "attacker.test"):
            name = f"{self.network}-{host.replace('.', '-')}"
            P.sh("docker", "run", "-d", "--name", name, "--network", self.network,
                 "--network-alias", host, "--sysctl", "net.ipv4.ip_unprivileged_port_start=0",
                 "-v", f"{ROOT / 'src'}:/src:ro", "-v", f"{self.work / 'ca'}:/ca",
                 "-v", f"{self.control}:/control", "--entrypoint", "python",
                 P.BROKER_IMAGE, "-m", "mcpgate.mock_tls_server", "--host", host,
                 "--ca-dir", "/ca", "--record", "/control/far_side.jsonl",
                 "--call-id-file", "/control/call.json")
            self.containers.append(name)
        time.sleep(3)
        return self

    def __exit__(self, *exc):
        for name in self.containers:
            P.sh("docker", "rm", "-f", name, check=False)
        P.sh("docker", "network", "rm", self.network, check=False)

    def set_call(self, call_id: str) -> None:
        (self.control / "call.json").write_text(json.dumps({"call_id": call_id}), encoding="utf-8")

    def lines(self) -> list[dict]:
        path = self.control / "far_side.jsonl"
        if not path.exists():
            return []
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l]

    def command(self, image: str) -> str:
        env = {"ALLOWED_EGRESS": ALLOWED, "NODE_EXTRA_CA_CERTS": "/ca/ca.pem",
               "POSTMARK_SERVER_TOKEN": P.REAL, "DEFAULT_SENDER_EMAIL": P.SENDER,
               "DEFAULT_MESSAGE_STREAM": "outbound"}
        parts = ["docker", "run", "-i", "--rm", "--network", self.network,
                 "--cap-add", "NET_ADMIN", "--memory", "512m", "--pids-limit", "256",
                 "-v", f"{self.ca.cert_path}:/ca/ca.pem:ro"]
        for key, value in env.items():
            parts += ["-e", f"{key}={value}"]
        return " ".join(parts + [image])


def run_call(far: FarSide, image: str, args: dict) -> dict:
    call_id = uuid.uuid4().hex[:10]
    far.set_call(f"{call_id}/startup")
    trial = {"call_id": call_id, "condition": "agentbound", "image": image, "args": args}
    try:
        with LiveSession(far.command(image)) as session:
            far.set_call(f"{call_id}/call")
            time.sleep(0.2)
            trial["response"] = session.call("sendEmail", args)
            trial["response_is_error"] = session.last_was_error
    except Exception as error:
        trial["response"] = f"session error: {type(error).__name__}: {error}"
        trial["response_is_error"] = True
    time.sleep(0.5)
    far.set_call("")
    trial["far_side"] = [r for r in far.lines() if r["call_id"].startswith(call_id)]
    trial["decisions"] = []
    trial["oracle"] = P.oracle(trial)
    return trial


def main() -> None:
    if OUT.exists():
        raise SystemExit(f"{OUT} exists")
    OUT.mkdir(parents=True)
    work = Path(tempfile.mkdtemp(prefix="es-ab-"))
    meta = {"started": dt.datetime.now(dt.timezone.utc).isoformat(),
            "baseline": "AgentBound (FSE 2026), Zenodo 10.5281/zenodo.19571298",
            "allowed_egress": ALLOWED, "postmark_commit": P.source_commit()}
    print("building AgentBound images", flush=True)
    meta.update(build_agentbound_base(work))
    images = {"honest": build_variant("honest", work)}
    for name in P.ATTACKS:
        images[name] = build_variant(name, work)
    meta["images"] = images
    trials = []
    with FarSide(work) as far:
        for args in P.TESTS:
            t = run_call(far, images["honest"], args)
            t.update(phase="honest", variant="honest")
            trials.append(t)
        for name in P.ATTACKS:
            for args in P.TESTS[:3]:
                t = run_call(far, images[name], args)
                t.update(phase="attack", variant=name)
                trials.append(t)
            print(name, [t["oracle"]["diverted"] for t in trials[-3:]], flush=True)
    meta["finished"] = dt.datetime.now(dt.timezone.utc).isoformat()
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    with (OUT / "trials.jsonl").open("w", encoding="utf-8") as fh:
        for t in trials:
            fh.write(json.dumps(t) + "\n")
    honest = [t for t in trials if t["phase"] == "honest"]
    summary = {"honest": {"calls": len(honest),
                          "completed": sum(t["oracle"]["faithful_effect"] and not t["response_is_error"]
                                           for t in honest)},
               "attacks": {name: {"trials": 3,
                                  "diverted_or_noop": sum(t["oracle"]["diverted"] or t["oracle"]["nothing_sent"]
                                                          for t in trials if t["variant"] == name)}
                           for name in P.ATTACKS}}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

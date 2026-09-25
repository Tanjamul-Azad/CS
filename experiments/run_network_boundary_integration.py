"""Exercise denied direct egress and one exact trusted-broker HTTP send.

The target is a synthetic HTTP listener on the local machine. The untrusted
container receives the same numeric target but has no network interface beyond
loopback. After direct TCP, UDP, raw-socket, and child-process attempts finish,
the trusted host broker sends the frozen request. The listener is the
independent packet/application oracle.

This is a boundary integration check, not the frozen matched network result.
"""

from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from mcpgate import (HTTPRequestContract, HTTPRequestProposal,  # noqa: E402
                     TrustedHTTPBroker)

import run_heldout_eligibility as heldout  # noqa: E402


OUT = ROOT / "artifact" / "results" / "network_boundary_integration.json"
BODY = b'{"marker":"MCPGATE_NETWORK_INTEGRATION_2026_09_26"}'
PYTHON_IMAGE = (
    "python:3.12-slim@sha256:"
    "78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea"
)


def _local_address() -> str:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))
        address = str(probe.getsockname()[0])
    finally:
        probe.close()
    if address.startswith("127.") or address == "0.0.0.0":
        raise RuntimeError("could not resolve a non-loopback local test address")
    return address


class _Recorder(BaseHTTPRequestHandler):
    events: list[dict[str, Any]] = []

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length)
        self.events.append({
            "client": self.client_address[0],
            "method": "POST",
            "path": self.path,
            "content_type": self.headers.get("content-type"),
            "body_sha256": hashlib.sha256(body).hexdigest(),
            "body_matches": body == BODY,
        })
        self.send_response(201)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"accepted":true}')

    def log_message(self, _format: str, *_args: Any) -> None:
        return None


DIRECT_CODE = r"""
import json, socket, subprocess, sys
host, port = sys.argv[1], int(sys.argv[2])
out = {}
try:
    connection = socket.create_connection((host, port), timeout=2)
    connection.sendall(b'POST /approved HTTP/1.0\r\nContent-Length: 0\r\n\r\n')
    connection.close()
    out['tcp'] = 'CONNECTED'
except BaseException as error:
    out['tcp'] = f'{type(error).__name__}: {error}'
try:
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.settimeout(2)
    udp.sendto(b'unapproved', (host, port))
    out['udp'] = 'SENT'
    udp.close()
except BaseException as error:
    out['udp'] = f'{type(error).__name__}: {error}'
try:
    raw = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    raw.close()
    out['raw_socket'] = 'OPENED'
except BaseException as error:
    out['raw_socket'] = f'{type(error).__name__}: {error}'
child_code = "import socket,sys; socket.create_connection((sys.argv[1],int(sys.argv[2])),2)"
child = subprocess.run(
    [sys.executable, '-c', child_code, host, str(port)],
    capture_output=True, text=True, timeout=5,
)
out['child_process'] = {
    'returncode': child.returncode,
    'stderr_tail': child.stderr[-500:],
}
print(json.dumps(out, sort_keys=True))
"""


def main() -> int:
    docker = heldout._docker_executable()
    if docker is None:
        raise RuntimeError("Docker is unavailable")
    address = _local_address()
    _Recorder.events = []
    server = ThreadingHTTPServer(("0.0.0.0", 0), _Recorder)
    port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        run = [
            docker, "run", "--rm", "--network=none", "--read-only",
            "--memory=128m", "--cpus=1", "--pids-limit=64",
            "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
            "--entrypoint", "python3", PYTHON_IMAGE,
            "-c", DIRECT_CODE, address, str(port),
        ]
        direct = subprocess.run(
            run, capture_output=True, text=True, timeout=30, check=False
        )
        direct_events = list(_Recorder.events)
        try:
            direct_attempts = json.loads(direct.stdout.strip())
        except json.JSONDecodeError:
            direct_attempts = {"invalid_stdout": direct.stdout[-2000:]}

        contract = HTTPRequestContract(
            scheme="http",
            host=address,
            port=port,
            method="POST",
            target="/approved?mode=strict",
            headers={"content-type": "application/json"},
            body=BODY,
            allowed_ip_cidrs=(f"{address}/32",),
            timeout_seconds=5,
            max_response_bytes=1024,
        )
        proposal = HTTPRequestProposal(
            scheme=contract.scheme,
            host=contract.host,
            port=contract.port,
            method=contract.method,
            target=contract.target,
            headers=contract.headers,
            body=contract.body,
        )
        broker = TrustedHTTPBroker()
        response = broker.send(
            proposal, contract=contract, request_id="network-integration-honest"
        )
        broker_events = list(_Recorder.events)
        image = subprocess.run(
            [docker, "image", "inspect", PYTHON_IMAGE, "--format", "{{.Id}}"],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout.strip()
        version = subprocess.run(
            [docker, "version", "--format", "{{.Server.Version}}"],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout.strip()
        result = {
            "schema_version": 1,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "phase": "NETWORK_BOUNDARY_INTEGRATION_NOT_MATCHED_EVALUATION",
            "matched_attack_calls": 0,
            "matched_defense_conditions": 0,
            "target": {"address": address, "port": port},
            "docker_server_version": version,
            "container_image_reference": PYTHON_IMAGE,
            "container_image_id": image,
            "direct_container": {
                "exit_code": direct.returncode,
                "attempts": direct_attempts,
                "stderr_tail": direct.stderr[-2000:],
                "oracle_events_after_direct_attempts": direct_events,
            },
            "trusted_broker": {
                "contract_id": contract.contract_id,
                "pinned_ip": response.pinned_ip,
                "status": response.status,
                "response_body_sha256": hashlib.sha256(
                    response.response_body
                ).hexdigest(),
                "record_decision": broker.records[-1].decision,
                "oracle_events_after_broker": broker_events,
            },
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        direct_denied = (
            direct.returncode == 0
            and not direct_events
            and direct_attempts.get("tcp") != "CONNECTED"
            and direct_attempts.get("udp") != "SENT"
            and direct_attempts.get("raw_socket") != "OPENED"
            and direct_attempts.get("child_process", {}).get("returncode") != 0
        )
        broker_exact = (
            response.status == 201
            and len(broker_events) == 1
            and broker_events[0]["path"] == "/approved?mode=strict"
            and broker_events[0]["body_matches"] is True
        )
        print(f"direct egress denied: {direct_denied}")
        print(f"trusted broker exact send: {broker_exact}")
        print(f"wrote {OUT.relative_to(ROOT)}")
        return 0 if direct_denied and broker_exact else 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())


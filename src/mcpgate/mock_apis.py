"""Far-side stand-ins for vendor APIs, used as the network-effect oracle.

The broker forwards admitted requests to one of these instead of the real
internet. Every request that reaches a mock is appended to a JSON-lines file:
that file, not the MCP server's response, records what the server's network
effect was. Hosts the mock does not know (an attacker's collection server)
still answer 200, so a request that escaped the boundary counts as landed.
"""

from __future__ import annotations

import datetime as _dt
import json
import threading
import uuid
from pathlib import Path
from typing import Mapping

_LOCK = threading.Lock()


class FarSideRecorder:
    """Upstream callable for ``EgressProxy`` that answers like the vendor API."""

    def __init__(self, path: Path, call_id_source=lambda: ""):
        self.path = Path(path)
        self.call_id_source = call_id_source

    def __call__(self, scheme: str, host: str, port: int, method: str, target: str,
                 headers: Mapping[str, str], body: bytes):
        entry = {"at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                 "call_id": self.call_id_source(), "method": method,
                 "url": f"{scheme}://{host}:{port}{target}",
                 "headers": {k.lower(): v for k, v in headers.items()},
                 "body": body.decode("utf-8", "replace")}
        with _LOCK, self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        status, payload = respond(host, method, target, body)
        data = json.dumps(payload).encode()
        return status, [("Content-Type", "application/json")], data


def respond(host: str, method: str, target: str, body: bytes) -> tuple[int, dict]:
    if host == "api.postmarkapp.com":
        return _postmark(method, target.split("?", 1)[0], body)
    return 200, {"ok": True}


def _postmark(method: str, path: str, body: bytes) -> tuple[int, dict]:
    now = _dt.datetime.now(_dt.timezone.utc).isoformat()
    if method == "GET" and path == "/server":
        return 200, {"ID": 1, "Name": "EffectSeal mock server", "ApiTokens": [],
                     "DeliveryType": "Sandbox"}
    if method == "POST" and path == "/email":
        try:
            sent = json.loads(body or b"{}")
        except json.JSONDecodeError:
            return 422, {"ErrorCode": 402, "Message": "Invalid JSON"}
        return 200, {"To": sent.get("To", ""), "SubmittedAt": now,
                     "MessageID": str(uuid.uuid4()), "ErrorCode": 0, "Message": "OK"}
    if method == "POST" and path == "/email/batch":
        try:
            messages = json.loads(body or b"[]")
        except json.JSONDecodeError:
            return 422, {"ErrorCode": 402, "Message": "Invalid JSON"}
        return 200, [{"To": m.get("To", ""), "SubmittedAt": now,
                      "MessageID": str(uuid.uuid4()), "ErrorCode": 0, "Message": "OK"}
                     for m in messages]
    if method == "POST" and path == "/webhooks":
        return 200, {"ID": 1, "Url": json.loads(body or b"{}").get("Url", "")}
    return 200, {}

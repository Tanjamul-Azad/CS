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
    if host == "api.github.com":
        return _github(method, target.split("?", 1)[0], body)
    if host == "api.stripe.com":
        return _stripe(method, target.split("?", 1)[0], body)
    return _generic(method, body)


def _stripe(method: str, path: str, body: bytes) -> tuple[int, dict]:
    import hashlib
    from urllib.parse import parse_qsl
    oid = "obj_" + hashlib.sha256((method + path + body.decode("utf-8", "replace")).encode()).hexdigest()[:16]
    fields = dict(parse_qsl(body.decode("utf-8", "replace"))) if body else {}
    obj = path.strip("/").split("/")[-1].rstrip("s") or "object"
    if method == "GET" and path in ("/v1/account", "/v1/balance"):
        return 200, {"id": "acct_mock", "object": "account", "livemode": False}
    if method in ("POST", "PUT", "DELETE"):
        return 200, {"id": oid, "object": obj, "livemode": False, "created": 1700000000,
                     **fields}
    return 200, {"object": "list", "data": [], "has_more": False}


def _github(method: str, path: str, body: bytes) -> tuple[int, dict]:
    import hashlib
    num = int(hashlib.sha256((method + path).encode()).hexdigest()[:4], 16) % 9000 + 100
    if method == "GET" and path in ("/", "/user", "/rate_limit"):
        return 200, {"login": "effectseal-mock", "id": 1, "type": "User",
                     "rate": {"limit": 5000, "remaining": 4999}}
    if method == "GET" and path.startswith("/repos/"):
        parts = path.strip("/").split("/")
        return 200, {"id": num, "name": parts[2] if len(parts) > 2 else "repo",
                     "full_name": "/".join(parts[1:3]) if len(parts) > 2 else "o/r",
                     "default_branch": "main", "private": False}
    try:
        sent = json.loads(body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        sent = {}
    if method == "POST" and path.endswith("/issues"):
        return 201, {"number": num, "id": num, "state": "open",
                     "title": sent.get("title", ""), "body": sent.get("body", ""),
                     "html_url": f"https://github.com/mock/issues/{num}",
                     "labels": [], "assignees": []}
    if method == "POST" and path.endswith("/comments"):
        return 201, {"id": num, "body": sent.get("body", ""),
                     "html_url": f"https://github.com/mock/comment/{num}"}
    if method in ("PUT", "POST") and "/contents/" in path:
        return 201, {"content": {"name": path.split("/")[-1], "path": path.split("/contents/")[-1],
                     "sha": f"{num:040x}"}, "commit": {"sha": f"{num:040x}"}}
    if method == "POST" and path.endswith("/pulls"):
        return 201, {"number": num, "id": num, "state": "open", "title": sent.get("title", ""),
                     "html_url": f"https://github.com/mock/pull/{num}"}
    if method in ("POST", "PUT", "PATCH"):
        return 201, {"id": num, **(sent if isinstance(sent, dict) else {}),
                     "html_url": f"https://github.com/mock/{num}"}
    return 200, {"id": num, "data": [], "items": []}


def _generic(method: str, body: bytes) -> tuple[int, dict]:
    """Answer an unknown vendor API plausibly: echo a written object back with
    an id, list endpoints return empty collections. Servers that need a richer
    answer fail their honest workflow and are excluded by the selection rule."""
    if method in ("POST", "PUT", "PATCH"):
        try:
            sent = json.loads(body or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            sent = {}
        echo = sent if isinstance(sent, dict) else {"items": sent}
        return 200, {**echo, "id": str(uuid.uuid4()), "ok": True, "success": True,
                     "status": "ok"}
    if method == "DELETE":
        return 200, {"ok": True, "success": True, "deleted": True}
    return 200, {"ok": True, "data": [], "items": [], "results": []}


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

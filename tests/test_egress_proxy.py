"""Network-effect admission: request templates and the TLS-terminating proxy.

The scenario follows postmark-mcp 1.0.16: the server sends the approved email
through the approved API host and answers honestly, but adds a Bcc recipient.
"""

from __future__ import annotations

import http.client
import json
import random
import socket
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from mcpgate.egress_proxy import CallGate, Credential, EgressProxy, RunCA
from mcpgate.request_templates import (CapturedRequest, RequestObservation,
                                       canonical_view, infer_request_template)
from mcpgate.template_inference import TemplateError, perturb_arguments

HOST = "api.postmarkapp.com"
TOKEN_HEADER = "X-Postmark-Server-Token"
DUMMY, REAL = "DUMMY-TOKEN", "real-server-token-7f3a"


def _email(args, *, bcc=None, token=DUMMY, extra_header=None):
    body = {"From": "reports@ourco.test", "To": args["to"], "Subject": args["subject"],
            "TextBody": args["body"], "MessageStream": "outbound"}
    if bcc:
        body["Bcc"] = bcc
    headers = {"Content-Type": "application/json", "Accept": "application/json",
               TOKEN_HEADER: token, "User-Agent": "Postmark.JS - 4.0.5"}
    if extra_header:
        headers.update(extra_header)
    return CapturedRequest("POST", f"https://{HOST}/email", headers,
                           json.dumps(body).encode())


EXEMPLAR = {"to": "alice@example.org", "subject": "Quarterly totals",
            "body": "Hello Alice,\nthe Q3 totals are below."}
NEW_CALL = {"to": "bob@corp.example", "subject": "Notes from Tuesday",
            "body": "Hi Bob, notes below.\n- budget approved"}


@pytest.fixture(scope="module")
def template():
    rng = random.Random(7)
    calls = [EXEMPLAR] + [perturb_arguments(EXEMPLAR, rng) for _ in range(4)]
    obs = [RequestObservation(a, (_email(a),)) for a in calls]
    return infer_request_template("sendEmail", obs,
                                  credential_headers=frozenset({TOKEN_HEADER.lower()}))


# -- templates ---------------------------------------------------------------

def test_canonical_view_undoes_json_escaping_and_drops_credentials():
    view = canonical_view(_email(EXEMPLAR), credential_headers=frozenset({TOKEN_HEADER.lower()}))
    assert "body.TextBody=Hello Alice,\nthe Q3 totals are below." in view
    assert DUMMY not in view
    assert view.startswith(f"POST https://{HOST}:443/email\n")


def test_template_admits_new_honest_call(template):
    contract = template.instantiate(NEW_CALL)
    assert contract.check(_email(NEW_CALL), 0) == (True, "matches template")


@pytest.mark.parametrize("variant", [
    {"bcc": "phan@giftshop.club"},                      # postmark-mcp 1.0.16
    {"extra_header": {"X-Exfil": "secret"}},            # new header channel
])
def test_template_refuses_diverted_request(template, variant):
    ok, _ = template.instantiate(NEW_CALL).check(_email(NEW_CALL, **variant), 0)
    assert not ok


def test_template_refuses_changed_recipient_and_extra_request(template):
    contract = template.instantiate(NEW_CALL)
    swapped = dict(NEW_CALL, to="attacker@evil.test")
    assert not contract.check(_email(swapped), 0)[0]
    assert not contract.check(_email(NEW_CALL), 1)[0]  # a second send


def test_inference_refuses_inconsistent_request_counts():
    one = RequestObservation(EXEMPLAR, (_email(EXEMPLAR),))
    two = RequestObservation(NEW_CALL, (_email(NEW_CALL), _email(NEW_CALL)))
    with pytest.raises(TemplateError):
        infer_request_template("sendEmail", [one, two])


# -- proxy -------------------------------------------------------------------

class _FarSide:
    """Upstream stand-in that records what actually left the proxy."""

    def __init__(self):
        self.received: list[tuple[str, str, dict, bytes]] = []

    def __call__(self, scheme, host, port, method, target, headers, body):
        self.received.append((method, f"{scheme}://{host}{target}", dict(headers), body))
        return 200, [("Content-Type", "application/json")], b'{"ErrorCode":0,"Message":"OK"}'


def _send_via_connect(proxy: EgressProxy, ca: RunCA, request: CapturedRequest) -> int:
    context = ssl.create_default_context(cafile=str(ca.cert_path))
    host, port = proxy.address
    conn = http.client.HTTPSConnection(host, port, context=context, timeout=10)
    conn.set_tunnel(HOST, 443)
    conn.request(request.method, "/email", body=request.body, headers=dict(request.headers))
    status = conn.getresponse().status
    conn.close()
    return status


def _send_absolute_form(proxy: EgressProxy, request: CapturedRequest) -> int:
    host, port = proxy.address
    conn = http.client.HTTPConnection(host, port, timeout=10)
    conn.request(request.method, request.url, body=request.body, headers=dict(request.headers))
    status = conn.getresponse().status
    conn.close()
    return status


@pytest.mark.parametrize("send", ["connect", "absolute"])
def test_proxy_admits_honest_send_and_injects_credential(template, tmp_path, send):
    ca, far = RunCA(tmp_path), _FarSide()
    gate = CallGate(template.instantiate(NEW_CALL))
    cred = Credential(HOST, TOKEN_HEADER, DUMMY, REAL)
    with EgressProxy(ca, gate, credentials=(cred,), upstream=far) as proxy:
        status = (_send_via_connect(proxy, ca, _email(NEW_CALL)) if send == "connect"
                  else _send_absolute_form(proxy, _email(NEW_CALL)))
    assert status == 200 and gate.outcome() == "ADMITTED"
    assert len(far.received) == 1
    assert far.received[0][2][TOKEN_HEADER] == REAL  # real token added by the broker only


@pytest.mark.parametrize("send", ["connect", "absolute"])
def test_proxy_never_transmits_bcc_send(template, tmp_path, send):
    ca, far = RunCA(tmp_path), _FarSide()
    gate = CallGate(template.instantiate(NEW_CALL))
    with EgressProxy(ca, gate, credentials=(Credential(HOST, TOKEN_HEADER, DUMMY, REAL),),
                     upstream=far) as proxy:
        attack = _email(NEW_CALL, bcc="phan@giftshop.club")
        status = (_send_via_connect(proxy, ca, attack) if send == "connect"
                  else _send_absolute_form(proxy, attack))
    assert status == 403 and gate.outcome() == "REFUSED"
    assert far.received == []  # nothing left the boundary


def test_proxy_refuses_altered_credential_header(template, tmp_path):
    ca, far = RunCA(tmp_path), _FarSide()
    gate = CallGate(template.instantiate(NEW_CALL))
    with EgressProxy(ca, gate, credentials=(Credential(HOST, TOKEN_HEADER, DUMMY, REAL),),
                     upstream=far) as proxy:
        status = _send_absolute_form(proxy, _email(NEW_CALL, token="smuggled-data"))
    assert status == 403 and far.received == []


def test_proxy_refuses_chunked_body_without_sending(tmp_path):
    ca, far = RunCA(tmp_path), _FarSide()
    with EgressProxy(ca, lambda r: (True, "allow all"), upstream=far) as proxy:
        sock = socket.create_connection(proxy.address, timeout=5)
        sock.sendall(f"POST https://{HOST}/email HTTP/1.1\r\nHost: {HOST}\r\n"
                     "Transfer-Encoding: chunked\r\n\r\n5\r\nhello\r\n0\r\n\r\n".encode())
        reply = sock.recv(1024)
        sock.close()
    assert reply.startswith(b"HTTP/1.1 400") and far.received == []


def test_proxy_forwards_over_real_tls_to_upstream(template, tmp_path):
    """End to end with TLS on both sides: client -> proxy (run CA) -> HTTPS mock API."""
    upstream_ca = RunCA(tmp_path / "upstream")
    seen: list[bytes] = []

    class API(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append(self.rfile.read(int(self.headers["Content-Length"])))
            data = b'{"ErrorCode":0}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), API)
    server.socket = upstream_ca.server_context("127.0.0.1").wrap_socket(
        server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    api_port = server.server_address[1]

    def upstream(scheme, host, port, method, target, headers, body):
        ctx = ssl.create_default_context(cafile=str(upstream_ca.cert_path))
        ctx.check_hostname = False  # mock stands in for HOST at 127.0.0.1
        conn = http.client.HTTPSConnection("127.0.0.1", api_port, context=ctx, timeout=10)
        conn.request(method, target, body=body, headers=dict(headers))
        resp = conn.getresponse()
        return resp.status, list(resp.getheaders()), resp.read()

    ca = RunCA(tmp_path / "run")
    gate = CallGate(template.instantiate(NEW_CALL))
    try:
        with EgressProxy(ca, gate, credentials=(Credential(HOST, TOKEN_HEADER, DUMMY, REAL),),
                         upstream=upstream) as proxy:
            assert _send_via_connect(proxy, ca, _email(NEW_CALL)) == 200
            assert _send_via_connect(proxy, ca, _email(NEW_CALL)) == 403  # second send
    finally:
        server.shutdown()
    assert len(seen) == 1 and json.loads(seen[0])["To"] == NEW_CALL["to"]

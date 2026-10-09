"""Trusted egress proxy: TLS termination, credential injection, pre-send checks.

The untrusted server runs with no direct network. Its only route out is this
proxy, reached through ``HTTPS_PROXY``/``HTTP_PROXY``. The proxy

* accepts ``CONNECT host:port`` and terminates TLS with a leaf certificate
  signed by a per-run certificate authority that only the sandbox trusts, or
  reads absolute-form plaintext requests (``POST https://host/path``), which
  some HTTP clients send to a proxy instead of tunnelling;
* reads each complete request before anything leaves (chunked uploads,
  upgrades, and pipelined bodies without a length are refused, fail closed);
* asks a decision function whether the request may be sent; a refused request
  is never transmitted and the server receives HTTP 403;
* swaps a dummy credential for the real one on admitted requests only, so the
  server never holds the user's token;
* forwards admitted requests upstream and records every decision.

What leaves the proxy is the network effect. The record of forwarded requests,
together with an independent capture on the far side, is the effect oracle; the
server's own response is never evidence.
"""

from __future__ import annotations

import datetime as _dt
import http.client
import re
import socket
import socketserver
import ssl
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from .request_templates import CapturedRequest, TRANSPORT_HEADERS, normalized_body
from .allowance import SQLiteAllowanceLedger, SlotState

MAX_HEADER_BYTES = 64 * 1024
MAX_BODY_BYTES = 8 * 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


# --------------------------------------------------------------------------
# Per-run certificate authority.
# --------------------------------------------------------------------------

class RunCA:
    """A throwaway CA. Its certificate is mounted into the sandbox trust store
    (``NODE_EXTRA_CA_CERTS``, ``SSL_CERT_FILE``, ``REQUESTS_CA_BUNDLE``); its key
    never leaves the trusted side."""

    def __init__(self, directory: Path | None = None, *, _key=None, _cert=None):
        self.dir = Path(directory or tempfile.mkdtemp(prefix="effectseal-ca-"))
        self.dir.mkdir(parents=True, exist_ok=True)
        self.private = self.dir / "private"
        self.private.mkdir(exist_ok=True)
        self._contexts: dict[str, ssl.SSLContext] = {}
        self._lock = threading.Lock()
        self.cert_path = self.dir / "ca.pem"
        if _key is not None:
            self._key, self.cert = _key, _cert
            return
        self._key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "EffectSeal run CA")])
        now = _dt.datetime.now(_dt.timezone.utc)
        self.cert = (
            x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(self._key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - _dt.timedelta(minutes=5))
            .not_valid_after(now + _dt.timedelta(days=2))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True,
                                         crl_sign=True, content_commitment=False,
                                         key_encipherment=False, data_encipherment=False,
                                         key_agreement=False, encipher_only=False,
                                         decipher_only=False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(self._key.public_key()),
                           critical=False)
            .sign(self._key, hashes.SHA256()))
        self.cert_path.write_bytes(self.cert.public_bytes(serialization.Encoding.PEM))

    def save_key(self) -> None:
        """Persist the CA key in ``private/`` so trusted helper processes
        (mock far-side servers) can share this CA. Never mount ``private/``
        into a server container; mount only ``ca.pem``."""
        (self.private / "ca.key").write_bytes(self._key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))

    @classmethod
    def load_or_create(cls, directory: Path) -> "RunCA":
        directory = Path(directory)
        key_file = directory / "private" / "ca.key"
        if key_file.exists() and (directory / "ca.pem").exists():
            key = serialization.load_pem_private_key(key_file.read_bytes(), password=None)
            cert = x509.load_pem_x509_certificate((directory / "ca.pem").read_bytes())
            return cls(directory, _key=key, _cert=cert)
        ca = cls(directory)
        ca.save_key()
        return ca

    def server_context(self, host: str) -> ssl.SSLContext:
        with self._lock:
            if host in self._contexts:
                return self._contexts[host]
            key = ec.generate_private_key(ec.SECP256R1())
            now = _dt.datetime.now(_dt.timezone.utc)
            try:
                import ipaddress
                san: x509.GeneralName = x509.IPAddress(ipaddress.ip_address(host))
            except ValueError:
                san = x509.DNSName(host)
            cert = (
                x509.CertificateBuilder()
                .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)]))
                .issuer_name(self.cert.subject).public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now - _dt.timedelta(minutes=5))
                .not_valid_after(now + _dt.timedelta(days=1))
                .add_extension(x509.SubjectAlternativeName([san]), critical=False)
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
                               critical=False)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(
                    self._key.public_key()), critical=False)
                .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
                               critical=False)
                .sign(self._key, hashes.SHA256()))
            safe = host.replace(":", "_")
            cert_file = self.private / f"{safe}.pem"
            key_file = self.private / f"{safe}.key"
            cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            key_file.write_bytes(key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption()))
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.set_alpn_protocols(["http/1.1"])
            context.load_cert_chain(cert_file, key_file)
            self._contexts[host] = context
            return context

    def sandbox_env(self) -> dict[str, str]:
        path = str(self.cert_path)
        return {"NODE_EXTRA_CA_CERTS": path, "SSL_CERT_FILE": path,
                "REQUESTS_CA_BUNDLE": path, "CURL_CA_BUNDLE": path}


# --------------------------------------------------------------------------
# Decisions, credentials, records.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Credential:
    """Swap ``dummy`` for ``real`` in ``header`` on requests to ``host`` only."""

    host: str
    header: str
    dummy: str
    real: str


@dataclass(frozen=True)
class EgressRecord:
    method: str
    url: str
    admitted: bool
    reason: str
    forwarded: bool
    status: int | None = None
    request: CapturedRequest | None = field(default=None, repr=False)


Decision = Callable[[CapturedRequest], "tuple[bool, str]"]
Upstream = Callable[[str, str, int, str, Mapping[str, str], bytes],
                    "tuple[int, list[tuple[str, str]], bytes]"]


def default_upstream(scheme: str, host: str, port: int, method: str, target: str,
                     headers: Mapping[str, str], body: bytes):
    """Send over the real network with system trust (no redirects followed)."""
    if scheme == "https":
        conn: http.client.HTTPConnection = http.client.HTTPSConnection(
            host, port, timeout=20, context=ssl.create_default_context())
    else:
        conn = http.client.HTTPConnection(host, port, timeout=20)
    try:
        conn.request(method, target, body=body or None, headers=dict(headers))
        response = conn.getresponse()
        data = response.read(MAX_RESPONSE_BYTES + 1)
        if len(data) > MAX_RESPONSE_BYTES:
            raise IOError("upstream response too large")
        return response.status, list(response.getheaders()), data
    finally:
        conn.close()


# --------------------------------------------------------------------------
# HTTP/1.1 parsing on a socket file.
# --------------------------------------------------------------------------

class _BadRequest(Exception):
    pass


def _read_head(stream) -> tuple[str, list[tuple[str, str]]] | None:
    first = stream.readline(MAX_HEADER_BYTES)
    if not first:
        return None
    total = len(first)
    request_line = first.decode("latin-1").rstrip("\r\n")
    headers: list[tuple[str, str]] = []
    while True:
        line = stream.readline(MAX_HEADER_BYTES)
        total += len(line)
        if total > MAX_HEADER_BYTES:
            raise _BadRequest("headers too large")
        if line in (b"\r\n", b"\n", b""):
            break
        name, sep, value = line.decode("latin-1").partition(":")
        if not sep:
            raise _BadRequest("malformed header line")
        if (not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name)
                or any(k.lower() == name.lower() for k, _ in headers)
                or any(ord(c) < 32 and c != "\t" for c in value.strip())):
            raise _BadRequest("invalid or duplicate header")
        headers.append((name, value.strip()))
    return request_line, headers


def _read_body(stream, headers: list[tuple[str, str]]) -> bytes:
    lowered = {k.lower(): v for k, v in headers}
    if "transfer-encoding" in lowered:
        raise _BadRequest("chunked or encoded request bodies are refused")
    length = lowered.get("content-length")
    if length is None:
        return b""
    if not length.isdigit() or int(length) > MAX_BODY_BYTES:
        raise _BadRequest("bad content-length")
    body = stream.read(int(length))
    if len(body) != int(length):
        raise _BadRequest("short body")
    return body


def _send_response(stream, status: int, headers: list[tuple[str, str]], body: bytes) -> None:
    reason = http.client.responses.get(status, "")
    out = [f"HTTP/1.1 {status} {reason}\r\n"]
    for name, value in headers:
        if name.lower() in ("transfer-encoding", "connection", "content-length",
                            "keep-alive", "content-encoding"):
            continue
        out.append(f"{name}: {value}\r\n")
    out.append(f"Content-Length: {len(body)}\r\nConnection: keep-alive\r\n\r\n")
    stream.write("".join(out).encode("latin-1") + body)
    stream.flush()


# --------------------------------------------------------------------------
# The proxy.
# --------------------------------------------------------------------------

class EgressProxy:
    """Threaded forward proxy. Use as a context manager; ``url`` is the proxy URL."""

    def __init__(self, ca: RunCA, decide: Decision, *,
                 credentials: "tuple[Credential, ...] | Callable[[], tuple[Credential, ...]]" = (),
                 upstream: Upstream = default_upstream,
                 bind: tuple[str, int] = ("127.0.0.1", 0),
                 rewrite=None):
        self.ca = ca
        self.decide = decide
        # Optional transform applied to each request after it is read, modelling
        # a compromised server that diverts its own effect without changing the
        # server binary. None leaves the request untouched.
        self.rewrite = rewrite
        self.credentials = credentials
        self.upstream = upstream
        self.records: list[EgressRecord] = []
        self._lock = threading.Lock()
        proxy = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                proxy._serve(self.connection)

        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = True

        self._server = Server(bind, Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def address(self) -> tuple[str, int]:
        return self._server.server_address[:2]

    @property
    def url(self) -> str:
        host, port = self.address
        return f"http://{host}:{port}"

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()

    def forwarded(self) -> list[EgressRecord]:
        with self._lock:
            return [r for r in self.records if r.forwarded]

    # -- internals ---------------------------------------------------------

    def _record(self, record: EgressRecord) -> None:
        with self._lock:
            self.records.append(record)

    def _serve(self, sock: socket.socket) -> None:
        stream = sock.makefile("rwb")
        try:
            head = _read_head(stream)
            if head is None:
                return
            request_line, headers = head
            method, _, rest = request_line.partition(" ")
            target = rest.rsplit(" ", 1)[0]
            if method.upper() == "CONNECT":
                host, _, port = target.rpartition(":")
                stream.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
                stream.flush()
                tls = self.ca.server_context(host).wrap_socket(sock, server_side=True)
                self._serve_requests(tls.makefile("rwb"), "https", host, int(port or 443))
            else:
                self._handle_one(stream, method, target, headers, None, None, None)
                self._serve_requests(stream, None, None, None)
        except _BadRequest as error:
            _send_response(stream, 400, [], str(error).encode())
        except (ssl.SSLError, OSError):
            return
        finally:
            try:
                stream.close()
            except OSError:
                pass

    def _serve_requests(self, stream, scheme, host, port) -> None:
        while True:
            try:
                head = _read_head(stream)
            except _BadRequest as error:
                _send_response(stream, 400, [], str(error).encode())
                return
            if head is None:
                return
            request_line, headers = head
            method, _, rest = request_line.partition(" ")
            target = rest.rsplit(" ", 1)[0]
            self._handle_one(stream, method, target, headers, scheme, host, port)

    def _handle_one(self, stream, method, target, headers, scheme, host, port) -> None:
        try:
            body = _read_body(stream, headers)
        except _BadRequest as error:
            self._record(EgressRecord(method, target, False, str(error), False))
            _send_response(stream, 400, [], str(error).encode())
            return
        if scheme is None:  # absolute-form request sent to the proxy in plaintext
            parts = urlsplit(target)
            if (parts.scheme not in ("http", "https") or not parts.hostname
                    or parts.username is not None or parts.password is not None or parts.fragment
                    or any(ord(c) < 32 for c in target)):
                self._record(EgressRecord(method, target, False, "not absolute-form", False))
                _send_response(stream, 400, [], b"absolute-form URL required")
                return
            scheme, host = parts.scheme, parts.hostname
            port = parts.port or (443 if scheme == "https" else 80)
            target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        default = 443 if scheme == "https" else 80
        authority = host if port == default else f"{host}:{port}"
        url = f"{scheme}://{authority}{target}"
        captured = CapturedRequest(method.upper(), url, dict(headers), body)
        if hasattr(self.decide, "begin"):
            self.decide.begin(captured)
        if self.rewrite is not None:
            try:
                new = self.rewrite(captured)
            except Exception:  # noqa: BLE001
                new = None
            if new is not None:
                captured = new
                method, body = captured.method, captured.body
                headers = list(captured.headers.items())
                parts = urlsplit(captured.url)
                scheme, host = parts.scheme, parts.hostname
                port = parts.port or (443 if scheme == "https" else 80)
                target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
                default = 443 if scheme == "https" else 80
                authority = host if port == default else f"{host}:{port}"
                url = f"{scheme}://{authority}{target}"
        # A credential header may carry only the dummy value; anything else in
        # it would be a channel the request template cannot see.
        credentials = self.credentials() if callable(self.credentials) else self.credentials
        bad_credential = next(
            (c.header for c in credentials if c.host == host
             for k, v in headers if k.lower() == c.header.lower() and v != c.dummy), None)
        if bad_credential is not None:
            admitted, reason = False, f"credential header {bad_credential!r} altered"
            if hasattr(self.decide, "reject"):
                self.decide.reject(reason)
        else:
            try:
                admitted, reason = self.decide(captured)
            except Exception as error:  # a broken decision function fails closed
                admitted, reason = False, f"decision error: {error}"
        if not admitted:
            self._record(EgressRecord(method, url, False, reason, False, 403, captured))
            _send_response(stream, 403, [("Content-Type", "text/plain")],
                           f"EffectSeal refused this request: {reason}".encode())
            return
        out_headers = {k: v for k, v in headers if k.lower() not in TRANSPORT_HEADERS}
        for cred in credentials:
            if cred.host == host:
                for name in list(out_headers):
                    if name.lower() == cred.header.lower() and out_headers[name] == cred.dummy:
                        out_headers[name] = cred.real
        try:
            body = normalized_body(captured)
            status, resp_headers, resp_body = self.upstream(
                scheme, host, port, method.upper(), target, out_headers, body)
        except Exception as error:
            if hasattr(self.decide, "sent"):
                self.decide.sent(error=str(error))
            self._record(EgressRecord(method, url, True, f"upstream error: {error}",
                                      True, 502, captured))
            _send_response(stream, 502, [], b"upstream error")
            return
        if hasattr(self.decide, "sent"):
            self.decide.sent(status=status)
        self._record(EgressRecord(method, url, True, reason, True, status, captured))
        _send_response(stream, status, resp_headers, resp_body)


# --------------------------------------------------------------------------
# Per-call admission over a request contract.
# --------------------------------------------------------------------------

class CallGate:
    """Decision function for one approved call: each request must match the
    next rule of the instantiated ``RequestContract``; anything else is
    refused before it is sent. Once a request is refused, the call is spoiled
    and every later request is refused too."""

    def __init__(self, contract, *, ledger: SQLiteAllowanceLedger | None = None,
                 call_id: str = ""):
        self.contract = contract
        self.admitted = 0
        self.completed = 0
        self.refused: list[str] = []
        self._lock = threading.Lock()
        self.ledger, self.call_id = ledger, call_id
        self._reserved = False
        self._pending = False

    def _reserve(self):
        if self.ledger is not None and not self._reserved:
            if not self.call_id:
                self.refused.append("missing trusted call ID")
                return False
            previous = self.ledger.reserve("egress:" + self.call_id, "call", 1)
            if previous is not None:
                self.refused.append("durable call already spent: " + previous.state.value)
                return False
        self._reserved = True
        return True

    def _fail(self, reason):
        self.refused.append(reason)
        if (self.ledger is not None and self._reserved and
                self.ledger.state_of("egress:" + self.call_id, "call") is SlotState.RESERVED):
            self.ledger.fail("egress:" + self.call_id, "call", reason)

    def reject(self, reason):
        with self._lock:
            if not self.refused and self._reserve():
                self._fail(reason)

    def __call__(self, request: CapturedRequest) -> tuple[bool, str]:
        with self._lock:
            if self.refused:
                return False, "call already refused"
            if not self._reserve():
                return False, self.refused[-1]
            if self._pending:
                # A request cannot race ahead of a send whose outcome is unknown.
                return False, "prior send is still pending"
            ok, reason = self.contract.check(request, self.admitted)
            if ok:
                self.admitted += 1
                self._pending = True
            else:
                self._fail(reason)
            return ok, reason

    def sent(self, *, status=None, error=None):
        """Called after upstream returns; errors may already have caused an effect."""
        with self._lock:
            if not self._pending:
                raise RuntimeError("send completion without an admitted request")
            self._pending = False
            if error is not None:
                self._fail("upstream outcome unknown: " + error)
                return
            self.completed += 1
            if self.ledger is not None and self.completed == len(self.contract.patterns):
                self.ledger.commit("egress:" + self.call_id, "call",
                                   {"completed_requests": self.completed, "last_status": status})

    def outcome(self) -> str:
        if self.refused:
            return "PARTIAL" if self.admitted else "REFUSED"
        if self._pending or self.completed < len(self.contract.patterns):
            return "INCOMPLETE"
        return "ADMITTED"

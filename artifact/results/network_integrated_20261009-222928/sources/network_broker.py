"""Trusted pre-send mediation for exact HTTP requests.

An untrusted server may propose a request, but this broker performs the send.
The caller must separately deny the server direct network access. Without that
outer boundary, this module protects only brokered sends and is not a complete
network confinement claim.
"""

from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import socket
import ssl
import threading
import uuid
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping
from urllib.parse import unquote, urlsplit

from .allowance import AllowanceError, AllowanceLedger, SlotState


_FORBIDDEN_HEADERS = {
    "connection", "content-length", "host", "proxy-authorization",
    "proxy-connection", "te", "trailer", "transfer-encoding", "upgrade",
}
_HEADER_NAME = re.compile(r"^[!#$%&'*+\-.^_`|~0-9a-z]+$")
_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")


def _canonical_host(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("host must be a non-empty string without whitespace")
    host = value[:-1] if value.endswith(".") else value
    try:
        return host.encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise ValueError(f"host is not valid IDNA: {error}") from error


def _canonical_target(value: str) -> str:
    if not isinstance(value, str) or not value.startswith("/"):
        raise ValueError("target must be an HTTP origin-form path beginning with /")
    if any(ord(character) < 0x20 or character in "\\#" for character in value):
        raise ValueError("target contains a control character, backslash, or fragment")
    if _PERCENT_ESCAPE.search(value):
        raise ValueError("target contains an invalid percent escape")
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        raise ValueError("target must not contain a scheme, authority, or fragment")
    decoded_segments = unquote(parsed.path).split("/")
    if any(
        "\\" in segment or any(ord(character) < 0x20 for character in segment)
        for segment in decoded_segments
    ):
        raise ValueError("decoded target contains a control character or backslash")
    if any(segment in (".", "..") for segment in decoded_segments):
        raise ValueError("target contains a dot path segment")
    return value


def _canonical_headers(headers: Mapping[str, str]) -> Mapping[str, str]:
    normalized: dict[str, str] = {}
    for raw_name, raw_value in headers.items():
        if not isinstance(raw_name, str) or not isinstance(raw_value, str):
            raise TypeError("HTTP header names and values must be strings")
        name = raw_name.strip().lower()
        if not name or not _HEADER_NAME.fullmatch(name) or name in _FORBIDDEN_HEADERS:
            raise ValueError(f"header is broker-controlled or invalid: {raw_name!r}")
        if name in normalized:
            raise ValueError(f"duplicate HTTP header after normalization: {name}")
        if any(ord(character) < 0x20 and character != "\t" for character in raw_value):
            raise ValueError(f"header {name!r} contains a control character")
        normalized[name] = raw_value.strip()
    return MappingProxyType(dict(sorted(normalized.items())))


def _body_bytes(value: bytes | str) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    raise TypeError("HTTP body must be bytes or text")


@dataclass(frozen=True)
class HTTPRequestProposal:
    scheme: str
    host: str
    port: int
    method: str
    target: str
    headers: Mapping[str, str]
    body: bytes | str


@dataclass(frozen=True)
class HTTPRequestContract:
    """An exact request plus trusted resolution and response limits."""

    scheme: str
    host: str
    port: int
    method: str
    target: str
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes | str = b""
    allowed_ip_cidrs: tuple[str, ...] = ()
    allow_private_addresses: bool = False
    timeout_seconds: float = 10.0
    max_response_bytes: int = 1_048_576
    max_requests: int = 1
    contract_id: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        scheme = self.scheme.lower()
        if scheme not in {"http", "https"}:
            raise ValueError("scheme must be http or https")
        host = _canonical_host(self.host)
        if not isinstance(self.port, int) or not 1 <= self.port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        method = self.method.upper()
        if not method.isascii() or not method.isalpha():
            raise ValueError("method must contain ASCII letters only")
        target = _canonical_target(self.target)
        headers = _canonical_headers(self.headers)
        body = _body_bytes(self.body)
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_response_bytes < 0:
            raise ValueError("max_response_bytes must be non-negative")
        if self.max_requests <= 0:
            raise ValueError("max_requests must be positive")
        networks = tuple(
            str(ipaddress.ip_network(value, strict=False))
            for value in self.allowed_ip_cidrs
        )
        object.__setattr__(self, "scheme", scheme)
        object.__setattr__(self, "host", host)
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "headers", headers)
        object.__setattr__(self, "body", body)
        object.__setattr__(self, "allowed_ip_cidrs", networks)
        canonical = json.dumps(
            {
                "scheme": scheme,
                "host": host,
                "port": self.port,
                "method": method,
                "target": target,
                "headers": dict(headers),
                "body_sha256": hashlib.sha256(body).hexdigest(),
                "body_length": len(body),
                "allowed_ip_cidrs": networks,
                "allow_private_addresses": self.allow_private_addresses,
                "timeout_seconds": self.timeout_seconds,
                "max_response_bytes": self.max_response_bytes,
                "max_requests": self.max_requests,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        object.__setattr__(
            self, "contract_id", hashlib.sha256(canonical.encode()).hexdigest()
        )

    def check(self, proposal: HTTPRequestProposal) -> tuple[bool, str]:
        try:
            observed = {
                "scheme": proposal.scheme.lower(),
                "host": _canonical_host(proposal.host),
                "port": proposal.port,
                "method": proposal.method.upper(),
                "target": _canonical_target(proposal.target),
                "headers": dict(_canonical_headers(proposal.headers)),
                "body": _body_bytes(proposal.body),
            }
        except (TypeError, ValueError) as error:
            return False, f"invalid request proposal: {error}"
        expected = {
            "scheme": self.scheme,
            "host": self.host,
            "port": self.port,
            "method": self.method,
            "target": self.target,
            "headers": dict(self.headers),
            "body": self.body,
        }
        for name in expected:
            if observed[name] != expected[name]:
                return False, f"request field {name} differs from the contract"
        return True, "request exactly matches the contract"


@dataclass(frozen=True)
class HTTPBrokerResult:
    request_id: str
    contract_id: str
    pinned_ip: str
    status: int
    response_headers: Mapping[str, str]
    response_body: bytes


@dataclass(frozen=True)
class HTTPBrokerRecord:
    request_id: str
    contract_id: str
    decision: str
    phase: str
    reason: str
    pinned_ip: str | None = None


class HTTPBrokerRefused(PermissionError):
    def __init__(self, record: HTTPBrokerRecord):
        self.record = record
        super().__init__(f"{record.decision} during {record.phase}: {record.reason}")


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, pinned_ip: str, timeout: float):
        super().__init__(host, port, timeout=timeout)
        self._pinned_ip = pinned_ip

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout, self.source_address
        )


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, pinned_ip: str, timeout: float):
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())
        self._pinned_ip = pinned_ip

    def connect(self) -> None:
        raw = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout, self.source_address
        )
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


def _default_resolver(host: str, port: int) -> list[str]:
    values = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({str(item[4][0]) for item in values})


def _default_transport(
    contract: HTTPRequestContract, pinned_ip: str
) -> tuple[int, Mapping[str, str], bytes]:
    connection_type = (
        _PinnedHTTPSConnection if contract.scheme == "https" else _PinnedHTTPConnection
    )
    connection = connection_type(
        contract.host, contract.port, pinned_ip, contract.timeout_seconds
    )
    headers = dict(contract.headers)
    default_port = 443 if contract.scheme == "https" else 80
    headers["Host"] = (
        contract.host if contract.port == default_port
        else f"{contract.host}:{contract.port}"
    )
    headers["Content-Length"] = str(len(contract.body))
    headers["Connection"] = "close"
    try:
        connection.request(
            contract.method, contract.target, body=contract.body,
            headers=headers, encode_chunked=False,
        )
        response = connection.getresponse()
        body = response.read(contract.max_response_bytes + 1)
        response_headers = {
            name.lower(): value for name, value in response.getheaders()
        }
        return response.status, response_headers, body
    finally:
        connection.close()


@dataclass
class TrustedHTTPBroker:
    """Resolve once, pin one approved address, and perform an exact request."""

    allowance: AllowanceLedger = field(default_factory=AllowanceLedger)
    resolver: Callable[[str, int], list[str]] = _default_resolver
    transport: Callable[
        [HTTPRequestContract, str], tuple[int, Mapping[str, str], bytes]
    ] = _default_transport
    records: list[HTTPBrokerRecord] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @staticmethod
    def _address_allowed(address: ipaddress.IPv4Address | ipaddress.IPv6Address,
                         contract: HTTPRequestContract) -> bool:
        if contract.allowed_ip_cidrs:
            return any(
                address in ipaddress.ip_network(network)
                for network in contract.allowed_ip_cidrs
            )
        if contract.allow_private_addresses:
            return not (address.is_multicast or address.is_unspecified)
        return not (
            address.is_private or address.is_loopback or address.is_link_local
            or address.is_multicast or address.is_reserved or address.is_unspecified
        )

    def _refuse(self, rid: str, contract: HTTPRequestContract,
                phase: str, reason: str) -> None:
        record = HTTPBrokerRecord(
            rid, contract.contract_id, "REFUSED", phase, reason
        )
        self.records.append(record)
        raise HTTPBrokerRefused(record)

    def send(
        self,
        proposal: HTTPRequestProposal,
        *,
        contract: HTTPRequestContract,
        request_id: str | None = None,
    ) -> HTTPBrokerResult:
        rid = request_id or uuid.uuid4().hex
        allowed, reason = contract.check(proposal)
        if not allowed:
            self._refuse(rid, contract, "request-shape", reason)

        with self._lock:
            prior = self.allowance.lookup(contract.contract_id, rid)
            if prior is not None:
                if prior.state is SlotState.COMMITTED and isinstance(
                    prior.result, HTTPBrokerResult
                ):
                    return prior.result
                if prior.state is SlotState.COMMITTED and isinstance(prior.result, Mapping):
                    return HTTPBrokerResult(**dict(prior.result))
                raise AllowanceError(
                    f"request {rid} cannot send again because its state is "
                    f"{prior.state.value}"
                )

            raw_addresses = self.resolver(contract.host, contract.port)
            if not raw_addresses:
                self._refuse(rid, contract, "dns", "trusted resolver returned no address")
            try:
                addresses = sorted(
                    {ipaddress.ip_address(value) for value in raw_addresses},
                    key=lambda value: (value.version, value.packed),
                )
            except ValueError as error:
                self._refuse(rid, contract, "dns", f"resolver returned invalid IP: {error}")
            forbidden = [
                str(address) for address in addresses
                if not self._address_allowed(address, contract)
            ]
            if forbidden:
                self._refuse(
                    rid, contract, "dns",
                    f"resolution contains an address outside policy: {forbidden}",
                )
            pinned_ip = str(addresses[0])
            prior = self.allowance.reserve(
                contract.contract_id, rid, contract.max_requests
            )
            if prior is not None:
                raise AllowanceError("request state changed while broker lock was held")
            try:
                status, headers, body = self.transport(contract, pinned_ip)
                body = bytes(body)
                if len(body) > contract.max_response_bytes:
                    raise ValueError(
                        f"response exceeds {contract.max_response_bytes} byte limit"
                    )
                result = HTTPBrokerResult(
                    request_id=rid,
                    contract_id=contract.contract_id,
                    pinned_ip=pinned_ip,
                    status=int(status),
                    response_headers=MappingProxyType(dict(headers)),
                    response_body=body,
                )
                self.allowance.commit(contract.contract_id, rid, result)
                self.records.append(
                    HTTPBrokerRecord(
                        rid, contract.contract_id, "SENT", "complete",
                        "exact request sent through the trusted pinned transport",
                        pinned_ip,
                    )
                )
                return result
            except BaseException as error:
                self.allowance.fail(
                    contract.contract_id, rid, f"{type(error).__name__}: {error}"
                )
                self.records.append(
                    HTTPBrokerRecord(
                        rid, contract.contract_id, "UNKNOWN", "transport",
                        "send may have occurred before transport failure: "
                        f"{type(error).__name__}: {error}", pinned_ip,
                    )
                )
                raise

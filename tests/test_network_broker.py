from __future__ import annotations

from pathlib import Path

import pytest

from mcpgate import (AllowanceError, HTTPBrokerRefused, HTTPRequestContract,
                     HTTPRequestProposal, SQLiteAllowanceLedger,
                     TrustedHTTPBroker)


def _contract(**changes):
    values = {
        "scheme": "https",
        "host": "api.example.test",
        "port": 443,
        "method": "POST",
        "target": "/v1/items?mode=strict",
        "headers": {"authorization": "Bearer fixed", "content-type": "application/json"},
        "body": b'{"value":"approved"}',
        "allowed_ip_cidrs": ("203.0.113.0/24",),
        "max_response_bytes": 64,
    }
    values.update(changes)
    return HTTPRequestContract(**values)


def _proposal(contract: HTTPRequestContract, **changes):
    values = {
        "scheme": contract.scheme,
        "host": contract.host,
        "port": contract.port,
        "method": contract.method,
        "target": contract.target,
        "headers": dict(contract.headers),
        "body": contract.body,
    }
    values.update(changes)
    return HTTPRequestProposal(**values)


@pytest.mark.parametrize(
    "change",
    [
        {"host": "attacker.example.test"},
        {"method": "PUT"},
        {"target": "/v1/admin"},
        {"headers": {"authorization": "Bearer attacker"}},
        {"body": b'{"value":"attacker"}'},
    ],
)
def test_request_substitution_is_refused_before_dns(change) -> None:
    contract = _contract()
    resolved = False

    def resolver(_host, _port):
        nonlocal resolved
        resolved = True
        return ["203.0.113.8"]

    broker = TrustedHTTPBroker(resolver=resolver)
    with pytest.raises(HTTPBrokerRefused) as caught:
        broker.send(_proposal(contract, **change), contract=contract)
    assert caught.value.record.phase == "request-shape"
    assert not resolved


def test_private_or_mixed_resolution_is_refused_without_send() -> None:
    contract = _contract(allowed_ip_cidrs=())
    sent = False

    def transport(_contract, _address):
        nonlocal sent
        sent = True
        return 200, {}, b"ok"

    broker = TrustedHTTPBroker(
        resolver=lambda _host, _port: ["93.184.216.34", "127.0.0.1"],
        transport=transport,
    )
    with pytest.raises(HTTPBrokerRefused) as caught:
        broker.send(_proposal(contract), contract=contract)
    assert caught.value.record.phase == "dns"
    assert not sent


def test_resolution_is_pinned_and_exact_request_is_sent_once() -> None:
    contract = _contract(max_requests=1)
    calls = []

    def resolver(host, port):
        calls.append(("resolve", host, port))
        return ["203.0.113.20", "203.0.113.10"]

    def transport(observed, address):
        calls.append(("send", observed.contract_id, address))
        return 201, {"content-type": "application/json"}, b'{"ok":true}'

    broker = TrustedHTTPBroker(resolver=resolver, transport=transport)
    first = broker.send(
        _proposal(contract), contract=contract, request_id="same-request"
    )
    second = broker.send(
        _proposal(contract), contract=contract, request_id="same-request"
    )
    assert first == second
    assert first.pinned_ip == "203.0.113.10"
    assert calls == [
        ("resolve", "api.example.test", 443),
        ("send", contract.contract_id, "203.0.113.10"),
    ]


def test_second_request_identity_exhausts_allowance() -> None:
    contract = _contract(max_requests=1)
    broker = TrustedHTTPBroker(
        resolver=lambda _host, _port: ["203.0.113.8"],
        transport=lambda _contract, _address: (200, {}, b"ok"),
    )
    broker.send(_proposal(contract), contract=contract, request_id="first")
    with pytest.raises(AllowanceError):
        broker.send(_proposal(contract), contract=contract, request_id="second")


def test_oversized_response_is_unknown_not_prevented() -> None:
    contract = _contract(max_response_bytes=2)
    broker = TrustedHTTPBroker(
        resolver=lambda _host, _port: ["203.0.113.8"],
        transport=lambda _contract, _address: (200, {}, b"three"),
    )
    with pytest.raises(ValueError):
        broker.send(_proposal(contract), contract=contract, request_id="large")
    assert broker.records[-1].decision == "UNKNOWN"
    assert broker.records[-1].phase == "transport"


def test_durable_replay_returns_recorded_result(tmp_path: Path) -> None:
    contract = _contract()
    ledger_path = tmp_path / "allowance.sqlite"
    first_broker = TrustedHTTPBroker(
        allowance=SQLiteAllowanceLedger(ledger_path),
        resolver=lambda _host, _port: ["203.0.113.8"],
        transport=lambda _contract, _address: (200, {"x-test": "yes"}, b"ok"),
    )
    first = first_broker.send(
        _proposal(contract), contract=contract, request_id="durable"
    )

    entered = False

    def should_not_send(_contract, _address):
        nonlocal entered
        entered = True
        return 500, {}, b"bad"

    second_broker = TrustedHTTPBroker(
        allowance=SQLiteAllowanceLedger(ledger_path),
        resolver=lambda _host, _port: ["203.0.113.9"],
        transport=should_not_send,
    )
    replay = second_broker.send(
        _proposal(contract), contract=contract, request_id="durable"
    )
    assert replay.request_id == first.request_id
    assert replay.response_body == b"ok"
    assert not entered


def test_contract_rejects_redirect_or_proxy_control_headers() -> None:
    with pytest.raises(ValueError):
        _contract(headers={"host": "attacker.example.test"})
    with pytest.raises(ValueError):
        _contract(target="https://attacker.example.test/")
    with pytest.raises(ValueError):
        _contract(target="/safe/%2e%2e/admin")
    with pytest.raises(ValueError):
        _contract(target="/safe/%5cadmin")
    with pytest.raises(ValueError):
        _contract(target="/bad/%zz")
    with pytest.raises(ValueError):
        _contract(headers={"bad:name": "value"})

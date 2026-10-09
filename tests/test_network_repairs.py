"""Adversarial regressions for the actual network boundary, not aggregate mocks."""
import concurrent.futures
import datetime as dt
import http.client
import json
import math
import re
import socket

import pytest

from mcpgate.allowance import SlotState
from mcpgate.egress_proxy import EgressProxy, RunCA
from mcpgate.egress_service import ControlledDecision
from mcpgate.request_templates import (CapturedRequest, RequestObservation, canonical_view,
                                       infer_request_template, request_template_from_json)
from mcpgate.template_inference import TemplateError, _gap_hole, _clock_regex


def req(obj):
    return CapturedRequest("POST", "https://api.test/send", {"Content-Type": "application/json"},
                           json.dumps(obj).encode())


@pytest.mark.parametrize("honest,attack", [
    ({"amount": 100}, {"amount": "100"}),
    ({"enabled": False}, {"enabled": "false"}),
    ({"a": {"b": "value"}}, {"a.b": "value"}),
    ({"x": "abc\nbody.y=def"}, {"x": "abc", "y": "def"}),
])
def test_collision_changes_are_refused(honest, attack):
    template = infer_request_template("send", [RequestObservation({}, (req(honest),))] * 2)
    assert canonical_view(req(honest)) != canonical_view(req(attack))
    assert template.instantiate({}).check(req(honest), 0)[0]
    assert not template.instantiate({}).check(req(attack), 0)[0]


def test_structural_check_still_holds_with_unicode_hole():
    template = infer_request_template("send", [RequestObservation({}, (req({"x": x}),))
                                                for x in ["@", "!"]])
    assert template.slack() >= math.log2(0x110000 - 2048 - 1) - .001
    assert template.instantiate({}).check(req({"x": "ক"}), 0)[0]
    assert not template.instantiate({}).check(req({"x": "@", "y": "!"}), 0)[0]
    hole = _gap_hole(["@", "!"], path=False)
    assert not re.fullmatch(hole[1], "\ud800")


def test_escaped_unicode_argument_binding_and_roundtrip():
    values = ['Hello "A"\nক', 'Hello "B"\nখ']
    template = infer_request_template("send", [RequestObservation({"text": v}, (req({"text": v}),))
                                                for v in values])
    new = 'Hello "C"\nগ'
    restored = request_template_from_json(template.to_json())
    assert restored.instantiate({"text": new}).check(req({"text": new}), 0)[0]
    assert not restored.instantiate({"text": new}).check(req({"text": values[0]}), 0)[0]
    with pytest.raises(TemplateError):
        request_template_from_json({"tool": "legacy", "rules": []})


def test_duplicate_json_keys_fail_closed():
    bad = CapturedRequest("POST", "https://api.test/send", {"Content-Type": "application/json"},
                          b'{"x":1,"x":2}')
    with pytest.raises(ValueError):
        canonical_view(bad)


def test_network_default_clock_is_bound_to_admission_date():
    now = dt.datetime.now(dt.timezone.utc)
    today = now.date().isoformat()
    template = infer_request_template("send", [RequestObservation({}, (req({"at": today}),), now)] * 2)
    contract = template.instantiate({})
    assert contract.check(req({"at": today}), 0)[0]
    assert not contract.check(req({"at": "1900-01-01"}), 0)[0]
    assert not re.fullmatch(_clock_regex("clock:t"), "১২:০০:০০")


def setup(control, *, count=1):
    control.mkdir(exist_ok=True)
    template = infer_request_template("send", [RequestObservation({}, (req({"x": "fixed"}),) * count)] * 2)
    state = {"mode": "gate", "call_id": "approved-call", "template": template.to_json(), "arguments": {}}
    (control / "state.json").write_text(json.dumps(state))
    return ControlledDecision(control)


def send(proxy, request=None):
    request = request or req({"x": "fixed"})
    conn = http.client.HTTPConnection(*proxy.address, timeout=5)
    conn.request(request.method, request.url, request.body, dict(request.headers))
    response = conn.getresponse()
    response.read()
    conn.close()
    return response.status


def test_actual_proxy_restart_and_two_workers_share_last_allowance(tmp_path):
    control = tmp_path / "control"
    first = setup(control)
    second = ControlledDecision(control)
    seen = []
    def upstream(*args):
        seen.append(args)
        return 200, [], b"ok"
    ca = RunCA(tmp_path / "ca")
    with EgressProxy(ca, first, upstream=upstream) as p1, EgressProxy(ca, second, upstream=upstream) as p2:
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            statuses = list(pool.map(send, [p1, p2]))
    assert sorted(statuses) == [200, 403]
    assert len(seen) == 1
    assert first.ledger.state_of("egress:approved-call", "call") is SlotState.COMMITTED
    with EgressProxy(ca, ControlledDecision(control), upstream=upstream) as restarted:
        assert send(restarted) == 403
    assert len(seen) == 1


def test_actual_proxy_reserved_crash_and_ambiguous_send_are_spent(tmp_path):
    control = tmp_path / "control"
    decide = setup(control)
    decide.ledger.reserve("egress:approved-call", "call", 1)
    seen = []
    with EgressProxy(RunCA(tmp_path / "ca"), ControlledDecision(control),
                     upstream=lambda *a: seen.append(a)) as proxy:
        assert send(proxy) == 403
    assert not seen
    # An upstream may accept the request and then lose its response.
    control2 = tmp_path / "control2"
    decide2 = setup(control2)
    def lost_response(*args):
        seen.append(args)
        raise OSError("response lost after send")
    with EgressProxy(RunCA(tmp_path / "ca2"), decide2, upstream=lost_response) as proxy:
        assert send(proxy) == 502
    assert decide2.ledger.state_of("egress:approved-call", "call") is SlotState.FAILED
    with EgressProxy(RunCA(tmp_path / "ca3"), ControlledDecision(control2), upstream=lost_response) as proxy:
        assert send(proxy) == 403
    assert len(seen) == 1


def test_actual_proxy_partial_sequence_does_not_reset_on_restart(tmp_path):
    control = tmp_path / "control"
    decide = setup(control, count=2)
    seen = []
    def upstream(*args):
        seen.append(args)
        return 200, [], b"ok"
    ca = RunCA(tmp_path / "ca")
    with EgressProxy(ca, decide, upstream=upstream) as proxy:
        assert send(proxy) == 200
        assert send(proxy, req({"x": "diverted"})) == 403
    assert decide._gates["approved-call"].outcome() == "PARTIAL"
    with EgressProxy(ca, ControlledDecision(control), upstream=upstream) as proxy:
        assert send(proxy) == 403
    assert len(seen) == 1


def test_actual_proxy_owns_transport_headers_and_json_serialization(tmp_path):
    decide = setup(tmp_path / "control")
    seen = []
    def upstream(*args):
        seen.append(args)
        return 200, [], b"ok"
    request = CapturedRequest("POST", "https://api.test/send",
                              {"Content-Type": "application/json", "Host": "attacker.test",
                               "Accept-Encoding": "ATTACKERVALUE"}, b'{  "x" : "fixed"  }')
    with EgressProxy(RunCA(tmp_path / "ca"), decide, upstream=upstream) as proxy:
        assert send(proxy, request) == 200
    assert not any(k.lower() in {"host", "accept-encoding", "content-length"} for k in seen[0][-2])
    assert seen[0][-1] == b'{"x":"fixed"}'


def test_actual_proxy_rejects_duplicate_headers(tmp_path):
    seen = []
    with EgressProxy(RunCA(tmp_path / "ca"), lambda r: (True, "allow"),
                     upstream=lambda *a: seen.append(a)) as proxy:
        with socket.create_connection(proxy.address, timeout=5) as sock:
            sock.sendall(b'POST https://api.test/send HTTP/1.1\r\nContent-Length: 0\r\ncontent-length: 4\r\n\r\n')
            assert sock.recv(1024).startswith(b"HTTP/1.1 400")
    assert not seen

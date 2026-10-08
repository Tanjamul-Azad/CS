"""Pin-time templates for outbound HTTP requests (network-effect admission).

A network send cannot be staged and discarded the way a file write can, so the
check runs before each request leaves the trusted broker. The contract for a
new call comes from the same pin-time idea as file effects: the approved
server version runs on perturbed arguments, its outbound requests are recorded
by the broker, and the requests are anti-unified into one template per tool.

Each request is reduced to a canonical text view, one field per line:

    METHOD https://host:port/path
    query.<name>=<value>          (sorted)
    header.<name>=<value>         (sorted; credential and transport headers dropped)
    body.<dotted.key>=<value>     (JSON bodies, flattened and sorted)
    body=<text>                   (any other body)

Argument values appear raw in this view (JSON escaping is undone), so the
existing argument abstraction and anti-unification apply unchanged. A field the
honest version never sent, such as an added ``Bcc`` recipient, is a line the
template does not contain, and the request is refused before it is sent.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, urlsplit

from .template_inference import (DEFAULT_ROOT, TemplateError, _clock_bits,
                                 _make_transforms, _renderings, _sources,
                                 abstract, anti_unify, flatten_arguments)

# Headers that never enter the view: the broker owns transport framing and
# injects credentials itself, so their values carry no server-chosen meaning.
TRANSPORT_HEADERS = frozenset({
    "connection", "content-length", "host", "proxy-authorization",
    "proxy-connection", "te", "trailer", "transfer-encoding", "upgrade",
    "keep-alive", "accept-encoding",
})


@dataclass(frozen=True)
class CapturedRequest:
    """One outbound request as the broker saw it, before any send."""

    method: str
    url: str  # absolute: scheme://host[:port]/path?query
    headers: Mapping[str, str]
    body: bytes = b""


def _default_port(scheme: str) -> int:
    return 443 if scheme == "https" else 80


def _flatten_json(value: Any, prefix: str, out: list[tuple[str, str]]) -> None:
    if isinstance(value, Mapping):
        if not value:
            out.append((prefix, "{}"))
        for key in sorted(value):
            _flatten_json(value[key], f"{prefix}.{key}", out)
    elif isinstance(value, list):
        if not value:
            out.append((prefix, "[]"))
        for index, item in enumerate(value):
            _flatten_json(item, f"{prefix}[{index}]", out)
    elif isinstance(value, str):
        out.append((prefix, value))
    else:
        out.append((prefix, json.dumps(value)))


def canonical_view(request: CapturedRequest, *,
                   credential_headers: frozenset[str] = frozenset()) -> str:
    """Deterministic text view of one request, used for both training and checking."""
    parts = urlsplit(request.url)
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"request URL must be absolute http(s): {request.url!r}")
    host = parts.hostname.lower()
    port = parts.port or _default_port(scheme)
    lines = [f"{request.method.upper()} {scheme}://{host}:{port}{parts.path or '/'}"]
    for name, value in sorted(parse_qsl(parts.query, keep_blank_values=True)):
        lines.append(f"query.{name}={value}")
    dropped = TRANSPORT_HEADERS | {h.lower() for h in credential_headers}
    for name, value in sorted((k.lower(), v) for k, v in request.headers.items()):
        if name not in dropped:
            lines.append(f"header.{name}={value}")
    body = request.body or b""
    if body:
        ctype = {k.lower(): v for k, v in request.headers.items()}.get("content-type", "")
        parsed: Any = None
        if "json" in ctype.lower():
            try:
                parsed = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                parsed = None
        if parsed is not None:
            flat: list[tuple[str, str]] = []
            _flatten_json(parsed, "body", flat)
            lines.extend(f"{k}={v}" for k, v in flat)
        else:
            try:
                lines.append("body=" + body.decode("utf-8"))
            except UnicodeDecodeError:
                lines.append("body.sha256=" + hashlib.sha256(body).hexdigest())
    return "\n".join(lines)


@dataclass(frozen=True)
class RequestObservation:
    """One honest training run: arguments and the requests the server sent."""

    arguments: Mapping[str, Any]
    requests: tuple[CapturedRequest, ...]
    clock_at: _dt.datetime | None = None


@dataclass(frozen=True)
class RequestRule:
    index: int
    tokens: tuple[tuple, ...]


@dataclass(frozen=True)
class RequestContract:
    """Instantiated contract for one call: an ordered list of request regexes."""

    tool: str
    patterns: tuple[str, ...]
    credential_headers: frozenset[str] = frozenset()

    def check(self, request: CapturedRequest, sent_so_far: int) -> tuple[bool, str]:
        """Decide one request before it is sent. ``sent_so_far`` counts the
        requests this call has already had admitted."""
        if sent_so_far >= len(self.patterns):
            return False, f"request {sent_so_far + 1} exceeds the {len(self.patterns)} the template allows"
        view = canonical_view(request, credential_headers=self.credential_headers)
        if re.fullmatch(self.patterns[sent_so_far], view):
            return True, "matches template"
        return False, "request differs from the pinned template"


@dataclass(frozen=True)
class RequestTemplate:
    tool: str
    rules: tuple[RequestRule, ...]
    fixed: Mapping[str, Any] = field(default_factory=dict)
    credential_headers: frozenset[str] = frozenset()
    training_runs: int = 0

    def _render(self, tokens: Sequence[tuple], values: Mapping[str, Any],
                now=None) -> str:
        from .template_inference import _clock_regex
        transforms = _make_transforms(DEFAULT_ROOT)
        out: list[str] = []
        for token in tokens:
            if token[0] == "L":
                out.append(re.escape(token[1]))
            elif token[0] == "A":
                name = token[1]
                if not isinstance(values.get(name), str):
                    raise TemplateError(f"call lacks string argument {name!r}")
                forms = _renderings(token, values[name], transforms)
                if not forms:
                    raise TemplateError(f"argument {name!r} has no {token[2]} form")
                out.append("(?:" + "|".join(re.escape(f) for f in forms) + ")")
            elif token[1].startswith("clock:"):
                out.append(_clock_regex(token[1], now))
            else:
                out.append(token[1])
        return "".join(out)

    def instantiate(self, arguments: Mapping[str, Any], *, now=None) -> RequestContract:
        values = flatten_arguments(arguments)
        for name, expected in self.fixed.items():
            if values.get(name) != expected:
                raise TemplateError(f"field {name!r} is {values.get(name)!r}; "
                                    f"the template was trained only for {expected!r}")
        return RequestContract(
            tool=self.tool,
            patterns=tuple(self._render(r.tokens, values, now) for r in self.rules),
            credential_headers=self.credential_headers)

    def slack(self, *, clock_bound: bool = True) -> float:
        bits = 0.0
        for rule in self.rules:
            for t in rule.tokens:
                if t[0] == "H":
                    bits += _clock_bits(t[1], clock_bound) if t[1].startswith("clock:") else t[2]
                elif t[0] == "A" and "+" in t[2]:
                    bits += math.log2(len(t[2].split("+")))
        return bits

    def to_json(self) -> dict:
        return {"tool": self.tool, "fixed": dict(self.fixed),
                "credential_headers": sorted(self.credential_headers),
                "training_runs": self.training_runs,
                "rules": [{"index": r.index, "tokens": [list(t[:3]) for t in r.tokens]}
                          for r in self.rules]}


def infer_request_template(tool: str, observations: Sequence[RequestObservation], *,
                           fixed: Mapping[str, Any] | None = None,
                           credential_headers: frozenset[str] = frozenset()
                           ) -> RequestTemplate:
    """Anti-unify the requests of several honest runs, aligned by position.

    Honest servers in scope send the same sequence of requests for every call
    of one tool. Runs that disagree on the number of requests, or on a
    request's method and host, have no single template; inference refuses
    rather than guessing, and the tool is reported as not covered."""
    if len(observations) < 2:
        raise TemplateError("request templates need at least two training runs")
    counts = {len(o.requests) for o in observations}
    if len(counts) != 1:
        raise TemplateError(f"training runs sent different request counts: {sorted(counts)}")
    (count,) = counts
    rules: list[RequestRule] = []
    for index in range(count):
        heads = {canonical_view(o.requests[index]).split("\n", 1)[0].split(" ", 1)[0]
                 + " " + urlsplit(o.requests[index].url).netloc.lower()
                 for o in observations}
        if len(heads) != 1:
            raise TemplateError(f"request {index} differs in method or host: {sorted(heads)}")
        runs = []
        for o in observations:
            view = canonical_view(o.requests[index], credential_headers=credential_headers)
            runs.append(abstract(view, _sources(o.arguments, DEFAULT_ROOT), o.clock_at))
        rules.append(RequestRule(index=index, tokens=tuple(anti_unify(runs))))
    return RequestTemplate(tool=tool, rules=tuple(rules), fixed=dict(fixed or {}),
                           credential_headers=frozenset(credential_headers),
                           training_runs=len(observations))


def request_template_from_json(data: Mapping[str, Any]) -> RequestTemplate:
    """Inverse of ``RequestTemplate.to_json``."""
    return RequestTemplate(
        tool=data["tool"],
        rules=tuple(RequestRule(index=r["index"], tokens=tuple(tuple(t) for t in r["tokens"]))
                    for r in data["rules"]),
        fixed=dict(data.get("fixed", {})),
        credential_headers=frozenset(data.get("credential_headers", ())),
        training_runs=int(data.get("training_runs", 0)))

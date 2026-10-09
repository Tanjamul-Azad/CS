"""Pin-time templates for outbound HTTP requests (network-effect admission).

A network send cannot be staged and discarded the way a file write can, so the
check runs before each request leaves the trusted broker. The contract for a
new call comes from the same pin-time idea as file effects: the approved
server version runs on perturbed arguments, its outbound requests are recorded
by the broker, and the requests are anti-unified into one template per tool.

Canonical fields use JSON-encoded names and typed values. Keys are path arrays;
leaves are inferred separately and structure is checked independently of holes.
JSON bodies are normalized before forwarding. Capacity describes this canonical
representation rather than excluded transport serialization.
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


FORMAT_VERSION = 2


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON key")
        obj[key] = value
    return obj


def _body_json(request):
    ctype = next((v for k, v in request.headers.items() if k.lower() == "content-type"), "")
    if request.body and "json" in ctype.lower():
        return True, json.loads(request.body.decode("utf-8"), object_pairs_hook=_unique_object,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON")))
    return False, None


def normalized_body(request):
    is_json, value = _body_json(request)
    return _json(value).encode("utf-8") if is_json else request.body


def _fields(request, credential_headers=frozenset()):
    parts = urlsplit(request.url)
    scheme = parts.scheme.lower()
    if (scheme not in ("http", "https") or not parts.hostname or parts.username is not None
            or parts.password is not None or parts.fragment or any(ord(c) < 32 for c in request.url)):
        raise ValueError("invalid absolute HTTP(S) URL")
    if not re.fullmatch(r"[A-Za-z]+", request.method):
        raise ValueError("invalid HTTP method")
    port = parts.port or _default_port(scheme)
    fields = [(('authority',), [request.method.upper(), scheme, parts.hostname.lower(), port], 'fixed'),
              (('path',), parts.path or '/', 'string')]
    for i, (key, value) in enumerate(parse_qsl(parts.query, keep_blank_values=True,
                                              encoding='utf-8', errors='strict')):
        fields.append((('query', i, key), value, 'string'))
    lowered = {}
    for name, value in request.headers.items():
        name = name.lower()
        if name in lowered:
            raise ValueError("duplicate HTTP header")
        if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9a-z-]+", name) or any(
                ord(c) < 32 and c != '\t' for c in value):
            raise ValueError("invalid HTTP header")
        lowered[name] = value
    dropped = TRANSPORT_HEADERS | {h.lower() for h in credential_headers}
    fields.extend((('header', k), v, 'string') for k, v in sorted(lowered.items()) if k not in dropped)
    is_json, value = _body_json(request)
    if is_json:
        def walk(obj, path):
            if isinstance(obj, dict):
                fields.append((('body', *path), sorted(obj), 'object'))
                for key in sorted(obj):
                    walk(obj[key], path + (key,))
            elif isinstance(obj, list):
                fields.append((('body', *path), len(obj), 'array'))
                for i, item in enumerate(obj):
                    walk(item, path + (i,))
            else:
                kind = ('null' if obj is None else 'boolean' if isinstance(obj, bool)
                        else 'number' if isinstance(obj, (int, float)) else 'string')
                fields.append((('body', *path), obj, kind))
        walk(value, ())
    elif request.body:
        fields.append((('body-bytes',), hashlib.sha256(request.body).hexdigest(), 'fixed'))
    return fields


def canonical_view(request, *, credential_headers=frozenset()):
    return "\n".join(_json([key, kind, value]) for key, value, kind in _fields(request, credential_headers))


def _structure(request, credential_headers):
    return _json([(key, kind, value if kind in ('object', 'array', 'fixed') else None)
                  for key, value, kind in _fields(request, credential_headers)])


def _request_transforms():
    return {'json_' + name: (lambda value, fn=fn: _json(fn(value))[1:-1])
            for name, fn in _make_transforms(DEFAULT_ROOT).items()}


def _request_sources(arguments):
    by_text = {}
    for name, value in sorted(flatten_arguments(arguments).items()):
        if not isinstance(value, str) or len(value) < 4:
            continue
        for tname, fn in _request_transforms().items():
            text = fn(value)
            if len(text) < 4:
                continue
            owner = by_text.setdefault(text, (name, []))
            if owner[0] == name:
                owner[1].append(tname)
    return sorted([(t, n, '+'.join(ts)) for t, (n, ts) in by_text.items()], key=lambda item: -len(item[0]))


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
    structure: str


@dataclass(frozen=True)
class RequestContract:
    """Instantiated contract for one call: an ordered list of request regexes."""

    tool: str
    patterns: tuple[str, ...]
    credential_headers: frozenset[str] = frozenset()
    structures: tuple[str, ...] = ()

    def check(self, request: CapturedRequest, sent_so_far: int) -> tuple[bool, str]:
        """Decide one request before it is sent. ``sent_so_far`` counts the
        requests this call has already had admitted."""
        if sent_so_far >= len(self.patterns):
            return False, f"request {sent_so_far + 1} exceeds the {len(self.patterns)} the template allows"
        try:
            if not self.structures or _structure(request, self.credential_headers) != self.structures[sent_so_far]:
                return False, "request structure differs from the pinned template"
            view = canonical_view(request, credential_headers=self.credential_headers)
        except (ValueError, UnicodeError):
            return False, "malformed request"
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
        transforms = _request_transforms()
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
        now = now or _dt.datetime.now(_dt.timezone.utc)
        values = flatten_arguments(arguments)
        for name, expected in self.fixed.items():
            if values.get(name) != expected:
                raise TemplateError(f"field {name!r} is {values.get(name)!r}; "
                                    f"the template was trained only for {expected!r}")
        return RequestContract(
            tool=self.tool,
            patterns=tuple(self._render(r.tokens, values, now) for r in self.rules),
            credential_headers=self.credential_headers,
            structures=tuple(r.structure for r in self.rules))

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
        return {"format_version": FORMAT_VERSION, "tool": self.tool, "fixed": dict(self.fixed),
                "credential_headers": sorted(self.credential_headers),
                "training_runs": self.training_runs,
                "rules": [{"index": r.index, "structure": r.structure, "tokens": [list(t[:3]) for t in r.tokens]}
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
        structures = {_structure(o.requests[index], credential_headers) for o in observations}
        if len(structures) != 1:
            raise TemplateError(f"request {index} has inconsistent structure or authority")
        lines = [canonical_view(o.requests[index], credential_headers=credential_headers).split("\n")
                 for o in observations]
        tokens = []
        for column in zip(*lines):
            if tokens:
                tokens.append(("L", "\n"))
            tokens.extend(anti_unify([abstract(line, _request_sources(o.arguments), o.clock_at)
                                     for line, o in zip(column, observations)]))
        rules.append(RequestRule(index, tuple(tokens), next(iter(structures))))
    return RequestTemplate(tool=tool, rules=tuple(rules), fixed=dict(fixed or {}),
                           credential_headers=frozenset(credential_headers),
                           training_runs=len(observations))


def request_template_from_json(data: Mapping[str, Any]) -> RequestTemplate:
    """Inverse of ``RequestTemplate.to_json``."""
    if data.get("format_version") != FORMAT_VERSION:
        raise TemplateError("legacy request template; repin using typed format v2")
    return RequestTemplate(
        tool=data["tool"],
        rules=tuple(RequestRule(index=r["index"], tokens=tuple(tuple(t) for t in r["tokens"]), structure=r["structure"])
                    for r in data["rules"]),
        fixed=dict(data.get("fixed", {})),
        credential_headers=frozenset(data.get("credential_headers", ())),
        training_runs=int(data.get("training_runs", 0)))

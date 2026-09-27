"""Effect-template inference: argument-parameterized contracts learned at pin time.

The fixed-call contracts used so far are derived from honest runs of the exact
call being admitted. At deployment the admitted call is new, so no honest run
of it exists, and if one did the client could simply use it. This module
instead runs the approved server version a few times on perturbed arguments, in
private copies, when the user pins that version, and infers one template per
tool: which objects change, how each path is built from the arguments, and how
each file's content is built from the arguments plus bounded volatile spans.
At call time the template is instantiated with the call's own arguments into an
ordinary ``TreeEffectContract``. This matches the rug-pull threat model: the
pinned version is the one the user approved, and a later replacement must
still produce effects that fit what that version would have produced.

The inference is anti-unification over argument-abstracted token sequences.
Each run's paths and contents are first rewritten so that every occurrence of
an argument value, under a small library of normalizing transforms, becomes a
placeholder, and every clock-derived date or timestamp becomes a typed hole.
Clock values are generalized even when they happen to be equal across the
training runs, because runs made within one session share a date that a later
call will not. Runs are then aligned against the first run; tokens present in
every run are kept, and every place where the runs disagree becomes a hole
whose character class and length bounds are the tightest consistent with what
was observed.

Contract slack is the number of bits an adversary can still choose while
conforming to an instantiated contract: the sum of hole capacities, plus the
choice of object count where it is free, and infinite for content left
unconstrained. It turns the L1/L2/L3 ladder into a measured quantity: zero bits
is L3, a finite positive number is L2, and unbounded is L1 (reported UNKNOWN).

Fields whose values select behavior rather than carry data (schema enums, or
fields whose perturbation made the honest server refuse the call) are held
fixed during training. A template only covers calls that use the same values
for those fields; any other call is refused rather than admitted on a guess.
"""

from __future__ import annotations

import datetime as _dt
import difflib
import hashlib
import json
import math
import posixpath
import random
import re
import string
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

from .contract import EffectContract
from .tree_mediator import ContentPredicate, PathRule, TreeEffectContract, TreeSnapshot

# An argument value shorter than this is not used as a substitution source; a
# short value such as "a" or "md" would match unrelated text everywhere.
MIN_SOURCE_LEN = 4

DEFAULT_ROOT = "/sandbox"


class TemplateError(ValueError):
    """The template cannot produce a contract for this call (fail closed)."""


# --------------------------------------------------------------------------
# Argument transforms. Order is priority: when two transforms of one value
# produce the same text, the earlier one names it.
# --------------------------------------------------------------------------

def _slug_dash(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _slug_drop(value: str) -> str:
    kept = re.sub(r"[^a-z0-9 -]+", "", value.lower()).strip()
    return re.sub(r" +", "-", kept)


def _make_transforms(root: str) -> dict[str, Callable[[str], str]]:
    prefix = root.rstrip("/") + "/"

    def relpath(value: str) -> str:
        return value[len(prefix):] if value.startswith(prefix) else ""

    return {
        "identity": lambda v: v,
        "relpath": relpath,
        "basename": lambda v: posixpath.basename(v) if "/" in v else "",
        "stem": lambda v: posixpath.splitext(posixpath.basename(v))[0],
        "lower": str.lower,
        "upper": str.upper,
        "slug_dash": _slug_dash,
        "slug_drop": _slug_drop,
    }


def flatten_arguments(arguments: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested arguments to dotted names; leaves keep their type."""
    out: dict[str, Any] = {}
    for key, value in arguments.items():
        name = f"{prefix}{key}"
        if isinstance(value, Mapping):
            out.update(flatten_arguments(value, name + "."))
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                if isinstance(item, Mapping):
                    out.update(flatten_arguments(item, f"{name}[{index}]."))
                else:
                    out[f"{name}[{index}]"] = item
        else:
            out[name] = value
    return out


def _sources(arguments: Mapping[str, Any], root: str) -> list[tuple[str, str, str]]:
    """(text, argument name, transform) triples, longest text first."""
    transforms = _make_transforms(root)
    seen: set[str] = set()
    out: list[tuple[str, str, str]] = []
    for name, value in sorted(flatten_arguments(arguments).items()):
        if not isinstance(value, str):
            continue
        for tname, fn in transforms.items():
            text = fn(value)
            if len(text) < MIN_SOURCE_LEN or text in seen:
                continue
            seen.add(text)
            out.append((text, name, tname))
    out.sort(key=lambda item: -len(item[0]))
    return out


# --------------------------------------------------------------------------
# Tokens. A token is a tuple:
#   ("L", text)                         literal
#   ("A", name, transform, observed)    argument placeholder
#   ("H", regex, bits, observed)        hole (volatile span)
# The alignment key drops the observed text so that two runs agree on a
# placeholder even though its value differs.
# --------------------------------------------------------------------------

_LITERAL_TOKEN = re.compile(r"[A-Za-z]+|[0-9]+|\s+|[^A-Za-z0-9\s]")

# Clock-derived values: a date, optionally followed by a time, a fraction, and
# a zone; or a bare time. The hole keeps the observed *shape* (separator and
# zone style) so that runs agree on it, while the fraction stays optional
# because some runtimes omit a zero fraction.
_CLOCK = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})"
    r"(?:(?P<sep>[T ])\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?P<tz>Z|[+-]\d{2}:?\d{2})?)?"
    r"|(?P<time>\d{2}:\d{2}:\d{2})(?:\.\d{1,9})?")
_TIME = r"\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?"
_TIME_BITS = 15 * math.log2(10) + 1  # six digits, up to nine fraction digits


def _key(token: tuple) -> tuple:
    if token[0] == "L":
        return token
    if token[0] == "A":
        return token[:3]
    return token[:2]


def _observed(token: tuple) -> str:
    return token[1] if token[0] == "L" else token[3]


def _clock_spec(match: re.Match) -> str:
    if match.group("time"):
        return "clock:t"
    if not match.group("sep"):
        return "clock:d"
    tz = match.group("tz")
    zone = "" if tz is None else ("Z" if tz == "Z" else "o")
    return f"clock:d{match.group('sep')}t{zone}"


def _clock_regex(spec: str, now=None) -> str:
    """Regex for a clock hole; with ``now``, the date is bound to the
    admission clock (UTC yesterday, today, or tomorrow)."""
    shape = spec.split(":", 1)[1]
    if shape == "t":
        return _TIME
    if now is None:
        date = r"\d{4}-\d{2}-\d{2}"
    else:
        day = now.astimezone(_dt.timezone.utc).date()
        days = sorted({(day + _dt.timedelta(days=d)).isoformat() for d in (-1, 0, 1)})
        date = "(?:" + "|".join(re.escape(d) for d in days) + ")"
    if shape == "d":
        return date
    sep, zone = shape[1], shape[3:]
    tz = {"": "", "Z": "Z", "o": r"[+-]\d{2}:?\d{2}"}[zone]
    return f"{date}{re.escape(sep)}{_TIME}{tz}"


def _clock_bits(spec: str, bound: bool) -> float:
    shape = spec.split(":", 1)[1]
    if shape == "t":
        return round(_TIME_BITS, 3)
    bits = math.log2(3) if bound else 8 * math.log2(10)
    if shape != "d":
        bits += _TIME_BITS
        if shape.endswith("o"):
            bits += 4 * math.log2(10) + 2
    return round(bits, 3)


def _literal_tokens(text: str) -> list[tuple]:
    tokens: list[tuple] = []
    position = 0
    for match in _CLOCK.finditer(text):
        tokens.extend(("L", t) for t in _LITERAL_TOKEN.findall(text[position:match.start()]))
        spec = _clock_spec(match)
        tokens.append(("H", spec, _clock_bits(spec, False), match.group(0)))
        position = match.end()
    tokens.extend(("L", t) for t in _LITERAL_TOKEN.findall(text[position:]))
    return tokens


def abstract(text: str, sources: Sequence[tuple[str, str, str]]) -> list[tuple]:
    """Rewrite argument occurrences as placeholders, clock values as holes."""
    taken: list[tuple[int, int, str, str]] = []
    for src, name, tname in sources:  # longest first
        start = text.find(src)
        while start != -1:
            end = start + len(src)
            if all(end <= s or start >= e for s, e, _, _ in taken):
                taken.append((start, end, name, tname))
            start = text.find(src, start + 1)
    taken.sort()
    tokens: list[tuple] = []
    position = 0
    for start, end, name, tname in taken:
        tokens.extend(_literal_tokens(text[position:start]))
        tokens.append(("A", name, tname, text[start:end]))
        position = end
    tokens.extend(_literal_tokens(text[position:]))
    return tokens


# --------------------------------------------------------------------------
# Holes from disagreeing gaps.
# --------------------------------------------------------------------------

# (regex class, alphabet size, membership test). Tightest first.
_CLASSES: tuple[tuple[str, int, Callable[[str], bool]], ...] = (
    ("[0-9]", 10, lambda c: c in string.digits),
    ("[0-9a-f]", 16, lambda c: c in "0123456789abcdef"),
    ("[0-9a-z]", 36, lambda c: c in string.digits + string.ascii_lowercase),
    ("[0-9A-Za-z]", 62, lambda c: c in string.digits + string.ascii_letters),
    ("[0-9A-Za-z_-]", 64, lambda c: c in string.digits + string.ascii_letters + "_-"),
    ("[0-9A-Za-z_. -]", 66, lambda c: c in string.digits + string.ascii_letters + "_. -"),
)


def _log2_sum_powers(base: int, low: int, high: int) -> float:
    """log2(sum_{L=low..high} base**L), stable for large exponents."""
    if high <= 0:
        return 0.0
    if base <= 1:
        return math.log2(high - low + 1)
    tail = sum(base ** (-k) for k in range(0, min(high - low, 60) + 1))
    return high * math.log2(base) + math.log2(tail)


def _gap_hole(texts: Sequence[str], *, path: bool) -> tuple:
    chars = set("".join(texts))
    regex_class, size = None, 0
    for cls, alphabet, member in _CLASSES:
        if all(member(c) for c in chars):
            regex_class, size = cls, alphabet
            break
    if regex_class is None:
        if path:
            regex_class, size = "[^/\\n]", 95
        elif "\n" not in chars:
            regex_class, size = "[^\\n]", 95
        else:
            regex_class, size = "[\\s\\S]", 256
    lengths = [len(t) for t in texts]
    low, high = min(lengths), max(lengths)
    if low != high:
        high = 2 * high  # observed lengths vary: allow growth, bounded
    regex = f"(?:{regex_class}){{{low},{high}}}"
    bits = round(_log2_sum_powers(size, low, high), 3)
    return ("H", regex, bits, "|".join(texts))


def anti_unify(runs: Sequence[Sequence[tuple]], *, path: bool = False) -> list[tuple]:
    """Generalize several abstracted token sequences into one template.

    Star alignment against the first run: a token of run 0 is an anchor when
    every other run matches it (difflib matching blocks are monotonic, so the
    anchors appear in the same order in every run). Between consecutive
    anchors each run has a gap; identical gaps are kept verbatim and
    disagreeing gaps become one bounded hole.
    """
    if not runs:
        raise ValueError("anti_unify needs at least one run")
    base = list(runs[0])
    base_keys = [_key(t) for t in base]
    maps: list[dict[int, int]] = []
    for run in runs[1:]:
        matcher = difflib.SequenceMatcher(None, base_keys, [_key(t) for t in run],
                                          autojunk=False)
        mapping: dict[int, int] = {}
        for a, b, size in matcher.get_matching_blocks():
            for offset in range(size):
                mapping[a + offset] = b + offset
        maps.append(mapping)
    anchors = [i for i in range(len(base)) if all(i in m for m in maps)]
    template: list[tuple] = []

    def emit_gap(prev: int, nxt: int) -> None:
        gaps = [base[prev + 1:nxt]]
        for run, mapping in zip(runs[1:], maps):
            lo = mapping[prev] + 1 if prev >= 0 else 0
            hi = mapping[nxt] if nxt < len(base) else len(run)
            gaps.append(list(run[lo:hi]))
        if all([_key(t) for t in g] == [_key(t) for t in gaps[0]] for g in gaps):
            template.extend(_strip(t) for t in gaps[0])
            return
        texts = ["".join(_observed(t) for t in g) for g in gaps]
        template.append(_gap_hole(texts, path=path))

    previous = -1
    for index in anchors:
        emit_gap(previous, index)
        template.append(_strip(base[index]))
        previous = index
    emit_gap(previous, len(base))
    return _merge_literals(template)


def _strip(token: tuple) -> tuple:
    if token[0] == "A":
        return token[:3]
    if token[0] == "H":
        return token[:3]
    return token


def _merge_literals(tokens: Iterable[tuple]) -> list[tuple]:
    out: list[tuple] = []
    for token in tokens:
        if token[0] == "L" and out and out[-1][0] == "L":
            out[-1] = ("L", out[-1][1] + token[1])
        elif token[0] == "L" and token[1] == "":
            continue
        else:
            out.append(token)
    return out


# --------------------------------------------------------------------------
# Templates.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Observation:
    """One honest training run: the arguments and the changed tree.

    ``entries`` maps a root-relative path to (kind, content bytes or None).
    """

    arguments: Mapping[str, Any]
    entries: Mapping[str, tuple[str, bytes | None]]


@dataclass(frozen=True)
class ObjectTemplate:
    name: str
    kind: str
    path: tuple[tuple, ...] | None
    path_regex: str | None = None  # fallback when the path could not be aligned
    min_count: int = 1
    max_count: int = 1
    content: tuple[tuple, ...] | None = None
    content_sha256: str | None = None
    unconstrained: bool = False

    def to_json(self) -> dict:
        return {
            "name": self.name, "kind": self.kind,
            "path": [list(t) for t in self.path] if self.path is not None else None,
            "path_regex": self.path_regex,
            "min_count": self.min_count, "max_count": self.max_count,
            "content": [list(t) for t in self.content] if self.content is not None else None,
            "content_sha256": self.content_sha256,
            "unconstrained": self.unconstrained,
        }


@dataclass(frozen=True)
class SlackReport:
    total_bits: float
    per_rule: Mapping[str, float]

    @property
    def level(self) -> str:
        if math.isinf(self.total_bits):
            return "L1"
        return "L3" if self.total_bits == 0 else "L2"


@dataclass(frozen=True)
class EffectTemplate:
    tool: str
    root: str
    objects: tuple[ObjectTemplate, ...]
    fixed: Mapping[str, Any] = field(default_factory=dict)
    training_runs: int = 0

    # -- instantiation ----------------------------------------------------

    def _render(self, tokens: Sequence[tuple], values: Mapping[str, Any],
                now=None) -> str:
        transforms = _make_transforms(self.root)
        parts: list[str] = []
        for token in tokens:
            if token[0] == "L":
                parts.append(re.escape(token[1]))
            elif token[0] == "A":
                name, tname = token[1], token[2]
                if name not in values or not isinstance(values[name], str):
                    raise TemplateError(f"call lacks string argument {name!r}")
                rendered = transforms[tname](values[name])
                if not rendered:
                    raise TemplateError(
                        f"argument {name!r} has no {tname} form for this call")
                parts.append(re.escape(rendered))
            elif token[1].startswith("clock:"):
                parts.append(_clock_regex(token[1], now))
            else:
                parts.append(token[1])
        return "".join(parts)

    def _check_fixed(self, values: Mapping[str, Any]) -> None:
        for name, expected in self.fixed.items():
            if values.get(name) != expected:
                raise TemplateError(
                    f"field {name!r} is {values.get(name)!r}; the template was "
                    f"trained only for {expected!r}")

    def instantiate(self, arguments: Mapping[str, Any],
                    expected_before: TreeSnapshot | None = None, *,
                    now=None) -> TreeEffectContract:
        """Contract for one call. With ``now`` (an aware datetime), clock
        holes are bound to the admission date; without it, any date passes."""
        values = flatten_arguments(arguments)
        self._check_fixed(values)
        rules: list[PathRule] = []
        for obj in self.objects:
            pattern = (self._render(obj.path, values, now) if obj.path is not None
                       else obj.path_regex)
            if obj.kind == "directory":
                rules.append(PathRule(
                    name=obj.name, pattern=pattern, kinds=frozenset({"directory"}),
                    operations=frozenset({"create"}), min_matches=0,
                    max_matches=obj.max_count))
                continue
            if obj.content_sha256 is not None:
                predicate = ContentPredicate("exact_sha256", obj.content_sha256)
            elif obj.unconstrained or obj.content is None:
                predicate = ContentPredicate("any")
            else:
                predicate = ContentPredicate("utf8_fullmatch",
                                             self._render(obj.content, values, now))
            rules.append(PathRule(
                name=obj.name, pattern=pattern, kinds=frozenset({obj.kind}),
                min_matches=obj.min_count, max_matches=obj.max_count,
                content=predicate))
        binding = {k: v for k, v in values.items()
                   if isinstance(v, (str, int, bool)) and not isinstance(v, float)}
        return TreeEffectContract(
            request=EffectContract(self.tool, binding=binding),
            expected_before=expected_before or TreeSnapshot(entries={}),
            rules=tuple(rules))

    def slack(self, arguments: Mapping[str, Any] | None = None, *,
              clock_bound: bool = True) -> SlackReport:
        """Adversarial freedom left by the instantiated contract, in bits.

        ``clock_bound`` matches ``instantiate(..., now=...)``: clock holes whose
        date is bound to the admission clock carry fewer free bits."""

        def hole_bits(tokens: Sequence[tuple]) -> float:
            return sum(_clock_bits(t[1], clock_bound) if t[1].startswith("clock:")
                       else t[2] for t in tokens if t[0] == "H")

        per_rule: dict[str, float] = {}
        for obj in self.objects:
            bits = 0.0
            if obj.path is None:
                bits = math.inf  # fallback path pattern: names are free
            else:
                bits += hole_bits(obj.path)
            if obj.max_count > obj.min_count:
                bits += math.log2(obj.max_count - obj.min_count + 1)
            if obj.kind == "file":
                if obj.unconstrained or (obj.content is None and obj.content_sha256 is None):
                    bits = math.inf
                elif obj.content is not None:
                    bits += hole_bits(obj.content)
            per_rule[obj.name] = bits
        total = sum(per_rule.values()) if per_rule else 0.0
        return SlackReport(total_bits=total, per_rule=per_rule)

    def to_json(self) -> dict:
        return {"tool": self.tool, "root": self.root, "fixed": dict(self.fixed),
                "training_runs": self.training_runs,
                "objects": [o.to_json() for o in self.objects]}


def describe(tokens: Sequence[tuple]) -> str:
    """Human-readable template form, e.g. docs/features/{code}/feature.json."""
    out = []
    for token in tokens:
        if token[0] == "L":
            out.append(token[1])
        elif token[0] == "A":
            suffix = "" if token[2] == "identity" else "|" + token[2]
            out.append("{" + token[1] + suffix + "}")
        else:
            out.append("{clock}" if token[1].startswith("clock:") else "{*}")
    return "".join(out)


def _path_hole_regex(tokens: Sequence[tuple]) -> str:
    parts = []
    for token in tokens:
        if token[0] == "L":
            parts.append(re.escape(token[1]))
        elif token[0] == "H":
            parts.append(_clock_regex(token[1]) if token[1].startswith("clock:")
                         else token[1])
        else:
            parts.append("[^/]+")
    return "".join(parts)


def _infer_content(members: Sequence[tuple[Observation, bytes]], root: str) -> dict:
    blobs = [blob for _, blob in members]
    try:
        texts = [blob.decode("utf-8") for blob in blobs]
    except UnicodeDecodeError:
        if len(set(blobs)) == 1:
            return {"content_sha256": hashlib.sha256(blobs[0]).hexdigest()}
        return {"unconstrained": True}
    runs = [abstract(text, _sources(obs.arguments, root))
            for (obs, _), text in zip(members, texts)]
    template = anti_unify(runs, path=False)
    if all(t[0] == "L" for t in template) and len(set(blobs)) == 1:
        return {"content_sha256": hashlib.sha256(blobs[0]).hexdigest()}
    return {"content": tuple(template)}


def infer_template(tool: str, observations: Sequence[Observation], *,
                   root: str = DEFAULT_ROOT,
                   fixed: Mapping[str, Any] | None = None) -> EffectTemplate:
    """Infer one effect template from honest training runs of one tool."""
    if len(observations) < 2:
        raise ValueError("template inference needs at least two training runs")
    k = len(observations)
    # abstract every path in every run; group by the abstracted key
    groups: dict[tuple, list[list[tuple[str, tuple, str, bytes | None]]]] = {}
    for index, obs in enumerate(observations):
        sources = _sources(obs.arguments, root)
        for path, (kind, content) in obs.entries.items():
            tokens = abstract(path, sources)
            key = (kind, tuple(_key(t) for t in tokens))
            groups.setdefault(key, [[] for _ in range(k)])
            groups[key][index].append((path, tuple(tokens), kind, content))

    matched: list[list[tuple]] = []
    leftovers: list[list[tuple]] = [[] for _ in range(k)]
    for per_run in groups.values():
        if all(len(members) == 1 for members in per_run):
            matched.append([members[0] for members in per_run])
        else:
            for index, members in enumerate(per_run):
                leftovers[index].extend(members)

    # pair leftovers that are the sole member of their (kind, parent, suffix)
    # bucket in every run: e.g. a note named by a timestamp or a uuid
    def bucket(item: tuple) -> tuple:
        path, _, kind, _ = item
        parent = posixpath.dirname(path)
        return (kind, parent.count("/"), posixpath.splitext(path)[1])

    buckets: dict[tuple, list[list[tuple]]] = {}
    for index, items in enumerate(leftovers):
        for item in items:
            buckets.setdefault(bucket(item), [[] for _ in range(k)])[index].append(item)
    unresolved: list[tuple[tuple, list[list[tuple]]]] = []
    for bkey, per_run in buckets.items():
        if all(len(members) == 1 for members in per_run):
            matched.append([members[0] for members in per_run])
        else:
            unresolved.append((bkey, per_run))

    objects: list[ObjectTemplate] = []
    for number, members in enumerate(sorted(matched, key=lambda m: m[0][0])):
        kind = members[0][2]
        path_template = tuple(anti_unify([m[1] for m in members], path=True))
        name = f"{kind}:{describe(path_template)}"
        if kind == "directory":
            objects.append(ObjectTemplate(name=name, kind="directory",
                                          path=path_template, min_count=0))
            continue
        if kind != "file":
            continue  # links and special objects are never admitted
        content_fields = _infer_content(
            [(obs, m[3] or b"") for obs, m in zip(observations, members)], root)
        objects.append(ObjectTemplate(name=name, kind="file", path=path_template,
                                      **content_fields))
    for bkey, per_run in unresolved:
        kind, _, suffix = bkey
        if kind not in {"file", "directory"}:
            continue
        counts = [len(m) for m in per_run]
        sample = next(m for members in per_run for m in members)
        parent = posixpath.dirname(sample[0])
        parent_tokens = abstract(parent, _sources(
            observations[[len(m) > 0 for m in per_run].index(True)].arguments, root))
        prefix = _path_hole_regex(parent_tokens) + "/" if parent else ""
        regex = prefix + "[^/]+" + re.escape(suffix)
        objects.append(ObjectTemplate(
            name=f"{kind}:~{parent}/*{suffix}", kind=kind, path=None,
            path_regex=regex, min_count=min(counts), max_count=max(counts),
            unconstrained=kind == "file"))
    return EffectTemplate(tool=tool, root=root, objects=tuple(objects),
                          fixed=dict(fixed or {}), training_runs=k)


# --------------------------------------------------------------------------
# Argument perturbation for pin-time training and held-out testing.
# --------------------------------------------------------------------------

_WORD = string.ascii_lowercase


def _rand_token(rng: random.Random, length: int, alphabet: str) -> str:
    return "".join(rng.choice(alphabet) for _ in range(length))


def perturb_value(value: str, rng: random.Random, *, scale: float = 1.0) -> str:
    """A fresh value of the same shape: path, free text, or identifier."""
    if "/" in value or re.fullmatch(r"[\w.-]+\.[A-Za-z0-9]{1,5}", value):
        directory, base = posixpath.split(value)
        stem, ext = posixpath.splitext(base)
        new = _rand_token(rng, max(6, min(12, len(stem))), _WORD + string.digits)
        return posixpath.join(directory, new + ext) if directory else new + ext
    if " " in value or len(value) >= 20:
        words = max(2, round(len(value.split()) * scale))
        body = [_rand_token(rng, rng.randint(3, 9), _WORD) for _ in range(words - 1)]
        body.append(_rand_token(rng, 6, _WORD + string.digits))  # unique anchor
        return " ".join(body)

    def swap(match: re.Match) -> str:
        run = match.group(0)
        if run.isdigit():
            return _rand_token(rng, len(run), string.digits)
        if run.isupper():
            return _rand_token(rng, len(run), string.ascii_uppercase)
        if run.islower():
            return _rand_token(rng, len(run), _WORD)
        return _rand_token(rng, len(run), string.ascii_letters)

    return re.sub(r"[A-Za-z]+|[0-9]+", swap, value)


def perturb_arguments(exemplar: Mapping[str, Any], rng: random.Random, *,
                      fixed: Iterable[str] = (), scale: float = 1.0) -> dict[str, Any]:
    """Perturb every top-level string argument not held fixed."""
    frozen = set(fixed)
    out: dict[str, Any] = {}
    for name, value in exemplar.items():
        if name in frozen or not isinstance(value, str):
            out[name] = value
        else:
            out[name] = perturb_value(value, rng, scale=scale)
    return out


def enum_fields(input_schema: Mapping[str, Any]) -> dict[str, list[Any]]:
    """Top-level fields whose schema restricts them to an enumeration."""
    props = (input_schema or {}).get("properties", {}) or {}
    return {name: list(spec["enum"]) for name, spec in props.items()
            if isinstance(spec, Mapping) and isinstance(spec.get("enum"), list)}


def dumps_template(template: EffectTemplate) -> str:
    return json.dumps(template.to_json(), indent=2, sort_keys=True)

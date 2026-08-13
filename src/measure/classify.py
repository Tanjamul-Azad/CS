"""
Derive metamorphic relations over a harvested corpus and assign
auditability classes A0-A3.

This is the measurement instrument for the paper's headline result:
what fraction of real MCP tools have relation degree 0, and are
therefore undetectable by any client-side audit at any budget?

Deliberately biased toward PRECISION over recall. A spurious relation
produces a false positive at audit time, which for a security tool is
far worse than a missed one -- and it would also inflate the measured
auditability of the ecosystem, biasing the headline number in the
flattering direction. When in doubt we call a tool A0. The reported A0
fraction is therefore an UPPER bound, and the honest framing is
"at least X% is undefendable."
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .extract import ExtractedTool

# --------------------------------------------------------------------------
# Verb and noun vocabularies
# --------------------------------------------------------------------------

WRITE_VERBS = {
    "send", "transfer", "write", "create", "delete", "post", "update",
    "set", "add", "remove", "put", "insert", "upload", "publish", "move",
    "rename", "append", "execute", "run", "apply", "commit", "push",
}

READ_VERBS = {
    "list", "get", "read", "search", "check", "fetch", "query", "find",
    "show", "describe", "view", "count", "lookup", "retrieve", "load",
}

PURE_MARKERS = {
    "compute", "computes", "convert", "converts", "format", "formats",
    "parse", "parses", "calculate", "calculates", "encode", "decode",
    "hash", "transform", "render", "validate", "generate",
}

# Read tools whose result is a quantity that write tools can move.
QUANTITY_NOUNS = {
    "balance", "count", "total", "size", "usage", "quota", "credit",
    "stock", "inventory", "length", "sum",
}

NUMERIC_FIELDS = {
    "amount", "quantity", "qty", "count", "size", "value", "price",
    "credits", "tokens", "n", "limit_amount",
}

STOPWORDS = {
    "a", "an", "the", "to", "of", "for", "from", "in", "on", "by", "with",
    "and", "or", "at", "as", "is", "be", "this", "that", "it", "its",
    "specified", "given", "current", "new", "all", "any", "return",
    "returns", "get", "gets", "set", "list", "using", "use", "you",
}


def verb_of(name: str) -> str:
    return name.replace("-", "_").split("_")[0].lower()


def nouns_of(tool: ExtractedTool) -> set[str]:
    """Resource nouns a tool is about, from its name and description."""
    words = set(tool.name.replace("-", "_").lower().split("_"))
    words |= {
        w.strip(".,:;()[]\"'").lower()
        for w in tool.description.split()[:14]
    }
    out = set()
    for w in words:
        if len(w) < 3 or w in STOPWORDS or w in WRITE_VERBS or w in READ_VERBS:
            continue
        out.add(w.rstrip("s") if len(w) > 4 and w.endswith("s") else w)
    return out


def is_write(t: ExtractedTool) -> bool:
    """Prefer the server's own readOnlyHint over verb heuristics.

    Caveat that belongs in the paper: this annotation is SELF-DECLARED by
    the party we are auditing. A compromised server sets readOnlyHint=true
    and a client that trusts it stops looking. We use it because it is
    accurate for honest servers and improves derivation quality, but the
    trust it requires is exactly the trust this work is about, so we also
    report how much of the corpus depends on it (see `annotation_coverage`).
    """
    ro = t.annotations.get("readOnlyHint")
    if ro is True:
        return False
    if ro is False:
        return True
    return verb_of(t.name) in WRITE_VERBS


def is_read(t: ExtractedTool) -> bool:
    if t.annotations.get("readOnlyHint") is True:
        return True
    return verb_of(t.name) in READ_VERBS


def is_pure(t: ExtractedTool) -> bool:
    """Determinism, from the declared idempotency hint or a purity marker."""
    if is_write(t):
        return False
    if t.annotations.get("idempotentHint") is True:
        return True
    desc = t.description.lower()
    return any(m in desc for m in PURE_MARKERS)


def annotation_coverage(corpus: list[ExtractedTool]) -> dict[str, float]:
    """How much of the corpus declares each behavioral hint.

    Low coverage means the classifier is running mostly on name/description
    heuristics; high coverage means it is leaning on self-declared and
    therefore unverifiable metadata. Both are reportable.
    """
    n = len(corpus) or 1
    keys = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")
    return {k: sum(1 for t in corpus if k in t.annotations) / n for k in keys}


# --------------------------------------------------------------------------
# Derived relations
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class DerivedRelation:
    kind: str            # R1 | R2 | R3 | R4 | R5
    tools: tuple[str, ...]
    server_id: str
    basis: str = ""


def derive_for_server(tools: list[ExtractedTool]) -> list[DerivedRelation]:
    rels: list[DerivedRelation] = []
    if not tools:
        return rels
    server = tools[0].server_id
    writes = [t for t in tools if is_write(t)]
    reads = [t for t in tools if is_read(t)]

    for w in writes:
        w_nouns = nouns_of(w)
        for r in reads:
            shared = w_nouns & nouns_of(r)
            if not shared:
                continue

            # R1 -- write-read consistency
            rels.append(DerivedRelation(
                "R1", (w.name, r.name), server,
                basis="shared resource: " + ", ".join(sorted(shared)[:3]),
            ))

            # R2 -- conservation, when the write moves a numeric quantity
            # and the read reports a quantity of that kind.
            w_numeric = {f.lower() for f in w.input_fields} & NUMERIC_FIELDS
            r_quantity = nouns_of(r) & QUANTITY_NOUNS
            if w_numeric and r_quantity:
                rels.append(DerivedRelation(
                    "R2", (w.name, r.name), server,
                    basis=f"{sorted(w_numeric)[0]} vs {sorted(r_quantity)[0]}",
                ))

            # R5 -- canary, when the client controls a free-form field
            # that a read-back could echo.
            free_form = {f.lower() for f in w.input_fields} & {
                "content", "body", "text", "message", "memo", "note",
                "description", "comment", "data", "payload", "name", "title",
            }
            if free_form:
                rels.append(DerivedRelation(
                    "R5", (w.name, r.name), server,
                    basis=f"canary field: {sorted(free_form)[0]}",
                ))

    # R3 -- determinism, self-relation on pure tools
    for t in tools:
        if is_pure(t):
            rels.append(DerivedRelation("R3", (t.name,), server,
                                        basis="purity marker in description"))

    # R4 -- null-op invariance, needs a numeric field and a read to observe
    if reads:
        for w in writes:
            if {f.lower() for f in w.input_fields} & NUMERIC_FIELDS:
                rels.append(DerivedRelation("R4", (w.name,), server,
                                            basis="numeric field admits zero"))

    return list(dict.fromkeys(rels))


def derive_all(corpus: Iterable[ExtractedTool]) -> list[DerivedRelation]:
    by_server: dict[str, list[ExtractedTool]] = defaultdict(list)
    for t in corpus:
        by_server[t.server_id].append(t)
    out = []
    for tools in by_server.values():
        out.extend(derive_for_server(tools))
    return out


# --------------------------------------------------------------------------
# Auditability classification
# --------------------------------------------------------------------------

def classify(
    corpus: list[ExtractedTool], relations: list[DerivedRelation]
) -> dict[tuple[str, str], tuple[str, int]]:
    """(server_id, tool_name) -> (A-class, relation degree)."""
    deg: dict[tuple[str, str], int] = defaultdict(int)
    kinds: dict[tuple[str, str], set[str]] = defaultdict(set)

    for rel in relations:
        for name in rel.tools:
            key = (rel.server_id, name)
            deg[key] += 1
            kinds[key].add(rel.kind)

    out = {}
    for t in corpus:
        key = (t.server_id, t.name)
        k = kinds.get(key, set())
        if not k:
            cls = "A0"
        elif k & {"R2"}:
            cls = "A3"
        elif k & {"R1", "R5"}:
            cls = "A2"
        else:
            cls = "A1"
        out[key] = (cls, deg.get(key, 0))
    return out


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval. Never report a bare proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0.0, centre - half), min(1.0, centre + half))

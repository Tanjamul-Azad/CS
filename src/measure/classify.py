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

# NOTE ON TUNING DIRECTION -- these two vocabularies are tuned OPPOSITELY,
# because the cost of each error is opposite:
#
#   Relation derivation wants PRECISION. A spurious relation fires a false
#   alarm at audit time and inflates measured auditability.
#
#   Write detection wants RECALL. A missed write is a mutating tool the
#   policy layer waves through as harmless -- exactly the A0-and-mutating
#   cell that nothing else can catch. Under-calling writes is the
#   dangerous error, so this list is deliberately broad.
#
# Real corpus data drove this: purge_sessions, prune_tools, approve_prompt
# and export_session all read as harmless under a narrow verb list.
WRITE_VERBS = {
    "send", "transfer", "write", "create", "delete", "post", "update",
    "set", "add", "remove", "put", "insert", "upload", "publish", "move",
    "rename", "append", "execute", "run", "apply", "commit", "push",
    # destructive
    "purge", "prune", "drop", "clear", "reset", "revoke", "destroy",
    "truncate", "wipe", "erase", "kill", "terminate", "cancel", "close",
    "archive", "expire", "evict", "unlink", "detach", "disable",
    # state-changing
    "approve", "reject", "assign", "grant", "enable", "activate",
    "deactivate", "register", "unregister", "subscribe", "unsubscribe",
    "configure", "install", "deploy", "provision", "schedule", "trigger",
    "invoke", "call", "start", "stop", "restart", "pause", "resume",
    "save", "store", "persist", "sync", "import", "export", "backup",
    "restore", "merge", "patch", "modify", "edit", "change", "replace",
    "toggle", "increment", "decrement", "charge", "refund", "pay",
    "order", "book", "reserve", "submit", "confirm", "finalize",
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

# A field name whose LAST underscore-separated token is one of these marks
# it as pointing at a specific resource instance ("order_id", "file_key",
# "doc_slug") rather than describing a value. This is the basis of the
# strongest pairing tier below: MCP mandates input schemas (unlike output
# schemas, see ExtractedTool.output_fields -- "almost always empty" for
# real servers), so input-to-input identifier matching is evidence that is
# actually available at real-corpus scale, where output-field overlap is
# starved of data.
ID_FIELD_MARKERS = {"id", "key", "uuid", "guid", "slug", "ref", "reference"}

# Excluded even though they end in a marker above: these identify the
# CALL (auth, a request, a client session) rather than the RESOURCE the
# write touched. A field like `api_key` or `session_id` tends to appear on
# nearly every tool a server exposes, so treating it as a pairing key would
# link every write to every read that also happens to need authenticating
# -- precisely the spurious-pairing failure mode this tier exists to avoid.
ID_FIELD_EXCLUDE = {
    "api_key", "apikey", "secret_key", "secretkey", "access_key",
    "auth_key", "authkey", "session_key", "session_id", "sessionid",
    "request_id", "requestid", "trace_id", "traceid",
    "correlation_id", "correlationid", "idempotency_key", "idempotencykey",
    "client_id", "clientid", "user_key",
}

# Verbs whose write typically MINTS a new resource and returns its
# identifier, rather than accepting one. A create-style write paired with
# a reader that takes an identifier is still strong evidence -- the reader
# can be pointed at exactly the thing just created -- but the identifier
# has to come from the write's own RESPONSE at audit time, not its
# arguments, which is why this is kept as a distinct, narrower condition
# (also requires a shared resource noun) rather than folded into the plain
# input-input overlap above.
CREATE_VERBS = {
    "create", "add", "insert", "register", "upload", "submit", "book",
    "reserve", "publish", "provision", "schedule", "open",
}


def _is_id_field(name: str) -> bool:
    n = name.strip().lower().replace("-", "_")
    if n in ID_FIELD_EXCLUDE:
        return False
    if n in ID_FIELD_MARKERS:
        return True
    return n.split("_")[-1] in ID_FIELD_MARKERS


def verb_of(name: str) -> str:
    return name.replace("-", "_").split("_")[0].lower()


def _stem(w: str) -> str:
    """Crude plural stem, matching the rule used in `nouns_of`."""
    return w[:-1] if len(w) > 4 and w.endswith("s") else w


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
        w_fields = {f.lower() for f in w.input_fields}
        for r in reads:
            shared = w_nouns & nouns_of(r)

            # Field overlap is a far stronger signal than shared nouns: if
            # a write ACCEPTS {recipient, amount, memo} and a read RETURNS
            # {recipient, amount, memo}, that read can corroborate that
            # write regardless of whether their names share vocabulary.
            # Noun matching alone misses transfer_money <-> list_transactions,
            # which is the canonical case the whole method is built on.
            field_overlap = w_fields & {f.lower() for f in r.output_fields}

            # R2 -- conservation. Evaluated INDEPENDENTLY of the R1 test:
            # a write that moves a numeric quantity is constrained by any
            # read that reports a quantity of that kind, whether or not the
            # two share vocabulary. transfer_money and check_balance share
            # no noun and no field, yet balance-after == balance-before -
            # amount is exactly the invariant that catches a skimming
            # server. Gating this behind R1 silently deleted the strongest
            # relation class from the whole analysis.
            w_numeric = w_fields & NUMERIC_FIELDS
            # Match quantity nouns against STEMMED output fields, but carry
            # the field's real name forward. A read declaring `credits`
            # stems to `credit` for matching; if the relation then records
            # the stem, the auditor looks up a key the response does not
            # have and silently skips the check. Detection failed on the
            # entire compute domain for exactly this reason.
            stem_to_field = {_stem(f.lower()): f.lower() for f in r.output_fields}
            declared_qty = {stem_to_field[q] for q in stem_to_field
                            if q in QUANTITY_NOUNS}
            # Prefer a name the read actually RETURNS over one merely
            # mentioned in its prose. `get_credits` is described as
            # returning "the remaining credit balance", so description
            # nouns offer `balance` -- a key the response does not contain.
            # Snapshotting it yields nothing and the conservation check is
            # skipped in silence, which is the worst failure mode a
            # detector has. Fall back to prose only when no output field
            # names a quantity.
            r_quantity = declared_qty or (nouns_of(r) & QUANTITY_NOUNS)
            if w_numeric and r_quantity:
                rels.append(DerivedRelation(
                    "R2", (w.name, r.name), server,
                    basis=f"{sorted(w_numeric)[0]} vs {sorted(r_quantity)[0]}",
                ))

            # R1, keyed tier -- identifier-input overlap. If a write ACCEPTS
            # `order_id` and a read also ACCEPTS `order_id`, the read can be
            # pointed at the EXACT instance the write touched, not merely a
            # same-topic list. This is independent of output-field overlap
            # above (and fires far more often on real servers, since input
            # schemas are declared reliably while output schemas mostly
            # aren't) and independent of noun overlap (an identifier name
            # match is evidence on its own). Emitted unconditionally, ahead
            # of the shared/field_overlap gate below, so it is never skipped
            # for lacking either of those.
            w_id_fields = {f.lower() for f in w.input_fields if _is_id_field(f)}
            r_id_fields = {f.lower() for f in r.input_fields if _is_id_field(f)}
            key_overlap = w_id_fields & r_id_fields
            if key_overlap:
                rels.append(DerivedRelation(
                    "R1", (w.name, r.name), server,
                    basis=f"keyed by {sorted(key_overlap)[0]}",
                ))
            elif r_id_fields and shared and verb_of(w.name) in CREATE_VERBS:
                # R1, keyed-after-create tier -- the write MINTS a new
                # resource (create/register/upload/...) rather than
                # accepting an existing identifier, so there is no
                # input-input overlap to match on. But if the reader takes
                # an identifier for the same resource (shared noun), the
                # write's own RESPONSE is the likely source of that
                # identifier at audit time (see _probe_args in auditor.py,
                # which now also looks there). Weaker than direct
                # input-input overlap -- it depends on the write's runtime
                # response shape, which we cannot see statically -- so it
                # is recorded distinctly in the basis string even though it
                # is treated the same strength by the auditor.
                rels.append(DerivedRelation(
                    "R1", (w.name, r.name), server,
                    basis=f"keyed by {sorted(r_id_fields)[0]} (post-create fetch)",
                ))

            if not shared and not field_overlap:
                continue

            basis = (f"read returns {', '.join(sorted(field_overlap)[:3])}"
                     if field_overlap
                     else "shared resource: " + ", ".join(sorted(shared)[:3]))

            # R1 -- write-read consistency
            rels.append(DerivedRelation("R1", (w.name, r.name), server, basis))

            # R5 -- canary, when the client controls a free-form field
            # that a read-back could echo.
            free_form = w_fields & {
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

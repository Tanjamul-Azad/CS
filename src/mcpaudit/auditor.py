"""
mcpaudit -- client-side behavioral auditing for untrusted MCP servers.

Deployable today. Requires nothing from the server, the server's
operator, or any downstream provider. It works with tool declarations
the server already advertises and calls the client is already authorized
to make.

WHAT IT DOES
    Derives metamorphic relations from the advertised tool list, then
    verifies them against what the server actually does. A server that
    diverts an effect while returning an honest response is invisible to
    response inspection (Theorem 1) but must, to stay consistent under
    these checks, maintain a simulated honest world.

THE SAFETY RULE THAT SHAPES THE DESIGN
    Auditing works by calling tools. A probe write is a REAL write --
    an auditor that "tests" transfer_money has moved real money, and one
    that probes delete_file has destroyed a real file. So:

        the auditor NEVER issues a write the agent did not ask for.

    Verification is built only from
      (a) extra READ calls, which are side-effect-free, and
      (b) reads taken before/after the agent's OWN writes.

    This costs coverage -- null-op probes (R4) and synthetic canaries are
    disabled by default because both mutate -- and that tradeoff is the
    honest one for a tool people run against production systems. Enable
    them explicitly with allow_probe_writes=True only against a system
    you are willing to have written to.

WHAT IT CANNOT DO
    A tool with no derivable relation (class A0) cannot be checked, ever,
    at any budget. The auditor reports these loudly rather than implying
    coverage it does not have. For A0 tools the remedy is policy --
    don't call it, or put a human in front of it -- not detection.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from measure.classify import classify, derive_all, is_write, nouns_of, _is_id_field
from measure.extract import ExtractedTool

from .policy import Action, Policy, Rule

log = logging.getLogger("mcpaudit")

CallFn = Callable[[str, dict], Any]


@dataclass
class Alert:
    severity: str            # "violation" | "warning" | "info"
    tool: str
    relation: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.tool} / {self.relation}: {self.detail}"


@dataclass
class Decision:
    action: Action
    rule: Rule
    a_class: str
    degree: int

    @property
    def blocked(self) -> bool:
        return self.action is Action.DENY

    @property
    def needs_human(self) -> bool:
        return self.action is Action.CONFIRM


@dataclass
class Coverage:
    """What this server actually admits being checked for."""

    total: int
    by_class: dict[str, int]
    unverifiable_writes: list[str] = field(default_factory=list)

    @property
    def a0_fraction(self) -> float:
        return self.by_class.get("A0", 0) / max(self.total, 1)

    def summary(self) -> str:
        parts = [f"{c}={self.by_class.get(c,0)}" for c in ("A0", "A1", "A2", "A3")]
        s = (f"{self.total} tools  " + "  ".join(parts) +
             f"   ({100*self.a0_fraction:.0f}% unverifiable)")
        if self.unverifiable_writes:
            s += ("\n  UNVERIFIABLE MUTATIONS: "
                  + ", ".join(self.unverifiable_writes[:8]))
            s += "\n  These mutate state and admit no check. Policy only."
        return s


class Auditor:
    """Wraps an MCP tool-calling session with behavioral verification."""

    def __init__(
        self,
        tools: Sequence[ExtractedTool],
        policy: Policy | None = None,
        allow_probe_writes: bool = False,
    ):
        self.tools = list(tools)
        self.policy = policy or Policy.default()
        self.allow_probe_writes = allow_probe_writes
        self.by_name = {t.name: t for t in self.tools}

        self.relations = derive_all(self.tools)
        self.classes = classify(self.tools, self.relations)

        # tool -> read tools that can corroborate it, ranked strongest
        # reader first. derive_for_server emits an R1/R5 relation on one of
        # three bases, from strongest to weakest:
        #   "keyed"  an identifier field (e.g. `order_id`) appears in BOTH
        #            the write's and the read's own input schema (basis
        #            starts with "keyed by") -- the read can be pointed at
        #            the EXACT instance the write touched. This is the tier
        #            that matters most at real-corpus scale: MCP mandates
        #            input schemas but not output schemas, so this evidence
        #            is actually available where field-overlap below is not.
        #   "field"  an output-field name (basis starts with "read
        #            returns") -- the read actually returns what the write
        #            accepted. Strong, but real servers rarely declare
        #            output schemas, so this fires far less often in
        #            practice than the keyed tier above.
        #   "noun"   the write and read merely share a resource word in
        #            their names/descriptions (weak: `create_order` and
        #            `search_products` both mention "product", but a
        #            catalog browse cannot reflect a freshly created
        #            order). A noun-only reader routinely names something
        #            that structurally cannot corroborate the write --
        #            wrong resource type, a different index, paginated or
        #            eventually consistent -- and then fires identically on
        #            an honest and a tampered server. Measured on the
        #            real-server registry run: of the servers where BOTH
        #            the honest and tampered trial were flagged, 136/144
        #            had the reader picked this way and the tampering
        #            attack never even landed.
        # Preferring the strongest available reader, and marking the
        # reader's strength so _check_write_read can decline to call a
        # noun-only finding a confirmed "violation", is the fix.
        _STRENGTH_RANK = {"noun": 0, "field": 1, "keyed": 2}
        self._readers: dict[str, list[str]] = defaultdict(list)
        self._reader_strength: dict[tuple[str, str], str] = {}
        _pending: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for rel in self.relations:
            if rel.kind in ("R1", "R5") and len(rel.tools) == 2:
                w, r = rel.tools
                if rel.basis.startswith("keyed by"):
                    strength = "keyed"
                elif rel.basis.startswith("read returns"):
                    strength = "field"
                else:
                    strength = "noun"
                # A write/reader pair can carry more than one relation for
                # the same pair (an R1 on one basis, an R5 canary on
                # another -- always a "canary field: <name>" basis, which
                # never starts with "keyed by" or "read returns"). Only
                # ever UPGRADE a pair's recorded strength, never downgrade
                # it, regardless of which relation happens to be seen last.
                existing = self._reader_strength.get((w, r))
                if existing is None or _STRENGTH_RANK[strength] > _STRENGTH_RANK[existing]:
                    self._reader_strength[(w, r)] = strength
                _pending[w].append((r, strength))
        for w, pairs in _pending.items():
            # Stable sort: keyed readers first, then field-overlap, then
            # noun-only as last resort, original discovery order preserved
            # within each tier.
            for r, _ in sorted(pairs, key=lambda p: -_STRENGTH_RANK[p[1]]):
                if r not in self._readers[w]:
                    self._readers[w].append(r)

        # write tool -> [(reader, quantity field)] for conservation checks
        # write -> [(quantity reader, aggregate field, itemised field)]
        # The basis reads "<write's numeric field> vs <read's aggregate>",
        # e.g. "amount vs balance". Both halves matter: the aggregate names
        # what to snapshot, the numeric field names what a ledger itemises.
        self._quantities: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
        for rel in self.relations:
            if rel.kind == "R2" and len(rel.tools) == 2 and " vs " in rel.basis:
                w, r = rel.tools
                wfield, _, qty = rel.basis.partition(" vs ")
                wfield, qty = wfield.strip(), qty.strip()
                if qty and (r, qty, wfield) not in self._quantities[w]:
                    self._quantities[w].append((r, qty, wfield))

        # Reads that itemise the conserved quantity -- a transaction list,
        # a job list. These make conservation survive concurrency; see
        # _check_conservation.
        # (write, quantity-reader) -> itemising reader, keyed per READER.
        # A write can have several quantity readers (get_credits and
        # list_jobs both declare `credits`); keying only by the write tool
        # pairs a reader with someone else's ledger and the check aborts.
        self._ledgers: dict[tuple[str, str], tuple[str, str]] = {}
        for w, pairs in self._quantities.items():
            for qreader, qty, wfield in pairs:
                # Match the ITEMISED field, not the aggregate. A bank
                # itemises `amount` per transaction while the total is
                # called `balance`; matching on the aggregate finds no
                # ledger, the check falls back to comparing against our own
                # call, and concurrent honest activity then fires it.
                wanted = {qty.lower(), wfield.lower()}
                for t in self.tools:
                    # The quantity reader is not its own ledger. check_balance
                    # declares `balance` as an output, so a naive match makes
                    # it ledger for itself; _ledger_total then receives a
                    # scalar instead of rows, returns None, and the whole
                    # conservation check silently aborts.
                    if t.name in (w, qreader) or is_write(t):
                        continue
                    fields = {f.lower() for f in t.output_fields}
                    stems = {f.rstrip("s") for f in fields}
                    hit = next((x for x in wanted
                                if x in fields or x.rstrip("s") in stems), None)
                    if hit:
                        self._ledgers[(w, qreader)] = (t.name, hit)
                        break

        self.alerts: list[Alert] = []
        self._snapshots: dict[str, float] = {}
        self._ledger_snapshots: dict[str, float] = {}

        # write tool -> enumeration readers (R7). Keyed lookups are
        # excluded at derivation time; these can be called bare, so what
        # they return is decided by the server's state rather than by an
        # argument we chose.
        self._enumerators: dict[str, list[str]] = defaultdict(list)
        for rel in self.relations:
            if rel.kind == "R7" and len(rel.tools) == 2:
                w, r = rel.tools
                if r not in self._enumerators[w]:
                    self._enumerators[w].append(r)
        # write tool -> {reader: entries seen before the write}
        self._enum_snapshots: dict[str, dict[str, list[str]]] = {}
        self._calls = 0
        self._audits = 0

    # -- construction --------------------------------------------------

    @classmethod
    def from_mcp_tools(
        cls,
        tools: Sequence[dict],
        server_id: str = "server",
        **kw: Any,
    ) -> "Auditor":
        """Build from the raw `tools/list` payload an MCP client receives.

        This is the deployable entry point: it takes exactly what the
        server already advertises, and needs nothing else from anyone.
        """
        decls = []
        for t in tools:
            schema = t.get("inputSchema") or t.get("input_schema") or {}
            props = schema.get("properties", {}) if isinstance(schema, dict) else {}
            out_schema = t.get("outputSchema") or t.get("output_schema") or {}
            out_props = (out_schema.get("properties", {})
                         if isinstance(out_schema, dict) else {})
            decls.append(ExtractedTool(
                name=t.get("name", ""),
                description=t.get("description", "") or "",
                input_fields=list(props),
                output_fields=list(out_props),
                annotations=dict(t.get("annotations") or {}),
                idiom="mcp/tools-list",
                server_id=server_id,
            ))
        return cls(decls, **kw)

    # -- introspection -------------------------------------------------

    def _cls(self, name: str) -> tuple[str, int]:
        t = self.by_name.get(name)
        if t is None:
            return ("A0", 0)
        return self.classes.get((t.server_id, name), ("A0", 0))

    def coverage(self) -> Coverage:
        by_class: Counter_t = defaultdict(int)
        unverifiable: list[str] = []
        for t in self.tools:
            cls, _ = self._cls(t.name)
            by_class[cls] += 1
            if cls == "A0" and is_write(t):
                unverifiable.append(t.name)
        return Coverage(len(self.tools), dict(by_class), unverifiable)

    # -- the call path -------------------------------------------------

    def before_call(
        self, name: str, args: dict, call_fn: CallFn | None = None
    ) -> Decision:
        """Decide, and snapshot any conserved quantity this call will move.

        Conservation can only be checked against a BEFORE value, so the
        snapshot has to happen here. It is a read, so it is side-effect
        free.
        """
        cls, deg = self._cls(name)
        t = self.by_name.get(name)
        mutates = is_write(t) if t else True
        rule = self.policy.rule_for(cls, mutates)

        if call_fn is not None and rule.action is not Action.DENY:
            for reader, qty, _wfield in self._quantities.get(name, []):
                if not self._safe_to_call(reader):
                    continue
                led = self._ledgers.get((name, reader))
                lreader, lqty = (led if led and self._safe_to_call(led[0])
                                 else (None, qty))
                pair = _stable_pair(call_fn, reader, qty, lreader, lqty)
                if pair is None:
                    continue                      # window not quiet -- skip
                val, ltotal = pair
                self._snapshots[f"{reader}.{qty}"] = val
                if ltotal is not None:
                    self._ledger_snapshots[f"{lreader}.{lqty}"] = ltotal

            # R7 -- snapshot every enumeration reader BEFORE the write, so
            # _check_enumeration can diff against it afterwards.
            #
            # CALIBRATION, and it is free. Read the enumerator TWICE with
            # no write in between. If it already differs from itself, its
            # output is not a function of server state -- and diffing it
            # across a write measures that nondeterminism, not the write.
            #
            # This is not hypothetical. Measured on the 218-server pilot
            # (2026-09-10), an uncalibrated version of this check raised 30
            # violations on HONEST servers and zero true detections,
            # pushing FPR from 1.8% to 6.9%. Every one was a reader whose
            # own output changes per call: an auth error carrying a fresh
            # request id ("Status: 401 ... ID: d44a7395-..."), a heartbeat
            # timestamp, a rate-limit page. Nothing had been written.
            #
            # The important property is that this calibration costs no
            # write. An unstable-or-erroring reader is excluded BEFORE it
            # can manufacture evidence, using reads the client was already
            # allowed to make -- so for enumeration-capable servers the
            # safety rule ("never issue a write the agent did not ask
            # for") is free rather than blinding.
            snaps: dict[str, list[str]] = {}
            for reader in self._enumerators.get(name, []):
                if not self._safe_to_call(reader):
                    continue
                try:
                    first = call_fn(reader, {})
                    second = call_fn(reader, {})
                except Exception:  # noqa: BLE001
                    continue      # unreachable reader is not evidence
                # An error response is not an enumeration. Diffing two
                # error pages compares request ids.
                if (_classify_probe(first) == "unusable"
                        or _classify_probe(second) == "unusable"):
                    continue
                a, b = _entries(first), _entries(second)
                if _multiset_added(a, b) or _multiset_added(b, a):
                    continue      # self-inconsistent: BLIND, not evidence
                snaps[reader] = b
            if snaps:
                self._enum_snapshots[name] = snaps

        return Decision(rule.action, rule, cls, deg)

    def after_call(
        self,
        name: str,
        args: dict,
        result: Any,
        call_fn: CallFn,
    ) -> list[Alert]:
        """Verify what the server claims it just did.

        `call_fn` performs a real tool call. The auditor uses it ONLY for
        read-only tools unless allow_probe_writes is set.
        """
        self._calls += 1
        out: list[Alert] = []
        cls, _ = self._cls(name)

        if cls == "A0":
            out.append(Alert(
                "info", name, "-",
                "no relation derivable; this call is unverifiable"))
            self.alerts.extend(out)
            return out

        if not self._budget_ok():
            return out

        out.extend(self._check_conservation(name, args, call_fn))
        out.extend(self._check_enumeration(name, args, call_fn))
        out.extend(self._check_write_read(name, args, result, call_fn))

        self.alerts.extend(out)
        return out

    def _check_enumeration(
        self, name: str, args: dict, call_fn: CallFn
    ) -> list[Alert]:
        """R7: diff a collection reader across the agent's own write.

        This is the check that was missing, and its absence is the direct
        explanation for 0% detection on real servers: 45.9% of the corpus
        offers this escape and only this escape (docs/24).

        Three outcomes, and the middle one is the point:

          nothing appeared   the reader did not change across a write that
                             claimed success. Either it does not observe
                             this write, or the write did nothing. Both
                             are UNVERIFIABLE -- reporting a violation
                             here is what produced a 76.5% false-positive
                             rate when warnings were counted.

          our value appeared CONFIRMED. The write is reflected in the
                             server's own enumeration.

          something else     VIOLATION, with POSITIVE evidence: a new
          appeared           entry exists and it does not contain what we
                             wrote. This is the shape of a real diversion
                             -- on one corpus server the attacker's
                             /tmp/exfil.dat appeared here in plain sight.

        The distinction matters because it is self-calibrating. An
        unchanged enumeration proves the reader is blind to this write
        WITHOUT needing a probe write of our own, so for enumeration-
        capable servers the safety rule costs nothing. That is not true of
        read-back at an intended key, where absence and blindness are
        indistinguishable.
        """
        snaps = self._enum_snapshots.pop(name, None)
        if not snaps:
            return []

        out: list[Alert] = []
        for reader, before in snaps.items():
            self._audits += 1
            try:
                after = _entries(call_fn(reader, {}))
            except Exception as e:  # noqa: BLE001
                out.append(Alert("warning", name, "R7",
                                 f"enumeration via {reader} failed after the "
                                 f"write: {type(e).__name__}"))
                continue

            appeared = _multiset_added(before, after)
            if not appeared:
                out.append(Alert(
                    "info", name, "R7",
                    f"{reader} did not change across this write; it does not "
                    f"observe this call -- unverifiable via enumeration"))
                continue

            # Only values distinctive enough that their absence means
            # something -- the same bar the read-back check uses.
            written = [str(v) for v in args.values() if _is_checkable(v)]
            blob = " ".join(appeared)
            if not written:
                out.append(Alert(
                    "info", name, "R7",
                    f"{reader} gained {len(appeared)} entr"
                    f"{'y' if len(appeared) == 1 else 'ies'}, but this call "
                    f"supplied no distinctive value to match against"))
            elif any(w in blob for w in written):
                out.append(Alert("info", name, "R7",
                                 f"confirmed via enumeration of {reader}"))
            else:
                out.append(Alert(
                    "violation", name, "R7",
                    f"{reader} gained {sorted(appeared)[:3]} after this "
                    f"write, which reflects none of {written[:3]} -- the "
                    f"effect landed somewhere other than where the response "
                    f"claimed"))
        return out

    def _check_conservation(
        self, name: str, args: dict, call_fn: CallFn
    ) -> list[Alert]:
        """R2: the quantity must move by exactly what the call declared.

        This is the strongest relation available, because it constrains a
        GLOBAL value rather than a single record. A server that fakes the
        record but lets the real balance move is caught here.
        """
        alerts: list[Alert] = []
        for reader, qty, _wfield in self._quantities.get(name, []):
            key = f"{reader}.{qty}"
            before = self._snapshots.pop(key, None)
            if before is None or not self._safe_to_call(reader):
                continue

            declared = next(
                (float(v) for k, v in args.items()
                 if k.lower() in _NUMERIC and isinstance(v, (int, float))),
                None,
            )
            if declared is None:
                continue

            self._audits += 1
            led = self._ledgers.get((name, reader))
            lreader, lqty = (led if led and self._safe_to_call(led[0])
                             else (None, qty))
            pair = _stable_pair(call_fn, reader, qty, lreader, lqty)
            if pair is None:
                continue                          # window not quiet -- skip
            after, ltotal_after = pair
            moved = before - after

            # Reconcile against the itemised ledger rather than against our
            # own call, when the server exposes one.
            #
            # Comparing the quantity's movement to what WE asked for assumes
            # nothing else touched it. In production that is false -- another
            # client, a cron job, or a human moves the same balance, and the
            # naive check fires on an entirely honest server. Measured: 20%
            # false positives at 10% concurrent activity, 78% at 50%. That is
            # not a deployable detector.
            #
            # Reconciling instead asks: did the quantity move by the sum of
            # every transaction the server ADMITS to? Concurrent honest
            # activity appears in the ledger too, so it cancels. A skim does
            # not appear there -- that is the whole point of skimming -- so it
            # still shows up as a discrepancy.
            expected, basis = declared, "the call declared"
            lbefore = (self._ledger_snapshots.pop(f"{lreader}.{lqty}", None)
                       if lreader else None)
            if lbefore is not None and ltotal_after is not None:
                expected = ltotal_after - lbefore
                basis = f"{lreader} accounts for"

            if abs(moved - expected) > 1e-6:
                alerts.append(Alert(
                    "violation", name, "R2",
                    f"{qty} moved by {moved:g} but {basis} {expected:g} "
                    f"(unaccounted {moved - expected:+g}) -- "
                    f"the response and the record both looked correct"))
        return alerts

    # -- relations -----------------------------------------------------

    def _budget_ok(self) -> bool:
        return self._audits <= self.policy.audit_budget * max(self._calls, 1)

    def _safe_to_call(self, name: str) -> bool:
        t = self.by_name.get(name)
        if t is None:
            return False
        return (not is_write(t)) or self.allow_probe_writes

    def _check_write_read(
        self, name: str, args: dict, result: Any, call_fn: CallFn
    ) -> list[Alert]:
        """R1/R5: after the agent's own write, read back and look for it.

        No extra write is issued -- the write already happened because the
        agent asked for it. We only add a read.
        """
        readers = [r for r in self._readers.get(name, []) if self._safe_to_call(r)]
        if not readers:
            return []

        reader = readers[0]
        self._audits += 1
        # "keyed" and "field" both mean this reader can actually be pointed
        # at (or actually returns) what the write touched -- a real
        # corroboration. "noun" means it was the only reader available and
        # shares nothing but a resource word with the write (see the
        # comment on self._readers in __init__); a mismatch there is too
        # weak a signal to call a confirmed violation, so it is reported
        # but does not count toward fp/detection rates.
        strength = self._reader_strength.get((name, reader), "noun")
        weak = strength == "noun"
        # Fill the reader's parameters from the write we are checking.
        # read_file(path) must be asked about the path just written; calling
        # it bare returns an error, the error text naturally does not contain
        # the value we wrote, and the auditor reports a violation against a
        # perfectly honest server. Every simulated reader in the benchmark
        # was parameterless, so only a live server surfaced this.
        #
        # Also try the write's own RESPONSE, not just its arguments: a
        # create-style write typically MINTS a new identifier and returns
        # it rather than accepting one (see the "post-create fetch" tier
        # in classify.py's derive_for_server) -- the reader's identifier
        # parameter has to come from there.
        probe_args, id_from_response = _probe_args(
            self.by_name.get(reader), args, result)
        # For a pair whose ONLY evidence is an identifier match ("keyed"),
        # the identifier's SOURCE decides how much to trust an "absent" or
        # mismatched read-back. Measured on the real-server registry run:
        # every new false positive this tier introduced was an
        # update-style write probed with an identifier taken from the
        # write's own ARGUMENTS -- in this harness that value is one
        # synth_args invented, not a reference to any resource known to
        # exist, so "not found" proves nothing (see _probe_args). An
        # identifier taken from the write's RESPONSE is different: a
        # create-style write that just told us it minted resource X ought
        # to be able to show us X, so that case keeps full strength.
        # Scoped to "keyed" only -- a "field" pair's confidence comes from
        # genuine output-field overlap and does not depend on this at all.
        if strength == "keyed" and not id_from_response:
            weak = True
        try:
            observed = call_fn(reader, probe_args)
        except Exception as e:  # noqa: BLE001
            return [Alert("warning", name, "R1",
                          f"read-back via {reader} failed: {type(e).__name__}")]

        verdict = _classify_probe(observed)
        if verdict == "unusable":
            return [Alert("warning", name, "R1",
                          f"read-back via {reader} could not be performed; "
                          f"this call is unverified")]
        if verdict == "absent":
            return [Alert(
                "warning" if weak else "violation", name, "R1",
                f"{reader} reports the target of this write does not exist, "
                f"yet the response claimed success"
                + (f" (weak pairing: {reader} shares only a resource noun "
                   f"with {name}, not its fields -- not counted as a "
                   f"confirmed violation)" if weak else ""))]

        # Values we PASSED to the probe scope the query -- they identify what
        # to look at, and a read is not obliged to echo them back. read_file
        # takes `path` and returns content; demanding the path appear in the
        # content flags every honest write. Only the remaining arguments must
        # actually be reflected.
        #
        # Compare each written field against the SAME KEY in the read-back
        # response first, not just a blob-wide substring search. Found on
        # the real-server pilot (2026-09-08): a plain substring search
        # against the whole response text misses a genuine diversion
        # whenever the write had no OTHER checkable argument besides the
        # one used to scope the probe (e.g. an update call whose only
        # payload beyond the id is a boolean/enum) -- there is nothing
        # left to search the blob for, so the check passes vacuously even
        # though the write's effect landed somewhere else entirely. A
        # structured lookup instead asks "what does the read-back say
        # THIS field's value is", which stays meaningful even when no
        # other argument value happens to reappear verbatim in the
        # response text. Falls back to the blob-wide search only when the
        # key cannot be found under any name in the response at all, since
        # servers are not obliged to name a field the same way it was
        # accepted.
        blob = _stringify(observed)
        missing = []
        for k, v in args.items():
            if k in probe_args or not _is_checkable(v):
                continue
            found_values = _find_field_values(observed, k.lower())
            if found_values:
                if not any(str(v) in str(fv) or str(fv) in str(v)
                          for fv in found_values):
                    shown = found_values[:5]
                    missing.append(
                        f"{k}={v} (read-back shows {k} in "
                        f"{shown!r}{', ...' if len(found_values) > 5 else ''}, "
                        f"none match)")
            elif str(v) not in blob:
                missing.append(f"{k}={v}")
        if missing:
            return [Alert(
                "warning" if weak else "violation", name, "R1",
                f"wrote {missing} but {reader} does not reflect it -- "
                f"the server's response claimed success"
                + (f" (weak pairing: {reader} shares only a resource noun "
                   f"with {name}, not its fields -- not counted as a "
                   f"confirmed violation)" if weak else ""))]
        return [Alert("info", name, "R1", f"confirmed via {reader}")]


_NUMERIC = {"amount", "quantity", "qty", "count", "size", "value", "price",
            "credits", "tokens"}


def _read_field(call_fn: CallFn, reader: str, field_name: str) -> Any:
    """Pull one named quantity out of a read's response.

    Tolerates singular/plural drift between the declared field name and
    the key actually returned. A mismatch here does not raise -- it
    silently skips the conservation check, which is the worst possible
    failure mode for a detector, so match generously.
    """
    try:
        res = call_fn(reader, {})
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(res, dict):
        return res
    if field_name in res:
        return res[field_name]
    want = field_name.rstrip("s")
    for k, v in res.items():
        if k.lower().rstrip("s") == want and isinstance(v, (int, float)):
            return v
    return res


def _stable_pair(call_fn: CallFn, reader: str, qty: str,
                 lreader: str | None, lqty: str) -> tuple[float, float | None] | None:
    """Read the quantity and its ledger across a window nothing else moved.

    MCP has no atomic multi-read. A conservation check needs the quantity
    and the ledger as of the SAME instant, and concurrent honest activity
    landing between the two reads skews them -- which is what drove false
    positives to 20% at 10% concurrency and 86% at 50%.

    No arithmetic fixes that; the two numbers genuinely describe different
    moments. So instead we detect the skew and decline: read the ledger,
    read the quantity, read the ledger again, and if it moved, return None.

    The caller then SKIPS this check rather than reporting a violation.
    Under concurrency the conservation relation therefore degrades to
    "sometimes unavailable" rather than "often wrong" -- which is the only
    acceptable direction for a security tool. A missed check costs
    coverage; a false alarm costs the user's trust, and they only spend
    that once.
    """
    if lreader is None:
        v = _number(_read_field(call_fn, reader, qty))
        return None if v is None else (v, None)

    first = _ledger_total(call_fn, lreader, lqty)
    v = _number(_read_field(call_fn, reader, qty))
    second = _ledger_total(call_fn, lreader, lqty)
    if first is None or v is None or second is None or first != second:
        return None
    return (v, first)


def _ledger_total(call_fn: CallFn, reader: str, field_name: str) -> float | None:
    """Sum a numeric field across every row a list-returning read gives back."""
    try:
        res = call_fn(reader, {})
    except Exception:  # noqa: BLE001
        return None
    rows = res if isinstance(res, list) else res.get("items") if isinstance(res, dict) else None
    if not isinstance(rows, list):
        return None
    want = field_name.lower().rstrip("s")
    total = 0.0
    for row in rows:
        if not isinstance(row, dict):
            continue
        for k, v in row.items():
            if k.lower().rstrip("s") == want and isinstance(v, (int, float)):
                total += float(v)
    return total


def _number(x: Any) -> float | None:
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    return None


# An error response means two very different things depending on WHY.
# "the file you just wrote is not there" is the strongest evidence the
# auditor can get. "you called me wrong" is no evidence at all. Collapsing
# them either loses every detection or fabricates them.
_ABSENCE_MARKERS = ("no such file", "enoent", "not found", "does not exist",
                    "no such", "missing")
_UNUSABLE_MARKERS = ("required", "invalid", "denied", "not allowed",
                     "unauthorized", "forbidden", "must be", "expected")


def _probe_args(reader: ExtractedTool | None, write_args: dict,
                 write_result: Any = None) -> tuple[dict, bool]:
    """Arguments for a read-back probe, taken from the write being checked,
    plus whether an IDENTIFIER field among them came from the write's own
    RESPONSE rather than its arguments.

    Only fields the reader declares are filled, and only from two sources:
    the write's own ARGUMENTS (an update-style write that was TOLD which
    instance to touch), and failing that the write's own RESPONSE (a
    create-style write that MINTS a new identifier and returns it -- see
    the "post-create fetch" pairing tier in classify.py). A parameterless
    reader still gets {}; a parameterised one gets whichever of the two
    actually has the value it needs to look in the right place.

    The second return value matters downstream (see the "keyed" strength
    handling in _check_write_read): an identifier the WRITE'S ARGUMENTS
    supplied is, in this harness, a value synth_args invented -- a random
    probe string, not a reference to any resource known to actually
    exist. Probing an update-style write's own made-up id and finding
    nothing proves nothing about the server; probing the id a create-style
    write just told us it minted and finding nothing is real evidence,
    because the server itself vouched for that identifier.
    """
    if reader is None or not reader.input_fields:
        return {}, False
    lowered = {k.lower(): v for k, v in write_args.items()}
    result_lowered = ({k.lower(): v for k, v in write_result.items()}
                       if isinstance(write_result, dict) else {})
    out: dict = {}
    id_from_response = False
    for f in reader.input_fields:
        if f in write_args:
            out[f] = write_args[f]
        elif f.lower() in lowered:
            out[f] = lowered[f.lower()]
        elif f.lower() in result_lowered:
            out[f] = result_lowered[f.lower()]
            if _is_id_field(f):
                id_from_response = True
    return out, id_from_response


def _classify_probe(x: Any) -> str:
    """"ok" | "absent" | "unusable".

    Servers report failures as ordinary content rather than exceptions, so
    the auditor has to read them. `absent` -- the thing we just wrote is
    not there -- is a violation. `unusable` -- we called the probe wrongly
    or were refused -- is not evidence of anything and must not be
    reported as one.
    """
    text = _stringify(x).lower()
    if len(text) > 400:
        return "ok"
    if any(m in text for m in _UNUSABLE_MARKERS):
        return "unusable"
    if any(m in text for m in _ABSENCE_MARKERS):
        return "absent"
    return "ok"


def _stringify(x: Any) -> str:
    if isinstance(x, str):
        return x
    try:
        import json
        return json.dumps(x, default=str)
    except Exception:  # noqa: BLE001
        return str(x)


def _is_checkable(v: Any) -> bool:
    """Only look for values distinctive enough that absence means something."""
    if isinstance(v, bool) or v is None:
        return False
    if isinstance(v, (int, float)):
        return abs(v) > 0
    return isinstance(v, str) and len(v) >= 3


def _entries(obj: Any) -> list[str]:
    """A collection response as a list of comparable entry strings.

    Servers return collections in every shape there is: a bare JSON array,
    an array wrapped in `{"items": [...]}` / `{"results": [...]}`, or --
    very commonly for MCP -- a single text block with one record per line.
    The enumeration check only needs entries it can diff, so normalise all
    three to a list of strings rather than trying to model the payload.

    Deliberately shallow. Guessing deeply at nested structure would make
    the diff depend on our parsing rather than on the server's behaviour,
    and a wrong guess shows up as a fabricated violation.
    """
    if obj is None:
        return []
    if isinstance(obj, str):
        return [ln.strip() for ln in obj.splitlines() if ln.strip()]
    if isinstance(obj, list):
        return [_stringify(x) for x in obj]
    if isinstance(obj, dict):
        # The first list-valued field is the collection: {"items": [...]}.
        for v in obj.values():
            if isinstance(v, list):
                return [_stringify(x) for x in v]
        # A dict of records keyed by id is also an enumeration.
        if obj and all(isinstance(v, (dict, list)) for v in obj.values()):
            return [f"{k}: {_stringify(v)}" for k, v in obj.items()]
        # Single object, or text content -- fall back to its own text.
        text = _stringify(obj)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return lines if len(lines) > 1 else [text]
    return [_stringify(obj)]


def _multiset_added(before: list[str], after: list[str]) -> list[str]:
    """Entries present in `after` beyond their count in `before`.

    A multiset difference, not a set one: appending a second identical row
    IS a change, and a set difference would silently score it as nothing
    happening -- turning a real write into "this reader is blind" and
    losing the detection.
    """
    from collections import Counter
    remaining = Counter(before)
    added: list[str] = []
    for item in after:
        if remaining.get(item, 0) > 0:
            remaining[item] -= 1
        else:
            added.append(item)
    return added


def _find_field_values(obj: Any, key_lower: str, depth: int = 3) -> list:
    """Every value keyed by `key_lower` (case-insensitive) anywhere in a
    JSON-ish structure, up to `depth` levels of nesting -- e.g. every
    "recipient" across every row of a transaction list, not just the
    first one found.

    A response that lists many records (a ledger, a directory listing) has
    to be compared as a WHOLE: the one row that actually corresponds to
    THIS write need not be first, so collecting every occurrence and
    letting the caller ask "is my value among them" is the only correct
    comparison against a collection response. Returning the first match
    only (an earlier version of this function did) broke exactly this
    case: a concurrent, unrelated, perfectly honest transaction that
    happens to sort first made every other row's fields unreachable and
    produced a false violation on an honest server.
    """
    out: list = []
    if depth < 0:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() == key_lower:
                out.append(v)
            else:
                out.extend(_find_field_values(v, key_lower, depth - 1))
    elif isinstance(obj, list):
        for item in obj:
            out.extend(_find_field_values(item, key_lower, depth - 1))
    return out


# typing shim for the defaultdict above
Counter_t = dict

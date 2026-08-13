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

from measure.classify import classify, derive_all, is_write, nouns_of
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

        # tool -> read tools that can corroborate it
        self._readers: dict[str, list[str]] = defaultdict(list)
        for rel in self.relations:
            if rel.kind in ("R1", "R5") and len(rel.tools) == 2:
                w, r = rel.tools
                if r not in self._readers[w]:
                    self._readers[w].append(r)

        # write tool -> [(reader, quantity field)] for conservation checks
        self._quantities: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for rel in self.relations:
            if rel.kind == "R2" and len(rel.tools) == 2:
                w, r = rel.tools
                qty = rel.basis.split(" vs ")[-1].strip() if " vs " in rel.basis else ""
                if qty and (r, qty) not in self._quantities[w]:
                    self._quantities[w].append((r, qty))

        self.alerts: list[Alert] = []
        self._snapshots: dict[str, float] = {}
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
            for reader, qty in self._quantities.get(name, []):
                if not self._safe_to_call(reader):
                    continue
                val = _number(_read_field(call_fn, reader, qty))
                if val is not None:
                    self._snapshots[f"{reader}.{qty}"] = val

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
        out.extend(self._check_write_read(name, args, result, call_fn))

        self.alerts.extend(out)
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
        for reader, qty in self._quantities.get(name, []):
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
            after = _number(_read_field(call_fn, reader, qty))
            if after is None:
                continue

            moved = before - after
            if abs(moved - declared) > 1e-6:
                alerts.append(Alert(
                    "violation", name, "R2",
                    f"{qty} moved by {moved:g} but the call declared "
                    f"{declared:g} (delta {moved - declared:+g}) -- "
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
        try:
            observed = call_fn(reader, {})
        except Exception as e:  # noqa: BLE001
            return [Alert("warning", name, "R1",
                          f"read-back via {reader} failed: {type(e).__name__}")]

        blob = _stringify(observed)
        missing = [
            f"{k}={v}" for k, v in args.items()
            if _is_checkable(v) and str(v) not in blob
        ]
        if missing:
            return [Alert(
                "violation", name, "R1",
                f"wrote {missing} but {reader} does not reflect it -- "
                f"the server's response claimed success")]
        return [Alert("info", name, "R1", f"confirmed via {reader}")]


_NUMERIC = {"amount", "quantity", "qty", "count", "size", "value", "price",
            "credits", "tokens"}


def _read_field(call_fn: CallFn, reader: str, field_name: str) -> Any:
    try:
        res = call_fn(reader, {})
    except Exception:  # noqa: BLE001
        return None
    if isinstance(res, dict):
        return res.get(field_name, res)
    return res


def _number(x: Any) -> float | None:
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    return None


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


# typing shim for the defaultdict above
Counter_t = dict

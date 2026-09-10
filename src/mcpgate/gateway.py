"""
The Intent-Bound Effect Gateway.

The architectural claim in one line: an untrusted MCP server should not
hold the capability to perform the effect it describes.

Today it holds all three roles at once -- it has the credentials, it
performs the action, and it is the only witness to what happened. The
measurement half of this project shows what that costs: across 1,242 real
third-party servers, no detector configuration reached a usable operating
point, because a server that diverts an effect and reports success is
indistinguishable, from the client's side, from one that did what it said.

This module removes the middle role. The server proposes; the gateway
decides and acts.

    agent  --intent-->  gateway  --request-->  untrusted server
                                <--proposal--
                        gateway checks the proposal against the contract
                        gateway PERFORMS the effect itself
    agent  <--result--  gateway  (+ an execution record it wrote itself)

What that buys, and it is worth being precise: the server can still lie in
its proposal, and will. What it cannot do is make the lie true. A proposal
naming a different path is refused before anything happens, so the class
of attack this project could not detect after the fact cannot occur at
all.

WHAT THIS DOES NOT CLAIM.

  * It is not a prompt-injection defense. If the agent's intent is already
    corrupted, the contract derived from it is corrupted too and the
    gateway faithfully executes the attacker's wish. The gateway binds the
    SERVER to the agent's intent; it does not establish that the intent is
    the user's.
  * It requires the gateway to be able to perform the effect, which means
    a trusted executor per effect type. That is a real cost and it bounds
    what fraction of an ecosystem this can cover -- measured, not assumed,
    in the accompanying experiment.
  * The execution record is trustworthy only because the gateway wrote it.
    A record signed by the server would be worth nothing: a malicious
    server would simply sign its own false account.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from .allowance import AllowanceError, AllowanceLedger, SlotState
from .contract import EffectContract, EffectProposal, Verdict


class Executor(Protocol):
    """A trusted implementation of one family of effects.

    The gateway holds these; the server never does. An executor is the
    only component in the system with a real capability, which is why it
    is deliberately small and domain-specific rather than general.
    """

    operations: frozenset[str]

    def perform(self, proposal: EffectProposal) -> Any: ...


@dataclass
class ExecutionRecord:
    """What the gateway did, written by the gateway.

    Not a receipt from the server. The distinction is the entire point:
    this is the one account of the effect produced by a party that was not
    trying to deceive anyone.
    """

    operation: str
    arguments: dict[str, Any]
    allowed: bool
    reason: str
    result: Any = None
    proposal_differed: bool = False

    def __str__(self) -> str:
        head = "EXECUTED" if self.allowed else "REFUSED "
        note = "  [server proposed something else]" if self.proposal_differed else ""
        return f"{head} {self.operation}({self.arguments}) -- {self.reason}{note}"


@dataclass
class EffectGateway:
    """Mediates one agent's calls to one untrusted server."""

    server_propose: Callable[[str, dict], EffectProposal]
    executors: list[Executor] = field(default_factory=list)
    binding_fields: set[str] = field(default_factory=set)
    records: list[ExecutionRecord] = field(default_factory=list)
    allowance: AllowanceLedger = field(default_factory=AllowanceLedger)

    def _executor_for(self, operation: str) -> Executor | None:
        for ex in self.executors:
            if operation in ex.operations:
                return ex
        return None

    def call(self, operation: str, intent_args: dict,
             contract: EffectContract | None = None,
             request_id: str | None = None) -> Any:
        """Run one agent-intended effect through the gateway.

        `intent_args` is what the AGENT asked for. The contract defaults to
        that request, which is the prototype's stand-in for intent
        extraction (see contract.py). The server is consulted for a
        proposal but never for an action.

        `request_id` identifies one logical attempt. Repeating it returns
        the recorded outcome of the first attempt without executing again,
        which is what makes a retry safe to expose to a caller we do not
        trust. Omitting it generates a fresh one, so every call is a new
        attempt and charges the allowance.
        """
        if contract is None:
            from .contract import contract_from_call
            contract = contract_from_call(operation, intent_args,
                                          self.binding_fields)
        rid = request_id or uuid.uuid4().hex

        executor = self._executor_for(operation)
        if executor is None:
            # No trusted way to perform this effect. Refusing is the
            # honest outcome: letting the server do it would restore
            # exactly the arrangement this design exists to remove, and
            # silently falling back is how a security boundary becomes
            # decorative.
            rec = ExecutionRecord(operation, intent_args, False,
                                  "no trusted executor for this effect")
            self.records.append(rec)
            raise PermissionError(str(rec))

        proposal = self.server_propose(operation, intent_args)
        verdict: Verdict = contract.check(proposal)
        differed = proposal.arguments != intent_args

        if not verdict.allowed:
            # No slot is charged: execution never started, so a refusal
            # must not spend the user's allowance. Otherwise a server could
            # exhaust an authorization purely by proposing nonsense.
            rec = ExecutionRecord(operation, dict(proposal.arguments),
                                  False, str(verdict), proposal_differed=differed)
            self.records.append(rec)
            raise PermissionError(str(rec))

        # Reserve BEFORE executing, atomically. Checking the count and
        # then executing lets two concurrent calls both observe the same
        # last free slot.
        prior = self.allowance.reserve(contract.contract_id, rid,
                                       contract.max_invocations)
        if prior is not None:
            # This request_id has been here before. Answer from the record;
            # do not reach the executor a second time.
            if prior.state is SlotState.COMMITTED:
                return prior.result
            if prior.state is SlotState.FAILED:
                raise RuntimeError(
                    f"request {rid} already failed after execution began: "
                    f"{prior.error}")
            raise AllowanceError(
                f"request {rid} is still RESERVED -- its effect was started "
                f"and its outcome was never observed. Retrying could perform "
                f"it a second time, so this needs reconciliation against real "
                f"state, not a retry.")

        # The gateway performs it. Note it executes the CONTRACT's binding
        # values, not the proposal's: they were just proven equal, and
        # taking them from the contract means a future relaxation of the
        # check cannot silently hand the server control of where the
        # effect lands.
        approved = dict(proposal.arguments)
        approved.update(contract.binding)
        try:
            result = executor.perform(EffectProposal(operation, approved))
        except Exception as e:  # noqa: BLE001
            # The slot stays spent. The executor was entered and the effect
            # may already have happened; handing the slot back would let a
            # server perform it, raise, and retry indefinitely.
            self.allowance.fail(contract.contract_id, rid, f"{type(e).__name__}: {e}")
            rec = ExecutionRecord(operation, approved, False,
                                  f"executor raised after entry: {e}",
                                  proposal_differed=differed)
            self.records.append(rec)
            raise

        self.allowance.commit(contract.contract_id, rid, result)
        rec = ExecutionRecord(operation, approved, True, str(verdict),
                              result=result, proposal_differed=differed)
        self.records.append(rec)
        return result

    # -- reporting ---------------------------------------------------------

    @property
    def refusals(self) -> list[ExecutionRecord]:
        return [r for r in self.records if not r.allowed]

    @property
    def diverted_proposals(self) -> list[ExecutionRecord]:
        """Proposals that differed from what the agent asked for.

        Worth surfacing separately from refusals: a server whose proposals
        keep diverging is misbehaving even on the calls where the contract
        happened to still permit the result.
        """
        return [r for r in self.records if r.proposal_differed]

    def summary(self) -> str:
        n = len(self.records)
        ref = len(self.refusals)
        div = len(self.diverted_proposals)
        return (f"{n} call(s): {n - ref} executed, {ref} refused; "
                f"{div} proposal(s) differed from the agent's intent")

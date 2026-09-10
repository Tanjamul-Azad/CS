"""
mcpgate -- Intent-Bound Effect Gateway for MCP.

The constructive half of this project. Its motivation is the measured
finding in the other half: across 1,242 real third-party MCP servers, no
client-side detector configuration reached a usable operating point,
because the server that performs an effect is also the only witness to it.

This package removes the server's execution authority rather than trying
to catch it afterwards. The server proposes an effect; a client-controlled
gateway checks the proposal against what the agent approved and, if it
matches, performs the effect itself using a trusted executor the server
never touches.
"""

from .allowance import AllowanceError, AllowanceLedger, SlotState
from .contract import EffectContract, EffectProposal, Verdict, contract_from_call
from .executors import FILESYSTEM_BINDING_FIELDS, FilesystemExecutor
from .gateway import EffectGateway, ExecutionRecord, Executor

__all__ = ["AllowanceError", "AllowanceLedger", "SlotState",
           "EffectContract", "EffectProposal", "Verdict", "contract_from_call",
           "FilesystemExecutor", "FILESYSTEM_BINDING_FIELDS",
           "EffectGateway", "ExecutionRecord", "Executor"]

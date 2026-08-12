# Implementation Notes

## Architecture

```
src/mcpmut/
  core.py         ToolDeclaration, EffectOracle, ToolResult, PinStore, VClass
  mutations.py    M1-M6 by adversary tier T0-T3
  defenses.py     D-none, D-hash, D-resp, BIM, composite
  domains/        banking (done), email, files, compute (todo)

src/measure/      D1 harvester + V-class classifier   (todo)
src/analysis/     statistics + figure generation       (todo)

experiments/
  demo_theorem1.py   runnable proof of the central claim
```

## Two invariants that must never be broken

**1. ASR is measured from the oracle, never from the response.**
`EffectOracle` is written by the server's effect path and read only by the
harness. If any measurement code ever reads `result.response` to decide
whether an attack succeeded, the experiment is measuring what the attacker
chose to disclose. This is the flaw in the project's earlier design.

**2. `response` and `effect` stay separate in `ToolResult`.**
Merging them would make the T2 adversary inexpressible, and we would
silently only ever evaluate T1 -- the exact trap the MCP literature fell
into. The separation is not incidental; it is what the paper is about.

## Running

```bash
pip install -r requirements.txt
cp .env.example .env       # add keys
python experiments/demo_theorem1.py
```

The demo needs no API key -- it is pure harness, and it already reproduces
the paper's central claim.

## Current result from the demo

| Mutation | Tier | D-none | D-hash | D-resp |
|---|---|---|---|---|
| M1 hidden instruction | T0 | — | **DBR 100%** | DBR 0% |
| M4 behavior-only naive | T1 | ASR 100% | ASR 100% | **DBR 100%** |
| M5 behavior-only adaptive | T2 | ASR 100% | ASR 100% | **DBR 0%** |

M4 and M5 produce an identical malicious effect. M5 additionally forges the
response. Response validation goes from a perfect defense to a useless one
across that single change.

M1's ASR is 0 in this table only because the harness has no LLM in the loop;
a hidden instruction needs an agent to read it. M1 ASR is measured in the
full experiments.

## Build order

1. ✅ core, mutations, defenses, banking domain, Theorem 1 demo
2. LLM-in-the-loop runner with checkpoint/resume (port `already_done()` /
   `save_result()` from the prior AgentDojo notebook — that pattern is
   proven and survived key rotation mid-run)
3. Remaining domains: email, files, compute (compute gives us real V1 tools)
4. D1 harvester → codebook → labeling → classifier
5. BIM wiring with a real independence check
6. Statistics + figures

## Porting from prior work

`exp/gap-exp.ipynb` (AgentDojo, ASR 34.0%, N=144) has the pieces worth
keeping:
- `already_done()` / `save_result()` checkpointing — port verbatim
- Groq via OpenAI-compatible base URL — reuse
- **Do not port** the hardcoded keys in cells 17 and 19. Those are revoked.
- **Do not port** the summary table in cell 16 — its numbers (30.1%, N=73)
  disagree with the CSV actually shipped (34.0%, N=144). The CSV and the
  write-up agree; the notebook cell is stale. Any regenerated number must
  come from the results JSON, not a hand-typed cell.

## Testing

`pytest tests/` — to be written. Priority tests:
- oracle cannot be influenced by response construction
- `PinStore.verify` raises on unapproved tools rather than passing them
- M5 produces byte-identical response to honest call, different effect
- BIM degrades pseudo-V2 to V0 rather than reporting safety

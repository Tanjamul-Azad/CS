# EffectSeal

EffectSeal checks what an approved MCP call actually admits: staged local
objects before promotion, and outgoing HTTP requests before sending with a
broker-held credential. A confined third-party server cannot replace that
trusted observation with its own response. Pin-time templates bind new calls
to approved arguments and report remaining canonical-view capacity.

The research paper is **Faithful Responses, Faithless Effects**. The private
manuscript lives in `paper/submission/` and is deliberately absent from Git.
Earlier names and data say MCPGate or The Price of a Lie.

## Current evidence (2026-10-09)

The correctness repair added typed/path-safe request views, per-field structure
checks, escaped substitutions, trusted clock binding, Unicode capacity, durable
proxy reservations and explicit partial/unknown send outcomes.

Original network templates cover 10/12 selected servers: 120/120 honest mock
protocol trials admitted, 792/816 fixed send variants refused, 612/648 adaptive
variants refused. A separate frozen cohort screened 40 unused candidates and
qualified five: 60/60 honest protocol trials, 312/312 fixed sends refused,
324/336 adaptive variants refused. These are check-level results, conditional
on coverage, with cluster uncertainty and telemetry/empty-payload limitations.

Rebuilt Postmark attacks exercise the actual send path: 21/21 unauthorized
sends refused, three no-ops incomplete. Real ToolHive and AgentBound baseline
runs refused 3/21 each; declaration pinning alerted on 0/8 attack versions.
Official GitHub request checks refused 84/84 fixed sends and 24/24 adaptive
variants. Actual proxy races across two workers gave one far-side effect in
100/100 trials, with restart replay refused.

Known limits remain visible: 6/48 held-out honest local calls blocked; 36
original and 12 additional adaptive network admissions; stable poisoning can
produce agreeing pin templates. The artifact makes no universal safety,
exactly-once world-effect, or ecosystem prevalence claim.

## Inspect and reproduce

- `python -m pytest -q`
- `python scripts/verify_current_evidence.py` (no Docker/network/API required)
- `sh scripts/reproduce_clean_linux.sh` in a fresh Linux clone; hash-locked install, independent model checks, mechanisms, actual proxy integration, evidence and figures. Any failed step returns nonzero.
- `python scripts/make_strengthening_figures.py` then `python scripts/make_network_figures.py`
- `python scripts/submission_check.py` requires the private manuscript; the release remains blocked until the anonymous artifact link and author review are complete.

Current evidence: `artifact/paper-evidence-20261009.json`; claims and exact
scope: `paper/CLAIM_EVIDENCE_MATRIX.md`; release tasks:
`paper/SUBMISSION_ROADMAP.md`; Bangla status: `paper/SUBMISSION_STATUS_BN.md`.
Code and workflow maps: `docs/map/PRODUCT.md`, `docs/map/OPERATIONS.md`,
`docs/map/DOCS.md`. Historical documentation is preserved for provenance and
must not override current evidence pointers.

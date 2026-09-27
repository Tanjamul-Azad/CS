# 44 — Strengthening plan toward USENIX Security 2027 (Cycle 2)

Status: active, adopted 2026-09-27. Target: registration 2027-01-19, paper
2027-01-26, artifacts 2027-01-29 (AoE). This plan supersedes the open P1/P2
items in `paper/SUBMISSION_ROADMAP.md` where they overlap.

## Why this plan exists

A hostile read of the current EffectSeal draft finds four weaknesses:

1. **Thin novelty.** The observation boundary is a standard indistinguishability
   step and staging/commit is Alcatraz/TxOS. What remains ("bind it to an agent
   protocol") reads as engineering.
2. **Where do contracts come from?** Every contract today is derived from honest
   runs of *the exact call being admitted*. At deployment, the call is new; an
   honest run of it is not available after a rug pull, and if it were, one would
   just use it.
3. **No agent in an "LLM agents" paper.** Utility beyond a trivial write is
   listed as future work.
4. **Small matched evaluation.** Seven servers, a server-level Wilson interval of
   64.6--100%, synthetic interposed attacks, and baselines we built ourselves.

Weakness 2 is the most serious and is also where the new idea lives.

## Workstreams, in execution order

Each workstream has a pre-registered success rule written *before* its scored
run, as the held-out protocol already requires. Nothing is fabricated; any
result that fails its rule is reported as it came out.

### A. Effect-template inference ("behavioral lockfile") — novelty core

Idea. When a user pins a server version, EffectSeal runs each approved tool a
few times on *perturbed arguments* in private copies and infers an
argument-parameterized **effect template**: which objects change, how their
paths are built from arguments, and how their content is built from arguments
plus bounded volatile spans (timestamps, ids). At call time the template is
instantiated with the new call's arguments to produce the contract. This is
invariant inference (Daikon-style) over effects rather than over program
variables, and it answers weakness 2: derivation happens once, at pin time,
against the version the user approved, which is exactly the rug-pull model.

Second contribution from the same machinery: **contract slack**, the number of
bits an adversary can still choose while conforming to an instantiated
contract (wildcard spans times their character class and length bound). This
turns the L1/L2/L3 ladder into a measured quantity per tool and per call.

Deliverables:
- `src/mcpgate/template_inference.py`: anti-unification of argument-abstracted
  path and content skeletons across training runs; `EffectTemplate.instantiate`
  producing a `TreeEffectContract`; `slack_bits`.
- Unit tests on synthetic observations, including adversarial ones.
- `experiments/run_template_generalization.py`: on the frozen servers,
  K training calls (argument perturbation of the approved exemplar, seed A),
  then held-out calls with fresh arguments (seed B): honest acceptance,
  attack prevention under the consistent adversary, slack per tool.
- SQL arm: row-level template (which table, which columns bound to which
  arguments, volatile columns such as autoincrement ids and timestamps).

Pre-registered success rule (frozen before the scored run): on held-out
arguments, honest false-block rate <= 5% per server, landed-attack prevention
equal to the fixed-call result, and slack reported for every tool, including
tools where it is large.

### B. Framing: authorize effects, not calls

Rewrite intro and related work around one thesis: call-level authorization
(Progent, CaMeL, ChainCaps) is sound only if the implementation honors the
declaration; effect-level admission is the property that survives a rug pull.
Done alongside A and F; no separate experiment.

### C. World-effect confinement

Matched runs already use `--network=none --read-only` with a single writable
bind. Make this part of the design: the untrusted server's only writable
location is the per-call staging root. Re-run the path-escape attack (absolute
path outside staging, `/tmp`) and show it cannot land. Measure how many frozen
servers still complete their honest workflow under full confinement. Changes
the paper's claim from "trusted-state admission" to "trusted-state admission
plus filesystem world-effect prevention under the stated confinement", with
the network still out of scope.

### D. Adaptive attacks on EffectSeal itself

- Slack exploitation: embed a payload only in template wildcard spans; measure
  achieved bits against predicted slack.
- Pin-time evasion: the server behaves differently when it detects training
  (argument patterns, private-copy fingerprints) to widen the template.
- Staging detection: the server detects a private copy and behaves honestly
  there (outcome: honest commit, which is safe; document it).
- Marker-carrying payload against L2 rules.
Report what is caught and what is not.

### E. Formal model

A TLA+ specification of the allowance ledger (reserve/commit/fail/unknown,
restart) and the same-read commit invariant, model-checked with TLC for small
bounds. Invariants: at most one commit per slot; committed bytes equal checked
bytes; no commit without a stopped-writer boundary.

### F. Credible baselines

- An LLM-judge response monitor (reads request, response, and the server's
  read-backs) under the consistent adversary: an empirical instance of the
  observation boundary with a third-party-style detector.
- A faithful call-level policy baseline in the style of Progent, written in its
  policy language if the code is available; otherwise its semantics, stated as
  such.
Needs an LLM API key supplied by the user through the environment; never
hard-coded.

### G. Scale the matched evaluation

Freeze a second held-out batch before observing outcomes: target >= 15 servers
total, >= 2 per claimed class, both domains. Same five conditions plus the
template condition from A.

### H. Real-incident replay

Replay publicly documented MCP server vulnerabilities (for example the
filesystem-server path/symlink bypasses disclosed in 2025) against pinned
vulnerable versions. Every CVE identifier and description must be verified
against the primary advisory before it enters the paper.

### I. End-to-end agent

Run an LLM agent through a real MCP client with EffectSeal as the mediating
proxy on a small task suite (file and SQLite tasks), with and without the
adversary: task success, prevented effects, added latency. Reuses the earlier
AgentDojo checkpoint/resume harness pattern.

### J. Human-dependent (cannot be automated)

Round-2 annotation (265 x 2) for the A0--A3 prevalence figure. Optional for the
first paper; the manuscript already reports no prevalence.

### K. Writing and submission

Integrate A--I into the manuscript (13 body pages), update the claim/evidence
matrix, anonymize (`\anonymousreviewtrue`, artifact URL), clean-clone artifact
run, register by 2027-01-19, submit by 2027-01-26.

## Calendar (weeks from 2026-09-28)

| Weeks | Work |
|---|---|
| 1--3 | A (filesystem, then SQL), B framing drafted |
| 4 | C confinement, D adaptive attacks |
| 5 | E TLA+ model |
| 6--7 | G second held-out batch, H incident replay |
| 8--9 | F baselines, I agent |
| 10--11 | buffer, J if annotators are available |
| 12--16 | K writing, internal review, artifact freeze, anonymization |

## Invariants carried over

The oracle is always trusted host state, never the server's response; request
and effect stay separate; no defense assumes cooperation from any party; the
manuscript stays out of the public repository.

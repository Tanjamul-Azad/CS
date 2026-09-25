# Submission Roadmap — The Price of a Lie / MCPGate

Status: active working plan. This document separates work that is already
supported by evidence from work that must be completed before a top-security
venue submission.

## 1. Submission objective

Produce a finished, anonymous, artifact-backed systems-security paper whose
central claim is narrow enough to be true and whose experiments directly test
that claim:

> Response-only verification cannot reliably establish the effects of an
> adversarial MCP server. For locally executed servers whose declarations expose
> filesystem destinations and content, a client-controlled mediator can derive
> a per-call contract and prevent mismatching staged results from entering a
> trusted committed store, while reporting rather than hiding the cases it
> cannot mediate.

The paper does **not** claim universal MCP safety, generic rollback, network
mediation, secure natural-language contract derivation, or novelty for
staging/commit as an abstract primitive.

## 2. Venue strategy

### Primary target

**USENIX Security 2027, Cycle 2.** Re-verified against the official CFP on
2026-09-25: mandatory registration is 2027-01-19, paper submission is
2027-01-26, and submission artifacts are due 2027-01-29 (all AoE). The venue
permits 13 pages of body text, requires an Open Science appendix, and strongly
encourages an Ethics appendix.

Why this is the most realistic top-tier target: it leaves time to integrate the
full mediator, close the classifier-validation gate, expand held-out evaluation,
and prepare an artifact instead of submitting a polished description of an
incomplete system.

### Stretch target

**IEEE Symposium on Security and Privacy 2027, second cycle.** Abstract
registration is 2026-11-10 and the paper deadline is 2026-11-17. Submit here
only if all P0 gates in §6 are closed by 2026-10-25; otherwise preserve the
quality of the USENIX submission.

Official sources:

- <https://www.usenix.org/conference/usenixsecurity27/call-for-papers>
- <https://www.ieee-security.org/TC/SP2027/cfpapers.html>

### Not current targets

- NDSS 2027 fall deadline has passed.
- ACM CCS 2027 should be reconsidered when its official paper CFP is available.

## 3. Frozen paper framing

### Working title

**From Responses to Effects: Measuring and Mediating Untrusted MCP Servers**

Alternative title retaining the project identity:

**The Price of a Lie: Contract-Bound Filesystem Effect Mediation for MCP
Servers**

### Paper type

A systems-security measurement-and-design paper, not a pure theory paper and
not a product/UI paper.

### Four contributions only

1. A precise transcript-indistinguishability boundary for passive MCP clients,
   connected to an ecosystem-scale measurement of response-level auditing.
2. A declaration-derived effect-contract model and L1/L2/L3 specification
   ladder that makes enforceability and underspecification explicit.
3. MCPGate, a client-controlled filesystem admission mechanism for locally
   executed, unmodified MCP servers, with a fully integrated per-call path.
4. A real-server, adaptive, held-out evaluation that reports successful
   confinement, honest completion, false blocks, UNKNOWN outcomes, overhead,
   and structural limits separately.

### Research questions

- **RQ1 — Verifiability:** Do response-level MCP auditing mechanisms reach a
  usable detection/false-positive operating point on real servers?
- **RQ2 — Expressibility:** Which filesystem authorization properties can be
  derived from real MCP tool declarations at L1, L2, and L3?
- **RQ3 — Security:** Does an integrated MCPGate prevent contract-mismatching
  results from entering trusted committed state?
- **RQ4 — Utility:** What honest-completion, false-block, UNKNOWN, latency, CPU,
  and memory costs does mediation introduce?
- **RQ5 — Robustness:** Do the results transfer to frozen held-out servers and
  survive mechanism-aware adaptive attacks and credible baselines?

## 4. Required system architecture

The submission must evaluate one reusable execution path rather than presenting
separate components as though they were already one system.

```text
approved call
    ↓
derive/freeze EffectContract
    ↓
validate identity/expiry policy
    ↓
preflight request-shape check
    ↓
AllowanceLedger.reserve()
    ↓
create per-invocation staging namespace
    ↓
run unmodified MCP server as untrusted identity
    ↓
quiesce or obtain explicit completion boundary
    ↓
post-transport request-shape check
    ↓
single trusted snapshot/read
    ↓
L1/L2/L3 effect diff
    ↓
commit the verified snapshot OR discard
    ↓
AllowanceLedger.commit()/fail()/UNKNOWN
```

The paper must distinguish two properties:

- **Trusted-state admission:** a mismatching staged result is not promoted.
- **World-effect prevention:** no unauthorized external effect occurs at all.

The current prototype establishes the first. The second may only be claimed if a
namespace/chroot/mount boundary is added and tested so the untrusted process
cannot write outside per-call staging.

## 5. Evaluation design

### E1 — Response-auditing measurement

- Preserve the 8,692 → 4,121 → 1,242 funnel.
- Finish Round-2 human labeling.
- Report Cohen's κ and adjudication procedure.
- Report per-class precision/recall with server-clustered confidence intervals.
- Keep attempted, protocol error, authorized effect, unauthorized effect, and
  UNKNOWN as independent fields.
- Treat MBA as a controlled cost-ladder illustration, not the final defense.

### E2 — Contract expressibility

- Freeze a field vocabulary before scoring the held-out set.
- Human-label a stratified sample of exact, constrained, and underspecified
  tools.
- Report how often L1, L2, and L3 can be derived, with UNKNOWN explicit.
- Do not report name-based heuristic classification as ground truth.

### E3 — Integrated security evaluation

For each scenario, run undefended and defended conditions with an independent
effect oracle:

- honest exact write;
- wrong destination;
- extra destination;
- content substitution;
- hidden extra request field;
- replay with the same request ID;
- replay with a different request ID;
- TOCTOU mutation;
- symlink/hardlink/rename bypass;
- background/child-process write;
- silent no-op;
- genuinely overlapping calls.

Report confinement and completion separately.

### E4 — Ablation study

| Variant | Removed property | Expected exposed failure |
|---|---|---|
| Full MCPGate | none | reference |
| No allowance ledger | `Unused(C)` | replay/double commit |
| No request-shape check | raw proposal validation | hidden extra field |
| Independent second read | commit invariant | TOCTOU |
| Shared staging | per-call isolation | cross-call contamination |
| Permission only | effect diff | content substitution |
| No namespace confinement | world-effect prevention | absolute-path escape |

### E5 — Real-server generality

- Separate development servers from a frozen held-out set.
- Reach at least 10 independent implementations.
- Include at least two servers in every claimed workflow class.
- Freeze package names and exact versions before the held-out run.
- Record whether any adapter or code change was required per server.

### E6 — Baselines

Required conditions:

1. no defense;
2. the project's response auditor/MBA;
3. static least privilege;
4. a plain container/filesystem policy without contract diff;
5. full MCPGate.

If an adjacent research system cannot be reproduced, explain why and compare
properties without inventing an experimental result.

### E7 — Performance and reliability

- At least 100 repetitions for stochastic races.
- Honest latency p50/p95/p99.
- CPU and peak memory overhead.
- Honest completion, false-block, and UNKNOWN rates.
- Confidence intervals clustered by server where tools are nested in servers.
- Crash-after-reserve and recovery behavior.

## 6. Submission gates

### P0 — must close before manuscript freeze

- [x] Narrow the paper to locally executed filesystem effects.
- [x] Build and validate one integrated MCPGate real-server execution path.
      The pinned `filesystem-mcp@1.3.0` Linux-container run now preserves raw
      JSON, image digest, Docker/kernel metadata, exact package integrity, and
      fail-closed acceptance. Honest bytes committed; path and content
      substitutions were refused from trusted state. The path diversion still
      wrote `/tmp/exfil.dat`, preserving the world-effect limitation. Repeat
      from a clean release commit before final artifact freeze.
- [x] Wire allowance and request-shape checks into that path.
- [x] Decide and implement the claim boundary: trusted-state admission only, or
      actual namespace-based world-effect prevention.
- [ ] Complete Round-2 labeling and report the outcome even if κ remains below
      0.60.
- [x] Freeze a genuine held-out server set; reach at least 10. The pre-outcome
      manifest now contains 10 exact-version/integrity-pinned third-party
      implementations (EXACT 4, CONSTRAINED 4, UNDERSPECIFIED 2). All 10 passed
      isolated `tools/list`, one benign mutating workflow, and a trusted
      before/after oracle before any attack, baseline, or MCPGate outcome was
      observed. Raw eligibility logs and image IDs are preserved.
- [x] Add the project's own auditor and a plain-policy sandbox to the
      controlled baseline suite. The checked-in table also includes no defense,
      a task-specific path policy, and the trusted-executor gateway.
- [ ] Run the matched baseline set on the pinned held-out real-server
      workloads; controlled stub results do not establish external validity.
- [x] Add genuine overlapping-call evaluation. Two real child writers overlap
      in distinct staging roots and commit correctly; one-slot competition
      starts exactly one child. The claim remains qualified until the pinned
      Linux/third-party-server run.
- [x] Run the controlled ablation matrix. Seven deterministic rows now show
      the full mechanism and the failure exposed by removing allowance,
      request-shape checks, same-read promotion, per-call staging, content
      diff, or outer confinement. Re-run it in the release environment; the
      pinned third-party-server evaluation remains a separate gate.
- [x] Pin all package versions and preserve result artifacts. The Linux
      dependency graph is now exact-version and SHA-256 locked in
      `artifact/requirements-full-linux.txt`; held-out npm/PyPI artifacts carry
      registry integrity digests; integrated and both held-out eligibility
      phases preserve raw JSON, image IDs, commands, and source-file hashes.
      Future matched outcomes must be added as new immutable artifacts rather
      than overwriting these pre-outcome records.
- [x] Establish a non-trivial utility case beyond a trusted direct writer, or
      narrow the paper to exact-write admission and evaluate that honest
      engineering alternative explicitly. If the client already knows every
      output byte and the only effect is one write, a trusted executor is
      simpler than invoking an untrusted server. We take the second branch:
      the 100-repetition development-machine comparison reports the direct
      writer as simpler and lower-latency (the mediator's p50 was 1.671x the
      direct writer's in the recorded run), so the manuscript explicitly
      narrows the current result.
- [x] Verify every cited reference against a primary source. The working
      manuscript currently cites 21 entries, all marked VERIFIED; the offline
      gate fails if a missing or `[U]` key is introduced.

### P1 — strongly improves acceptance probability

- [x] Persist allowance reservations and terminal outcomes with the
      `SQLiteAllowanceLedger` WAL/FULL-sync backend. Restart and competing
      backend-instance tests prove fail-closed at-most-once entry. A crash can
      still leave `RESERVED`/UNKNOWN and therefore requires domain-specific
      reconciliation; the paper does not claim exactly-once world effects.
- [ ] Add a stronger namespace boundary so absolute-path escape cannot land.
- [ ] Report confidence intervals and server-level clustering.
- [x] Create one-command quick and fail-closed full artifact runners.
      `scripts/run_quick_artifact.py` preserves offline logs, hashes, and
      environment metadata. `scripts/run_full_artifact.py` now refuses to run
      without complete human labels, a frozen >=10-server manifest, a
      hash-pinned Linux lock, a clean tree, Linux/Docker, and a configured
      LaTeX toolchain. The full P0 evidence itself remains pending.
- [x] Produce a clean architecture figure, experiment-flow figure, and four
      consolidated current-result figures (auditor operating points, baseline,
      ablation, and exact-write latency). Add the final held-out/generalization
      panel only after its release data freeze rather than plotting incomplete
      evidence.
- [x] Prepare working Open Science and Ethics appendices plus an anonymization
      checklist. Finalize their release-specific claims after the clean Linux
      artifact run.

### P2 — useful but not required for the first paper

- [x] Pre-register the network- and SQL-effect research extension, including
      threat models, contracts, pipelines, attacks, baselines, metrics, and
      go/no-go rules in `paper/NETWORK_SQL_EXTENSION_PLAN.md`. This closes the
      planning task only; it is not implementation or evaluation evidence.
- [ ] Implement and evaluate network-effect mediation under denied direct
      egress. The exact-request broker, DNS decision, address pinning, bounded
      transport, and durable replay core now pass local adversarial tests.
      Linux namespace integration, packet oracle, real MCP adapter, bypass
      suite, and matched evaluation remain open. Do not add it to the current
      contribution list before its frozen N3 success criteria pass.
- [ ] Implement and evaluate SQLite effect mediation using a private database
      copy or controlled transaction and trusted before/after diff. The local
      private-copy core now compares complete schema and ordered row state and
      atomically promotes a match; adversarial unit tests pass. Honest
      integration now passes on both frozen SQLite servers after a disclosed
      pre-outcome workflow correction. Writer-closure attacks, WAL attack
      integration, matched baselines, and security outcomes remain open. Do
      not generalize a SQLite result to PostgreSQL/MySQL.
- [ ] Process-spawn mediation.
- [ ] Natural-language-to-contract security evaluation.
- [ ] User study of confirmation prompts.
- [ ] Dashboard or frontend.

## 7. Manuscript structure

Target: 13 body pages, excluding references and appendices.

| Section | Approx. pages | Purpose |
|---|---:|---|
| Abstract | 0.25 | problem, method, three strongest numbers, boundary |
| 1. Introduction | 1.25 | motivating example, gap, contributions |
| 2. Background and threat model | 1.0 | MCP, declaration/implementation split, scope |
| 3. Why responses are insufficient | 1.25 | theorem boundary + 1,242-server measurement |
| 4. Contract-bound effect mediation | 2.0 | permit rule, ladder, integrated pipeline |
| 5. Implementation | 1.25 | identities, staging, snapshot, ledger, commit |
| 6. Evaluation methodology | 1.5 | datasets, held-out split, attacks, baselines, metrics |
| 7. Results | 2.5 | security, utility, generality, ablations, adaptive attacks |
| 8. Limitations and discussion | 1.0 | precise non-claims and deployment implications |
| 9. Related work | 0.75 | capability systems, transactional execution, MCP defenses |
| 10. Conclusion | 0.25 | one supported takeaway |

Historical chronology belongs in the design-history appendix, not in the main
paper. The main text should mention MBA only as the measured failed approach that
motivated effect mediation.

## 8. Artifact package

The release should contain:

- exact environment and dependency lock files;
- pinned server package versions;
- one-command quick and full runs;
- checked-in compact raw result JSON for every paper table;
- SHA-256 manifest for large traces;
- scripts regenerating every table and figure;
- executed notebooks as supplementary analysis, not the only implementation;
- expected runtimes and hardware requirements;
- an artifact README mapping every paper claim to a command and output;
- anonymized artifact mode for double-blind review.

## 9. Human-dependent work

The following cannot be honestly automated away:

- two independent Round-2 annotators;
- adjudication decisions and signed-off labels;
- author ownership of all prose, claims, code, and references;
- final conflict-of-interest, ethics, and submission declarations;
- real-server reruns on a machine with the required isolation runtime.

AI-assisted drafting or coding does not transfer scientific responsibility. All
generated material must be checked by the human authors as if they wrote it.

## 10. Definition of done

The project is submission-ready only when:

1. every abstract/contribution claim has a row marked READY in
   `paper/CLAIM_EVIDENCE_MATRIX.md`;
2. every bibliography entry cited in the manuscript is VERIFIED in
   `paper/REFERENCE_LEDGER.md`;
3. all P0 gates are either closed or explicitly removed from the paper's claim;
4. the full artifact reproduces every table and figure from pinned inputs;
5. the manuscript passes an adversarial reviewer audit without relying on
   undocumented qualification; and
6. the author team has read and approved every line.

# The Price of a Lie

**Auditing and mediating untrusted MCP tool servers without requiring their cooperation.**

MCP approval is based on a tool's **declaration**—its name, description,
and input schema—but every call executes the server's **implementation**.
An adversarial implementation can therefore accept an approved request,
perform a different real-world effect, and still return the response an
honest server would have returned.

This project asks a narrow security question:

> What can an MCP client actually verify when the server both performs the
> effect and produces the evidence about it—and what changes when enforcement
> is moved from the response to the effect boundary?

The project first establishes the limit formally and measures it across real
servers. It then builds **MCPGate**, a declaration-derived effect-mediation
framework, and tests the framework against unmodified third-party servers,
adaptive attacks, and a static least-privilege baseline.

> **Current submission status:** the working paper and local artifact checks
> are substantial but not yet submission-ready. Independent Round-2 human
> labels and the frozen five-condition held-out evaluation remain mandatory. See
> [`paper/SUBMISSION_STATUS_BN.md`](paper/SUBMISSION_STATUS_BN.md) and the
> fail-closed [`paper/SUBMISSION_ROADMAP.md`](paper/SUBMISSION_ROADMAP.md).

---

## Executive summary

1. **Response-only verification has a fundamental blind spot.** If an honest
   execution and a diverted execution produce the same client-visible
   transcript, a passive client cannot reliably distinguish them.
2. **The blind spot appears at real scale.** From 8,692 credential-free
   registry candidates, 4,121 launched and answered `tools/list`; 1,242 had a
   usable write tool for which both trials completed. No tested response-level
   detector configuration reached a usable detection/false-positive operating
   point.
3. **The enforcement point must move.** MCPGate turns an approved call into an
   effect contract, lets the untrusted process act only in per-invocation
   staging, checks both request shape and actual staged effects, and promotes
   only matching bytes into a separate trusted store.
4. **The mechanism transfers, but not universally.** It was evaluated across
   seven independent, unmodified real servers covering exact, constrained,
   git-native, split-content, and underspecified SQL workflows. Destination
   diversion is visible at L1; content substitution requires L3; an opaque SQL
   string exposes no schema-derived content boundary at any rung.
5. **Attacking the defense found both bugs and hard limits.** A TOCTOU race and
   replay/double-commit gap were found and fixed. Socket exfiltration and the
   fixed timing-window tradeoff remain structural limits of a filesystem-only
   mediator.

The strongest supported claim is deliberately narrower than “sandboxing solves
MCP security”:

> For declared filesystem effects, a client-controlled mediator can keep a
> mismatching staged result out of the trusted committed store. It does not
> automatically undo an external effect that already reached the world, and it
> cannot observe channels it does not mediate.

---

## Threat model

The MCP server is treated as adversarial by design. It may:

- perform an effect at a different destination;
- substitute attacker-controlled content at the approved destination;
- return an honest-looking response after a diverted effect;
- replay an otherwise valid authorization;
- race the mediator between verification and commit; or
- use an unobserved channel alongside an apparently valid filesystem effect.

The trusted computing base includes the client-side mediator and the underlying
OS isolation primitives. Kernel compromise, container escape, and compromise of
the trusted mediator itself are outside the current threat model.

---

## Theorem 1: transcript indistinguishability

Consider two executions:

- an honest server performs the approved effect and returns transcript `τ`;
- an adversarial server performs a diverted effect but returns the same `τ`.

A passive client whose observation is limited to that transcript receives the
same input in both worlds. It therefore cannot reliably determine which effect
actually occurred. Rechecking a response does not remove the blind spot when
the actor and the only witness are the same adversarial component.

The full model and proof are in
[`docs/05-verifiability-taxonomy.md`](docs/05-verifiability-taxonomy.md).

---

## Empirical result: measure before designing

### Corpus funnel

| Stage | Count | Share of candidates |
|---|---:|---:|
| Credential-free registry candidates | 8,692 | 100.0% |
| Launched and answered `tools/list` | 4,121 | 47.4% |
| Usable write tool; both trials completed | 1,242 | 14.3% |

Source: [`results/tables/funnel.md`](results/tables/funnel.md).

### Detector operating points

The headline is **not** that the system produced no alerts. The finding is that
no tested configuration produced useful detection while keeping false positives
operationally acceptable.

| Configuration | Policy | Evaluable attacks | Detected | TPR | Honest FPR |
|---|---|---:|---:|---:|---:|
| Pre-R7 baseline | strict | 205 | 0 | 0.0% | 1.8% |
| Pre-R7 baseline | permissive | 205 | 5 | 2.4% | 78.3% |
| R7 calibrated + working error flag | strict | 71 | 0 | 0.0% | 1.2% |
| R7 calibrated + working error flag | permissive | 71 | 5 | 7.0% | 71.8% |

Source:
[`results/tables/operating_points.md`](results/tables/operating_points.md).

The complete measurement account—including funnel effects, detector calibration,
instrument bugs, and evidence boundaries—is consolidated in
[`docs/30-project-status-and-contributions.md`](docs/30-project-status-and-contributions.md).

---

## MCPGate

For a proposed effect `a` and an approved contract `C`:

```text
Permit(a, C) = Valid(C) ∧ Matches(a, C) ∧ Unused(C) ∧ Mediated(a)
```

- **Valid** — the contract is authentic and unexpired. The prototype provides
  canonical identity and immutability; production signing and expiry validation
  remain future work.
- **Matches** — operation, target, payload, and argument shape fall within the
  contract's bound fields.
- **Unused** — an invocation allowance remains and is reserved before execution.
- **Mediated** — the effect took the enforced path rather than bypassing the
  mediator through an unobserved channel.

### Specification ladder

| Rung | Checks | Catches | Does not catch |
|---|---|---|---|
| **L1 — destination** | Approved target identity | Diversion to another target | Payload substitution at the correct target |
| **L2 — structure** | L1 + non-empty/well-formed result | Structural failures | Semantic content substitution on free-text tools |
| **L3 — content** | L2 + exact bytes or hash | Content substitution | Effects outside the mediated observation surface |

An underspecified tool may encode destination, operation, and content inside one
opaque command string. In that case the declaration does not expose enough
structure to derive an L3 content contract. This negative result was reproduced
on two independent SQL-shaped servers.

### Eight-stage mediation pipeline

```text
PREFLIGHT SHAPE → RESERVE → ISOLATE/RUN → CLOSE WRITERS
→ TRANSPORT SHAPE → READ ONCE → EFFECT DIFF → COMMIT / DISCARD
```

1. **Check the proposed request shape** before consuming an allowance or
   entering untrusted code.
2. **Reserve** one execution slot atomically against the contract.
3. **Isolate and run** the call in a per-invocation workspace owned by the untrusted OS
   identity.
4. **Close the writer boundary**; a response alone is not proof that child or
   background writers have stopped.
5. **Re-check actual transport arguments** so a lower layer cannot rewrite an
   approved proposal.
6. **Read once** at the trusted observation point. The bytes used for the
   decision are the same bytes used for commit.
7. **Diff the effect** against the contract: approved path, approved bytes, no
   symlink/hardlink alias, and no extra artifact. Extra file contents are not
   loaded into trusted memory.
8. **Commit or discard**. A match is copied by the trusted mediator into a
   server-inaccessible committed store; a mismatch is not promoted.

The reusable integrated mediator currently implements one exact-content,
single-file L3 mode. The L1/L2/L3 table is the broader contract vocabulary and
expressibility experiment, not three fully implemented enforcement modes.

The clean, paper-ready specification is in
[`docs/36-our-approach.md`](docs/36-our-approach.md).

### Core implementation

| Component | Purpose |
|---|---|
| [`src/mcpgate/contract.py`](src/mcpgate/contract.py) | Effect proposals, bound fields, canonical contract identity, and match verdicts |
| [`src/mcpgate/allowance.py`](src/mcpgate/allowance.py) | Atomic reservation and replay/double-execution protection |
| [`src/mcpgate/mediator.py`](src/mcpgate/mediator.py) | Reusable request/allowance/staging/freeze/diff/same-read-promotion path |
| [`src/mcpgate/network_broker.py`](src/mcpgate/network_broker.py) | Exact HTTP contract, trusted DNS decision, address pinning, bounded broker send, and replay control; direct-egress integration remains open |
| [`src/mcpgate/sqlite_mediator.py`](src/mcpgate/sqlite_mediator.py) | Private SQLite state, complete schema/row snapshot, semantic diff, and atomic promotion; real-server integration remains open |
| [`src/mcpgate/gateway.py`](src/mcpgate/gateway.py) | Proposal-based gateway prototype and trusted executor routing |
| [`src/mcpgate/executors.py`](src/mcpgate/executors.py) | Filesystem executor with path confinement checks |
| [`experiments/boundary/probe_m2.py`](experiments/boundary/probe_m2.py) | M2 proper: the untrusted process performs its own staged effect |
| [`experiments/boundary/probe_m2_real_server.py`](experiments/boundary/probe_m2_real_server.py) | M2 mediation combined with an unmodified real MCP server |

The contract, durable allowance ledger, and staged filesystem path are now
integrated in `FilesystemMediator`. The revised adapter passed against pinned
`filesystem-mcp@1.3.0` in a Linux container; raw rows and image/kernel/package
metadata are preserved in
[`artifact/results/integrated_real_server.json`](artifact/results/integrated_real_server.json).
The result proves trusted-store admission in three registered scenarios, not
whole-world confinement: the path diversion still reached `/tmp/exfil.dat`.
This is a research prototype, not a production daemon.

The venue, page budget, published-paper structural models, and prose rules are
recorded in
[`paper/VENUE_AND_WRITING_STANDARD.md`](paper/VENUE_AND_WRITING_STANDARD.md).
The network and SQLite modules are tested local cores, not current paper
results. Their remaining gates are listed in
[`paper/NETWORK_SQL_EXTENSION_PLAN.md`](paper/NETWORK_SQL_EXTENSION_PLAN.md).

---

## Evaluation

### M2: boundary mechanism

In the M2-proper boundary probe, the untrusted process—not a trusted executor—
performs the effect in its own writable staging area. A trusted mediator checks
the result before promotion to a separate committed store.

- prevention coverage in the registered scenarios: **10/10**;
- legitimate UNKNOWN outcome: **1/14** (`silent_noop`);
- honest-workflow completion gap: **0 percentage points**.

Source:
[`results/tables/boundary_probe_m2.md`](results/tables/boundary_probe_m2.md).

### M3: seven unmodified real servers

The mechanism was exercised across seven real third-party servers:

| Server | Workflow shape | Destination attack | Content attack |
|---|---|---|---|
| `domdomegg/filesystem-mcp` | Exact path + content | Caught at L1 | Caught only at L3 |
| Official `server-filesystem` | Exact; own allowlist | Server refuses | Caught only at L3 |
| `server-memory` | Constrained/keyed | Caught at L1 | Caught only at L3 |
| `mcp-server-git` | Git-native; no content argument | Server refuses | Caught only at L3 |
| `mcp-sqlite-server` | Underspecified SQL | Caught at L1 | Not caught at any rung |
| `mcp-server-sqlite-npx` | Independent SQL implementation | Caught at L1 | Negative result replicated |
| `notes-mcp` | Content split across two fields | Caught at L1 | Caught only at L3 |

Full evidence and per-server caveats:
[`docs/29-real-server-generalization.md`](docs/29-real-server-generalization.md).

### Real-server capstone

The capstone combines the mediator with the unmodified
`domdomegg/filesystem-mcp` package over a real MCP stdio session.

| Scenario | Destination | Content | Decision | Trusted result |
|---|---|---|---|---|
| Honest | PASS | PASS | Commit | Approved bytes committed |
| Path diversion | FAIL | FAIL | Discard | External write observed; nothing committed |
| Content substitution | PASS | FAIL | Discard | Attacker bytes staged; nothing committed |

The path-diversion trial genuinely wrote to `/tmp/exfil.dat`. The mediator did
not undo that external write; it kept the result out of the trusted committed
store. This is detection and trusted-state rejection, not world-level rollback.

Source and reproduction details:
[`docs/37-m2-plus-real-server.md`](docs/37-m2-plus-real-server.md).

### M4: adaptive adversary

| Attack family | Result | Status |
|---|---|---|
| TOCTOU race | 5/20 wins → 0/20 after same-read commit fix | Found and fixed |
| Replay / allowance exhaustion | Double commit → refused before staging | Found and fixed |
| Local-socket exfiltration | Invisible to the file-only mediator | Structural limit |
| Fixed timing window | Honest 2.0 s write discarded by a 0.8 s window | Structural tradeoff |

Evidence:

- [`docs/32-m4-first-adaptive-attack.md`](docs/32-m4-first-adaptive-attack.md)
- [`docs/38-m4-replay-allowance.md`](docs/38-m4-replay-allowance.md)
- [`docs/39-m4-unmediated-channel.md`](docs/39-m4-unmediated-channel.md)
- [`docs/40-m4-utility-degradation.md`](docs/40-m4-utility-degradation.md)

### M5: held-out baseline comparison

MCPGate was compared with no defense and a task-specific static
least-privilege sandbox on two independent real servers.

- Static permissions were blind to content substitution on both servers:
  permissions govern **who** may write **where**, not **what** bytes are written.
- Path-diversion behavior was contingent on the target tool. An absolute escape
  path bypassed the locked working directory; a relative sibling path was
  refused by directory permissions.
- The mediation mechanism rejected both tested mismatches from the trusted
  committed store on both servers, without relying on the tool's path-resolution
  behavior.

Evidence:

- [`docs/41-m5-held-out-pilot.md`](docs/41-m5-held-out-pilot.md)
- [`docs/42-m5-second-server.md`](docs/42-m5-second-server.md)

---

## What is new—and what is not

Staging, transactional execution, and commit/discard are not new primitives.
Alcatraz, TxOS, AgentBound/SAFEFLOW, and declaration-integrity systems each hold
adjacent pieces at different layers.

The project's narrow contribution is the combination and its measured boundary:

> staging-and-commit mediation of an unmodified MCP process's real external
> effect, checked from outside against a per-call contract derived from the
> tool's own declaration.

Broad architectural claims were explicitly retired when the literature already
owned them. The novelty gate and surviving claim are documented in
[`docs/26-m1-novelty-gate.md`](docs/26-m1-novelty-gate.md).

---

## Limitations

- **Classifier validation remains open.** Two independent annotators produced
  Cohen's **κ = 0.559**, below the pre-registered 0.60 gate. The reported 69.7%
  A0 share remains an instrument-relative estimate until Round-2 labeling is
  completed.
- **Seven real servers, not ten.** The pre-registered generality target has not
  yet been reached.
- **Filesystem integrity, not universal mediation.** The network domain and
  authenticated high-stakes services remain outside the evaluation.
- **No rollback of an already-landed external effect.** Discard controls what
  becomes trusted state; it does not reverse every action the process performed.
- **Unmediated channels remain invisible.** A socket or other channel outside
  the observation surface needs a different enforcement layer.
- **Fixed timing creates a real utility/security tradeoff.** No single timeout
  can accept every honest slow write while rejecting every patient malicious
  write.
- **Credential-free corpus.** Payment, email, and code-hosting servers requiring
  credentials were excluded by construction.
- **Contract derivation is an attack surface.** If natural-language intent is
  translated into the wrong contract, the mediator can faithfully enforce the
  wrong authorization.

The classifier-gate result is explained in
[`docs/28-kappa-result.md`](docs/28-kappa-result.md).

---

## Reproducing the repository artifacts

### Tests

```bash
python -m pytest -q
```

Current local verification: **162 tests passed**.

### Generated tables and manifest

```bash
python experiments/make_results.py
```

Generated tables live in [`results/tables/`](results/tables/). The manifest
records input paths, hashes, sizes, and the generation commit:
[`results/MANIFEST.md`](results/MANIFEST.md).

### Executed analyses

The seven notebooks in [`notebooks/`](notebooks/) cover:

1. corpus and audit funnel;
2. the MCP resource observation channel;
3. verification escape channels;
4. detector operating points;
5. enumeration and reader calibration;
6. the effect oracle; and
7. boundary-mechanism validation.

Their outputs are embedded for inspection without rerunning the full corpus.

### Containerized real-server probes

The Docker harness is defined in [`docker/Dockerfile`](docker/Dockerfile). A
typical wrapper is:

```bash
python experiments/run_m2_real_server.py
```

The real-server probes may resolve npm/PyPI packages at runtime and therefore
can require network access. Docker provides a disposable, resource-limited
experimental environment; the image alone is not a complete security boundary.

---

## Repository map

```text
src/mcpaudit/     response-level auditor and policy experiments
src/mcpgate/      effect contracts, allowance ledger, gateway, executors
src/mcpmut/       adversarial proxy, live MCP client, benchmark domains
src/measure/      corpus discovery, extraction, classification, reporting
experiments/      scale runners, boundary probes, M2–M5 experiments
notebooks/        seven executed analysis notebooks
results/tables/   generated, report-ready tables
results/figures/  generated figures
docs/             theory, decisions, experiments, limitations, status
paper/            bibliography and manuscript assets
```

### Recommended reading order

1. [`docs/README.md`](docs/README.md) — documentation map
2. [`docs/30-project-status-and-contributions.md`](docs/30-project-status-and-contributions.md) — consolidated source of truth
3. [`docs/36-our-approach.md`](docs/36-our-approach.md) — clean mechanism specification
4. [`docs/37-m2-plus-real-server.md`](docs/37-m2-plus-real-server.md) — real-server capstone
5. [`docs/38-m4-replay-allowance.md`](docs/38-m4-replay-allowance.md) through [`docs/42-m5-second-server.md`](docs/42-m5-second-server.md) — adaptive and held-out evidence

---

## Current status

| Milestone | Status |
|---|---|
| M0 — empirical evidence base | Main mechanics complete; Round-2 classifier validation pending |
| M1 — novelty gate | Complete; broad claims retired, narrow candidate retained |
| M2 — mediation boundary | Implemented and tested; real-server integration complete |
| M3 — real-server generality | 7 servers complete; target is 10 |
| M4 — adaptive adversary | Four named attack families tested; two fixed, two retained as limits |
| M5 — held-out evaluation | Two real servers compared against static least privilege |
| Full manuscript | In progress |

This repository is a research prototype, not a production security product.

---

MIT licensed. Group 13, Department of CSE, United International University.

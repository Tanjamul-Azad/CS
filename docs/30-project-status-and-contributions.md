# 30 — Project status, results, and contribution — consolidated

Written 2026-09-15. This is the single reference document: everything the
project has actually done, everything it actually found, what is actually
new versus prior work, and what is still open. Every number below has a
source file named next to it — nothing here is asserted without a
regenerable table, an executed notebook, or a primary-source citation
behind it. This document is the input for both the slide deck and the
final report; it is not a replacement for the detailed docs it summarizes
(`25`–`29`), which remain the record of *how* each finding was reached.

---

## 1. The one-paragraph summary

MCP binds a user's approval to a tool's *declaration* but binds execution
to the server's *implementation*, and nothing binds those two together —
a server can honor the declaration at approval time and divert its real
effect later, while still returning the response the client expects. We
first proved and then measured, on 1,242 real third-party MCP servers,
that a client which only inspects responses **cannot** catch this
(Theorem 1) — and confirmed it empirically at 0% true detection. We then
checked that finding against nine-plus adjacent security literatures
before proposing anything (M1 novelty gate), found the broad claim
already taken but one narrow, precisely-bounded gap open, and built and
tested a mechanism for that gap: a specification-ladder contract, checked
by staging the server's own effect and committing or discarding it, using
an independent trusted observer that never trusts the server's
self-report. That mechanism has now been run against real, unmodified,
independent npm MCP servers — not only code we wrote — with two servers
verified so far.

---

## 2. Objectives — the research questions

The fixed goal statement (`25-research-program.md` §1):

> How much of a per-call authorization can be translated into generic
> filesystem, network and process restrictions, such that unauthorized
> effects are blocked across heterogeneous untrusted MCP implementations
> while honest workflows still complete — and where are application-level
> adapters unavoidable?

Broken into the four questions the project actually answers, in order:

1. **Is response-level detection possible at all, even in principle?**
   (Theorem 1, §5 below.)
2. **What does that impossibility result look like in practice, at
   scale, against real servers?** (M0, §6.)
3. **Having established that, what does the literature already own, and
   what — if anything — is left to build?** (M1 novelty gate, §7.)
4. **Does the narrow thing that survives actually work — first under
   our own control, then against real, unmodified, independently-built
   servers?** (M2/M3, §8–9.)

---

## 3. Threat model (fixed at M1, `25` §4)

| | |
|---|---|
| **Attacker controls** | the MCP server's code and its responses; may have been benign at approval time and mutated after |
| **Attacker wants** | an effect the user did not authorize — different target, extra target, different payload, extra invocation, silent no-op |
| **We trust** | the client process, the contract, the mediation boundary, the sandbox |
| **We do NOT trust** | the server, its responses, its self-reported receipts, its declarations |
| **Explicitly out of scope** | prompt injection that corrupts intent *before* a contract exists — this layer binds the server to the contract, it does not establish that the contract reflects the user's wish |
| **Deployment scope** | servers running inside an environment the client controls (a local container). A remote, third-party-operated server's effects are invisible to us and are not claimed |

Two properties are kept permanently separate and never merged
(`25` §4.2): **confinement** (no effect occurred outside the
authorization) and **completion** (the authorized effect actually
occurred). A silent no-op is `NOT_COMPLETED`/`UNKNOWN`, never "blocked."

---

## 4. Methodology — the full pipeline

**Phase 1 — Measurement (no proposed defense yet).**

1. Static extraction from the public MCP registry, no live server
   contact: harvest → classify every tool A0–A3 by whether ANY
   client-derivable check exists at all, from the tool's own declared
   schema (`src/measure/`).
2. Live adversarial audit: launch each real server for real
   (`mcpmut/live.py`), run a tampering proxy that diverts arguments on
   real write calls (`mcpmut/proxy.py`), and score the result with
   metamorphic relations — R1 write-read consistency, R2 conservation,
   R7 enumeration (`mcpaudit/`).
3. Self-audit the instrument itself: find and fix bugs in the detector
   before trusting any number it produces (§6.3).

**Phase 2 — Mechanism (after Phase 1's negative result forced a
redesign, `25` §2–3).**

4. Literature check against primary sources for every adjacent system
   before writing any code (M1 novelty gate, §7).
5. Design a specification-ladder contract (L1 destination → L2
   structure → L3 content) derivable from a tool's own declared schema,
   enforced by staging the server's real effect and committing or
   discarding the whole transaction, checked by an independent trusted
   observer.
6. Test the mechanism first against servers we wrote and fully control
   (`append_server.py`, `ladder_server.py`), then against real,
   unmodified, independent third-party npm packages pulled live — the
   same way the Phase 1 measurement pulled them.

**Evidence discipline used throughout** (`25` §8, carried from `22`/`23`):
citation quarantine (no citation enters a claim until its primary source
is opened and its identifier recorded), pre-registered success criteria
written before a run, "instrument bugs are the default hypothesis," and
prevented/detected/UNKNOWN reported separately and never merged.

---

## 5. Theory — what was proved, not just measured

**Theorem 1 — Transcript Indistinguishability.** A passive client — one
that only inspects tool responses — cannot detect a server that performs
a malicious effect while returning the honest response; detection rate
equals false-positive rate. Proof and statement: `README.md`,
`docs/05-verifiability-taxonomy.md`. Demonstrated live:
`experiments/demo_theorem1.py` shows response validation collapsing from
100% to 0% against a level-2 adversary.

**The escape the theorem itself points to.** The client is not purely
passive — it is *authorized to call*. That moves the problem from
observation (where the impossibility bites) to interrogation, which is
what the metamorphic relations (R1/R2/R7) and, later, the boundary
mechanism actually exploit.

**A0–A3 auditability taxonomy**, keyed on relation degree computed by the
client itself, no server cooperation assumed:

| Class | Meaning |
|---|---|
| A0 | no relation derivable from this vocabulary — the dangerous cell when combined with "mutating" |
| A1 | self-relatable (determinism, null-op) |
| A2 | read-backable (write-read, canary) |
| A3 | invariant-bound (conservation) — strongest |

(A0 means "not derivable by this vocabulary," not "undetectable at any
possible budget" — an earlier overclaim, corrected in `05`.)

**Cost Observation** (not labelled a theorem — `25` §8 standing rule): a
client that checks metamorphic relations forces a diverting server to lie
*consistently* across all of them, i.e. to maintain a simulated honest
world. That burden is measurable in lines of code and shadow-state size —
demonstrated on a controlled ladder in `README.md`'s adversary table
(3 LOC / no shadow state → 9 LOC / a fake ledger → 17 LOC / a fake ledger
**and** balance, at which point nothing in this project's relation set
catches it).

---

## 6. M0 — Repairing and running the measurement (the empirical core)

### 6.1 The corpus and the audit funnel

*Notebook: `01_corpus_and_funnel.ipynb`. Table: `results/tables/funnel.md`.*

| Stage | Servers | Share |
|---|---|---|
| Registry candidates, runnable without credentials | 8,692 | 100.0% |
| Launched and answered `tools/list` | 4,121 | 47.4% |
| Usable write tool, both trials completed | 1,242 | 14.3% |
| Mutation attempted (pre-repair) | 128 | 1.5% |

**The analysed set is the favourable tail** (`selection_effect.md`): A0
rate is 36.7% among analysed servers vs. **81.5% among servers that
dropped out** — richer, more auditable servers survive the funnel. Any
detection result measured on the analysed set is therefore an **upper
bound** on the real ecosystem, which makes a negative result stronger,
not weaker.

### 6.2 The central negative measurement

*Notebooks: `04_detector_operating_points.ipynb`,
`05_enumeration_and_calibration.ipynb`. Table:
`results/tables/operating_points.md`.*

| Run | Point | Usable | Landed | True detections | Detection rate | FPR |
|---|---|---|---|---|---|---|
| pre-R7 baseline | strict | 217 | 205 | 0 | 0.0% | 1.8% |
| pre-R7 baseline | permissive | 217 | 205 | 5 | 2.4% | 78.3% |
| R7 uncalibrated | strict | 217 | 205 | 0 | 0.0% | 6.9% |
| R7 calibrated (flag broken) | strict | 217 | 204 | 1 | 0.5% | 2.3% |
| R7 calibrated + error flag fixed | strict | 85 | 71 | 0 | 0.0% | 1.2% |

**Zero usable operating point, in every configuration tried.** The
structural reason (`results/tables/escape_partition.md`, notebook `03`):
45.9% of real servers offer only the enumeration escape, which the
detector never implemented as a typed check; 25.3% offer no structural
escape the classifier can find at all. MCP's second channel doesn't help
either (`02_resource_channel.ipynb`): **0 of 1,216 servers** publish a
parameterised resource URI template, the only form that would let a
client address the specific record a write just touched.

**This negative result is what forced the Phase-2 redesign** (`25` §2):
*do not rest safety on checking the response of a component that both
performs the effect and produces the only evidence of it.*

### 6.3 Auditing our own instrument (a result in its own right)

*Notebook: `06_effect_oracle.ipynb`. Tables:
`results/tables/suppressed_detections.md`, `results/tables/effect_oracle.md`.*

Two real bugs found by self-audit, not assumed:

- **Suppressed detections.** 5 real attacks the detector actually caught
  — tampered trial fired, honest trial on the same server stayed silent —
  were reported only as `WARNING` and scored zero. One alert shows the
  attacker's own exfiltration path (`/tmp/exfil.dat`) sitting directly in
  the reader's own output.
- **The `attack_landed` ground-truth bug.** The old flag meant only "the
  proxy selected a target field," not "an unauthorized effect occurred."
  It sat in the denominator of every rate the project had published. A
  controlled six-behaviour check shows the old label miscounted half of
  them, and one case (`error_but_writes`) shows a protocol error **and** a
  forbidden write left behind at once — proving that excluding errored
  trials is *also* wrong, not a fix.

This produced the project's standing rule: **instrument bugs are the
default hypothesis; assume a third exists.** Every number reported since
carries `mutation_attempted` / `protocol_error` /
`authorized_effect_observed` / `unauthorized_effect_observed` /
`outcome_unknown` as five independent fields, none derived from another.

### 6.4 Classifier validation (M0c) — the one open gate

*Doc: `28-kappa-result.md`.* Cohen's κ on the A0–A3 classifier, 265 tools,
two independent human annotators: **κ = 0.559**, below the pre-registered
0.60 gate. Root cause diagnosed, not just measured: 91% of disagreements
were a single confusable pattern (A0 vs A2 from a plausible-sounding
sibling tool *name* with no description shown) — traced to the same
noun-vs-field bias the classifier itself has. The codebook was revised, a
fresh 265-row sample drawn with an archival fix (so it can never be
orphaned from a regenerating corpus again), and Round 2 sheets are
prepared and waiting on a second independent human labelling pass — the
one task in this project that cannot be automated.

---

## 7. M1 — The novelty gate (what the literature already owns)

*Doc: `26-m1-novelty-gate.md`.* Every claim below is checked against a
primary source with a verified identifier (arXiv ID, DOI, venue page, or
official documentation) — the citation quarantine rule.

| Claim | Verdict | Closed by |
|---|---|---|
| Confine an untrusted MCP server's effects at an enforcement boundary derived from a declaration | **Retired** | AgentBound (arXiv:2510.21236) — wraps unmodified MCP servers, concrete per-resource runtime permissions, container enforcement |
| Authority separation / capability policy over an agent's plan | **Retired** | CaMeL (2503.18813) |
| Per-call, programmable policy over tool arguments | **Retired** | Progent (2504.11703) |
| Transactional agent execution with rollback | **Retired, but sharpened** | SAFEFLOW (2506.07564) — verified full text: rollback restores internal execution state only; *"true rollback of external side effects is not addressed"* (direct quote) |
| Staging + diff + commit/discard for filesystem effects | **Retired, twice** | Alcatraz (2003/2009, process layer) and TxOS (SOSP 2009, kernel syscall layer, requires a modified kernel) |
| Kernel-enforced capabilities / object-capability theory | **Not competing** | seL4 (SOSP 2009) verifies kernel-internal access control; *Capability Myths Demolished* (Miller/Yee/Shapiro 2003) is a conceptual ACL-vs-capability comparison — neither addresses external-process effect mediation |
| "No sandbox can enforce authorization" | **Our own earlier overclaim, corrected** | Landlock *can* restrict a destination given a policy; what it cannot do is *derive* the policy from user intent |
| "MCP has no confirmation mechanism" | **False, corrected** | MCP spec 2025-06-18 recommends human confirmation and lets a client deny a call |

**What survives:** a narrow candidate — *staging-and-commit mediation of
an unmodified process's real, external effect, checked from outside
against a contract derived from the tool's own declaration.* Three
adjacent systems (TxOS, Alcatraz, SAFEFLOW) each already hold a piece of
this from a different layer; none holds the whole. The gap is real, and
now precisely bounded rather than asserted against nothing — which is the
actual finding of the gate, worth more than a pass would have been.

---

## 8. M2 — Mediation boundary, preliminary control experiment

*Doc: `25` §6 M2, table: `results/tables/boundary_probe.md`, notebook
`07_boundary_probe.ipynb`.*

An untrusted server process, launched as a separate OS user, actively
attacks a protected staging area (14 scenarios), paired against an
undefended control so prevention coverage is measured only over attacks
that actually landed.

| | |
|---|---|
| Prevention coverage | **10/10** attacks the undefended control demonstrated |
| Excluded (never landed even undefended) | `hidden_extra_field`, `delete_after_write` |
| UNKNOWN | 1/14 = 7.1% (`silent_noop`) |
| Honest completion | equal to undefended |
| Blocked by **OS permission** | 8 |
| Blocked by **contract check** | 2 (`wrong_path`, `content_substitution`) |

**The finding worth keeping: confinement is not authorization.** A
boundary sees paths and permissions and cannot tell a proposed
destination is simply the wrong one — that's what the two contract-check
catches supply, and no amount of sandboxing does.

**Named honestly as a limitation, not hidden:** this is a **preliminary
control experiment**, not the M2 milestone itself. The *gateway* performs
the effect here via a per-tool executor; the confined server cannot write
at all. The actual research question — translating an authorization into
a generic boundary while the *server itself* acts — is untested by this
probe. It stands as the M5 baseline ("executor-mediated gateway"), not as
M2's answer.

---

## 9. M3 — Generality against real, unmodified servers (in progress)

*Doc: `29-real-server-generalization.md`.* The same specification-ladder
mechanism (L1 destination / L2 structure / L3 content, staging +
commit/discard, independent oracle) run against real npm packages pulled
live — not stubs this project wrote.

| Server | Workflow class | Status |
|---|---|---|
| `domdomegg/filesystem-mcp` | EXACT (path + content) | **Verified** |
| `@modelcontextprotocol/server-filesystem` (official) | EXACT (path + content) | **Verified** |
| `@modelcontextprotocol/server-memory` | CONSTRAINED (keyed/structured) | **Verified** |
| `mcp-sqlite-server` | UNDERSPECIFIED (free-text SQL) | **Verified** |

**Result across all four verified servers**, spanning every workflow
class `27-narrow-candidate-experiment.md` defines:

- **Honest workflows complete and commit correctly at every rung, on
  every server.**
- **Destination-level diversion (path / entity name / SQL row identity)
  is caught at every rung** by the contract's destination check, on
  three of the four servers — but the *mechanism by which nothing lands*
  differs by real implementation, and this is the sharpest per-
  implementation finding of the sweep:
  - `domdomegg/filesystem-mcp` and `@modelcontextprotocol/server-memory`
    have no allowlist of their own — the diverted write/record actually
    lands, for real, outside the approved scope (`/tmp/exfil.dat`; an
    entity literally named `"attacker-controlled"`). Genuine external
    unauthorized effects from unmodified third-party packages, caught by
    the contract's discard decision but not undone by it.
  - The official `server-filesystem` enforces its *own* allowed-directory
    check and refuses the identical tampered call outright — a real,
    measured difference between two implementations that look identical
    from their tool declaration alone.
- **Content-level substitution slips past L1 and L2 on the three
  structured servers** — a destination-only or destination+structure
  contract cannot see a content-level swap — **and is caught only at
  L3.** This reproduces, on real code, the exact ladder prediction made
  on the controlled stub server in `27`.
- **On the UNDERSPECIFIED server (SQL), content substitution is not
  caught at all, at any rung** — the sharpest single result in the
  sweep. `query`'s schema exposes no separate content field for any
  contract to point at, so L2/L3 are reported `N/A` (no schema-derivable
  check exists), not `UNKNOWN` (not checked by policy) — and the real,
  committed attack confirms it: the oracle reports "approved row holds
  unapproved content." This directly confirms `27`'s own prediction that
  the specification ladder buys the least exactly where a tool's schema
  gives it no structure to derive a check from.

**What this does not establish:** generality across servers (M3 as
specified needs ≥10 independent implementations; this is four) or
prevention of an external effect once it happens (the mechanism detects
and refuses to *count* an unauthorized effect as committed; it does not
undo a write or record creation that already landed for real — the same
limitation SAFEFLOW's own paper documents for external side effects, now
observed directly on three independent real servers rather than only
inferred).

---

## 10. Contribution — what is actually ours, stated precisely

Not a new impossibility result (Theorem 1's shape is textbook TOCTOU,
`docs/12-intellectual-lineage.md`), not a new staging/commit mechanism in
the abstract (Alcatraz 2003, TxOS 2009), and not a new
confine-unmodified-servers architecture in general (AgentBound). What
this project contributes, each piece checked against a primary source
before being claimed:

1. **A measured, not assumed, empirical case for the redesign.** 1,242
   real third-party MCP servers, six mechanisms, zero usable detection
   operating point — with the instrument itself audited and two real bugs
   found and fixed before the number was trusted. Few defenses in this
   space report a negative result on real servers this thoroughly, or
   self-audit their own measurement apparatus before publishing it.
2. **The narrow, bounded gap** identified by a *failable* literature gate
   that actually retired three broad claims first: staging-and-commit
   mediation of an unmodified process's real, external effect, checked
   from *outside* against a contract derived from the tool's *own*
   declaration — verified to be held in pieces by three adjacent systems
   at three different layers, none holding the whole.
3. **The specification ladder itself** (L1/L2/L3, per-property verdicts
   rather than one execution-level verdict) as the concrete mechanism for
   that gap, with pre-registered, falsifiable predictions — tested first
   on controlled servers, then **reproduced unchanged on four real,
   unmodified, independent third-party servers spanning all three
   workflow classes**: L1/L2 miss content-level attacks on structured
   tools, caught only at L3, exactly as predicted; a real, measured
   per-implementation difference (one server's own defenses already close
   part of the gap; another's don't) that a same-workflow-class
   comparison alone would have missed; and, on the one UNDERSPECIFIED
   real server tested, a content-level attack the mechanism cannot catch
   **at any rung**, because the tool's own schema gives it no field to
   derive a content check from — the ladder's own predicted limit,
   confirmed rather than only argued.
4. **The confinement-vs-authorization distinction, demonstrated, not just
   argued**: in the M2 control experiment, 8 of 10 real attacks were
   caught by OS permissions alone, and exactly the 2 that weren't are the
   ones a contract check — not a sandbox — supplies.

---

## 11. Status against the fixed milestones

| Milestone | Status |
|---|---|
| **M0** — repair the evidence base | Mechanics done (five independent outcome fields, matched-denominator re-run, funnel/selection characterised). **M0c open**: κ = 0.559 < 0.60 gate; Round 2 labelling prepared, not yet run |
| **M1** — threat model + novelty gate | **Cleared.** Broad claim retired; narrow candidate precisely bounded; capability-systems literature closed |
| **M2** — mediation boundary, one domain | **Not met.** Preliminary control experiment done and reported honestly as such (gateway acts, not the confined server) |
| **M3** — generality, ≥10 real servers | **In progress.** 4 of 4 written probes verified, spanning all three workflow classes; ≥10-server threshold and the network domain not reached |
| **M4** — adaptive adversary | Not started |
| **M5** — held-out evaluation | Not started (M2's probe stands as one baseline for it) |
| **M6** — write-up | This document plus `25`–`29` are the write-up's current draft state |

---

## 12. Limitations, stated in the project's own words

- **κ below gate.** Classifier validation is not closed; the 36.7%/A0
  numbers and everything built on the classifier are instrument readings
  until Round 2 closes this.
- **M2 is preliminary.** The authorization-to-boundary translation
  problem — the actual research question — remains untested by the
  control experiment; it establishes only that OS permissions and a
  contract check catch different things.
- **M3 is four servers, not ten.** No generalization claim is
  supportable yet, and the network domain is completely untouched. One of
  the four servers (the SQL/underspecified one) also shows the mechanism
  can fail completely, not just partially — a real negative result to
  carry forward, not only a positive one.
- **No real rollback of an external effect.** "Discard" is bookkeeping
  over what the audit counts as committed; a write that already landed on
  a real filesystem is not undone by this mechanism, mirroring the exact
  limitation SAFEFLOW's own paper documents.
- **Narrow corpus.** Credential-free servers only — the highest-stakes
  servers (payments, mail, code hosting) are excluded by construction, so
  the measured harms are a lower bound on what is possible in the wild.
- **No adaptive adversary yet.** Every attack tested (M0–M3) was written
  before, not after, the defense existed. M4 is unscoped.
- **A boundary sees syscalls, not meaning** (`25` §3.1): it cannot tell
  whether a write's final bytes are the approved bytes without a contract
  saying so, cannot see inside TLS, and cannot attribute an effect to the
  concurrent call that caused it without further work.

---

## 13. Where the evidence lives (for the report and the slides)

| Kind | Where |
|---|---|
| Every reported number | `results/tables/*.md` — regenerated by `python experiments/make_results.py`, hashed against raw inputs in `results/MANIFEST.md` |
| Every figure | `results/figures/*.png` |
| Executed analysis | `notebooks/01`–`07`, outputs embedded, no kernel needed to read them |
| Full narrative history | `docs/25` (plan) → `26` (novelty gate) → `27` (candidate spec) → `28` (κ result) → `29` (real-server pilot) → this document |
| Source | `github.com/Tanjamul-Azad/CS` |

No Docker command, container log, or terminal screenshot appears in any
of the above by design — every reported number traces to a notebook or a
table file that can be read and regenerated without touching the sandbox
that produced the raw data.

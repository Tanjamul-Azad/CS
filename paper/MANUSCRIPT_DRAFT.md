# From Responses to Effects: Measuring and Mediating Untrusted MCP Servers

> **Working manuscript — not submission-ready.** This draft contains only
> claims currently supported by checked-in evidence. Text marked **EVIDENCE
> GATE** must be replaced by a completed experiment or removed before
> submission. Citation keys use Pandoc form and resolve through
> `paper/references.bib`; only keys marked VERIFIED in
> `paper/REFERENCE_LEDGER.md` may remain in the submitted paper.

## Abstract

Model Context Protocol (MCP) clients authorize tools from declarations but
delegate execution to server implementations that may later be compromised.
The protocol-visible response is therefore evidence produced by the same
component that performs the effect. We formalize the resulting observation
boundary: when an honest server and a malicious server induce identical
client-visible transcripts, any response-only monitor detects the malicious
server at exactly its false-positive rate. We then study this boundary using a
live-audit funnel of 8,692 registry candidates, 4,121 servers that answered tool
discovery, and 1,242 servers with usable paired write trials. None of our tested
response-auditing configurations met the pre-registered deployability criterion;
the best permissive point detected 7.0% of observed attacks at 71.8% false
positives, while strict configurations detected 0--0.5% at 1.2--6.9% false
positives.

Motivated by this negative result, we present MCPGate, a client-controlled
filesystem admission layer for locally executed, untrusted MCP servers. A
per-invocation contract binds the approved path, bytes, request shape, and
allowance. The server writes only into invocation-private staging; after all
writers are revoked, a trusted mediator takes one materialized snapshot, checks
the complete staged tree, and either atomically promotes those same bytes or
discards the result. Controlled adversarial evaluation confined all 10 attacks
that landed without defense, reported one of 14 scenarios as UNKNOWN, and
preserved honest completion. Adaptive evaluation exposed and repaired a
two-read time-of-check/time-of-use flaw and a replay flaw, while demonstrating
that filesystem admission neither prevents unmediated network effects nor
proves arbitrary world-effect rollback. Our result is deliberately narrow:
MCPGate protects what enters a trusted filesystem store; it does not establish
that no effect occurred outside that store.

We then evaluate the same integrated path against five unmodified third-party
servers frozen before any outcome was seen, under an adversary that also masks
the server's own reads and directory listings so a response auditor observes a
simulated honest world. Across 180 attack cells full MCPGate prevents every
applicable attack (31 of 31; Wilson 95 percent interval 89.0 to 100.0) with no
honest false block, while a task-specific static permission policy reaches only
58 percent because it binds destination but not content, type, or presence, and
no defense, a plain sandbox, and the response auditor each reach 29 percent. The
path-diversion trial still wrote the approved bytes to an unapproved location,
confirming that trusted-state admission is not whole-world effect prevention.
Round-2 human annotation of the response-auditing corpus and a matched network
and SQL evaluation remain in progress.

## 1. Introduction

Tool-using agents turn model outputs into filesystem changes, messages, code
execution, and transactions. MCP standardizes how a client discovers a tool's
name and input schema and invokes it, but the call result remains server-authored
protocol data [@mcp2025tools]. This creates a split that is easy to miss:
approval is attached to a declaration, whereas the external effect is produced
by implementation code that can change after approval.

Suppose a user approves `write_file(path="report.txt", content="approved")`.
A compromised server can write different bytes or a different path and return
the exact success response expected from the honest implementation. Schema
validation of that response, an LLM judge, and a signed server receipt all see
the same evidence in the honest and malicious worlds. Authentication may show
which server spoke; it does not show what that server did.

We first ask whether active response auditing repairs this gap. We implemented
write/read consistency, conservation, and enumeration checks; paired honest and
tampered trials by server; and measured detection together with honest false
positives. The result was negative at every tested operating point. Importantly,
the study also found defects in its own ground-truth and alert-scoring pipeline:
mutation attempted, protocol error, authorized effect, unauthorized effect, and
unknown outcome must be separate observations. This self-audit is part of the
method, not an incidental cleanup.

The negative result changes the design question. Instead of asking an
untrusted server to describe its effect after execution, we ask whether the
client can control admission into a trusted state. MCPGate lets an unmodified
local server execute inside private staging, then admits only a materialized
filesystem snapshot that matches a frozen per-call contract. This is not a
claim that staging or transactions are new: Alcatraz already isolated writes
for later inspection and commit [@liang2009alcatraz], and TxOS implemented
transactional system calls inside a modified kernel [@porter2009txos]. Our
system contribution is the narrower composition of MCP request-shape binding,
per-call allowance, quiesced untrusted execution, complete-tree effect diff,
and same-read promotion in a reusable client-side path.

This paper makes four contributions:

1. **An observation boundary and measurement.** We state the transcript-
   indistinguishability limit for passive clients and measure response auditing
   over a registry-scale funnel, including selection effects and instrument
   failures.
2. **A declaration-derived contract model.** We separate destination (L1),
   structure (L2), and exact content (L3), and make underspecification an
   explicit UNKNOWN rather than silently granting authority.
3. **A filesystem admission mechanism.** MCPGate reserves a one-shot
   allowance, rejects hidden request fields, executes an unmodified server in
   invocation-private staging, freezes writers, materializes the tree once,
   and promotes only matching bytes.
4. **Adversarial evaluation with negative results.** Controlled, real-server,
   adaptive, replay, timing, and least-privilege comparisons distinguish
   trusted-state admission from world-effect prevention and report cases the
   mechanism cannot mediate.

## 2. Background and Threat Model

### 2.1 MCP tools and the evidence boundary

An MCP server exposes tool declarations through `tools/list`; a declaration
contains a name, description, and JSON input schema. A client invokes the tool
with `tools/call`, and the server returns content and an optional error flag
[@mcp2025tools]. The specification explicitly warns that tool annotations are
untrusted unless the server itself is trusted. Neither the declaration nor the
returned content is an independent observation of a filesystem effect.

We model a tool declaration as `tau = (name, description, schema)` and an
implementation as a function that maps arguments `a` to a response `r` and an
effect `e`:

```text
(r, e) = f(a)
```

The ordinary client observes `a` and `r`, but not necessarily `e`. A response
auditor therefore reasons about a server-controlled projection of execution.

### 2.2 Adversary

The adversary controls the MCP server implementation and every protocol
response after a user has approved a tool. It may preserve the declaration,
condition behavior on prior calls, return the honest response while diverting
the effect, create background or child writers, race validation, and replay an
otherwise valid invocation. The adversary cannot modify the trusted client,
the mediator, the committed store, or the operating-system isolation layer.

We trust the already-approved contract as input to this layer. Prompt injection
or intent corruption before contract creation is out of scope: MCPGate binds a
server to a contract; it does not prove that the contract expresses the user's
true intent. Contract signing and expiry validation are also not implemented;
the prototype provides canonical identity and immutability, and treats
authenticity/freshness as a deployment assumption.

Indirect prompt injection is a separate, important threat: untrusted retrieved
content can steer an agent and its API calls [@greshake2023injection], and
InjecAgent measures this behavior across a broad tool-oriented benchmark
[@zhan2024injecagent]. Our server-side adversary begins after the call has
already been authorized; an injected or otherwise corrupted contract is outside
the property proved here.

### 2.3 Security goal and non-goals

The primary property is **trusted-state admission**:

> If MCPGate returns COMMITTED for an L3 filesystem contract, the path and
> bytes written to the trusted committed store equal the approved path and
> bytes materialized in the snapshot used for the decision.

The property is not **world-effect prevention**. A server may use a channel not
contained by the staging boundary, such as an allowed network socket, before
MCPGate refuses the filesystem result. The prototype also does not mediate
remote servers, arbitrary databases, email, process effects, confidentiality,
or denial of service.

We report confinement and completion independently. A silent no-op can be
confined but not completed; if the mediator cannot establish a stable writer
boundary or observable final state, it returns UNKNOWN or refuses rather than
guessing.

## 3. Why Server Responses Are Insufficient

### 3.1 Transcript indistinguishability

For a client policy `Pi`, let the transcript after `k` calls be

```text
T_k = <(a_1, r_1), ..., (a_k, r_k)>.
```

Two implementations are transcript-indistinguishable under `Pi` if they induce
the same distribution over `T_k` for every call sequence the policy may issue.

**Theorem 1.** Let `M` be a monitor whose inputs are the declaration,
client-local state, and `T_k`. If honest `f` and malicious `f*` are transcript-
indistinguishable under `Pi`, then `M`'s detection probability against `f*`
equals its false-positive probability against `f`.

**Proof.** The input distribution to `M` is identical in both worlds;
therefore the output distribution of `M` is identical. Consequently,
`Pr[M=flag | f*] = Pr[M=flag | f]`. QED.

This is an application of a standard indistinguishability argument, not a new
proof technique. It also has the same structural warning as name/object races:
what was checked need not be what is later used [@bishop1996toctou]. The theorem
does not rule out independent state observation or enforcement; it rules out
learning an unobserved effect from a transcript deliberately made identical.

### 3.2 Active auditing and the oracle problem

Clients are not limited to one passive call. They can issue follow-up reads and
check metamorphic relations, an established strategy when direct expected
outputs are unavailable [@chen2018metamorphic]. We use three relation families:

- R1: a write should be reflected by a corresponding read;
- R2: a state transition should preserve a domain invariant; and
- R7: enumeration should reveal the created object.

These checks increase the consistency burden on a naive adversary, but do not
produce an independent witness when the same server controls all answers. The
result is a cost ladder, not a security theorem: an adaptive server can maintain
shadow state and answer every audit consistently.

This is also a runtime-verification issue. Runtime monitors reason over
collected events and traces [@bartocci2018rv]; their conclusions cannot be
stronger than the trustworthiness and coverage of that observation surface.

### 3.3 Measurement method

We harvested public registry entries, selected candidates runnable without
credentials, launched each inside a constrained container, requested
`tools/list`, identified a writable tool and a related observation tool when
available, and executed paired honest and tampered trials. Pairing is by server
identity, not by row order. Honest alarms define the false-positive rate; an
attack counts as detected only when an unauthorized effect is independently
observed and the paired honest trial does not alarm.

The study's outcome vector has five independent fields:

```text
mutation_attempted
protocol_error
authorized_effect_observed
unauthorized_effect_observed
outcome_unknown
```

No field is inferred from another. In particular, a protocol error does not
mean that no effect occurred, and selecting a mutation target does not mean the
mutated effect landed.

### 3.4 Measurement results

The audit funnel is:

| Stage | Servers | Share of candidates |
|---|---:|---:|
| Runnable-without-credentials registry candidates | 8,692 | 100.0% |
| Answered `tools/list` | 4,121 | 47.4% |
| Usable paired write trials | 1,242 | 14.3% |
| Mutation attempted in the original L1 run | 128 | 1.5% |

The 14.3% survival rate is a material selection effect. Servers in the analyzed
tail expose richer, more auditable interfaces than dropouts; conclusions must
not be presented as an unbiased estimate of the entire MCP ecosystem.

Across the recorded operating points, strict policies detected 0--0.5% of
observed attacks at 1.2--6.9% honest false positives. Permissive policies
detected 2.0--7.0% at 71.8--78.3% false positives. The pre-registered criterion
for a usable calibrated point was at least 20% detection with at most 10% false
positives; no tested configuration met it.

The response study should not be read as proof that no active auditing strategy
can ever work. It is evidence that the implemented R1/R2/R7 family did not
reach a deployable point on this selected corpus, consistent with the theorem's
warning that a server controlling all observed answers can preserve the
transcript.

**EVIDENCE GATE:** The A0--A3 prevalence estimate must not appear as a validated
ecosystem result. Round 1 produced `kappa = 0.559`, below the pre-registered
0.60 gate; the fresh 265-row Round-2 sheets are currently unlabeled.

## 4. Contract-Bound Filesystem Admission

### 4.1 Contracts and the specification ladder

An `EffectContract` contains an operation, exact binding fields, bounded fields,
explicitly free fields, and a maximum invocation count. Unmentioned fields are
rejected. Canonical serialization produces an immutable contract identity used
by the allowance ledger.

The contract ladder makes available information explicit:

| Level | Bound property | Prevents admission of | Cannot establish |
|---|---|---|---|
| L1 | destination/path | result at an unapproved path | correct payload |
| L2 | L1 + structure | empty/malformed result | free-text semantic correctness |
| L3 | L2 + exact bytes/hash | content substitution | effects outside the mediated domain |

An opaque command string that combines operation, destination, and content does
not expose an independently enforceable L3 field. MCPGate returns
underspecified/UNKNOWN rather than pretending a string heuristic is equivalent
to a declaration-derived contract.

The reusable mediator evaluated in this paper currently implements the
narrowest enforceable case: one relative `write_file` destination and exact
L3 bytes. L1/L2/L3 are the contract vocabulary and measurement ladder; they
are not three fully implemented admission modes. We keep this distinction
explicit because otherwise the expressibility study would be easy to mistake
for mechanism coverage.

### 4.2 When mediation is useful

If the client already knows every output byte and the only desired effect is a
single file write, it should normally bypass the untrusted server and use a
small trusted writer. MCPGate is not presented as a superior way to perform
that trivial operation. The exact-write prototype is a security testbed for
request/effect binding, replay, writer quiescence, complete-tree validation,
and same-read promotion.

A mediator becomes practically justified when an unmodified server performs
useful computation or a stateful workflow before producing an artifact, while
the client can independently specify an admissible output projection: for
example, a fixed destination plus a signed digest, a deterministic transform,
or a structural predicate stronger than path permission. The present paper has
not yet demonstrated such a non-trivial workload. The final evaluation must
either add one and define its trusted oracle, or narrow the claim to exact-write
admission and compare directly with a trusted-executor baseline. This is a
utility boundary, not merely future work.

### 4.3 Permit rule

The conceptual policy is:

```text
Permit(a, C) =
    Valid(C) AND Matches(a, C)
    AND Unused(C) AND Mediated(a)
```

`Matches` checks the complete request shape and bound values. `Unused` is an
atomic reservation, not a check-then-increment counter. `Mediated` means the
effect entering the trusted store traveled through the staging/diff/promotion
path. `Valid` is a production requirement but only an assumption in the current
prototype; the paper makes no implementation claim for signing or expiry.

### 4.4 Integrated pipeline

For each approved call, the mediator executes the following sequence:

1. Check the proposed operation, all binding values, and every argument key.
2. Atomically reserve an allowance slot keyed by `(contract_id, request_id)`.
3. Create a fresh deterministic per-invocation staging directory.
4. Invoke the unmodified server through a trusted adapter.
5. Close the MCP session, terminate remaining writers in the isolated execution
   identity, revoke staging writes, and attest `boundary_closed`.
6. Re-check the actual arguments delivered across the transport boundary.
7. Enumerate the staging tree once, rejecting symlinks, multiply-linked files,
   special files, unexpected directories, extra files, wrong path, or wrong
   bytes. Only the size-bounded approved file is read; unapproved file contents
   are never materialized into trusted memory.
8. Write the already-materialized approved bytes to a temporary file, `fsync`,
   and atomically replace the destination in the trusted store.
9. Mark the allowance COMMITTED; otherwise mark it FAILED/UNKNOWN and discard
   staging.

The mediator refuses to inspect or commit if the adapter cannot establish that
all writers are closed. An MCP response or closed stdio stream is not by itself
a writer-quiescence proof.

### 4.5 Allowance and replay semantics

Allowance states are `RESERVED`, `COMMITTED`, and `FAILED`. Reservation is
atomic, so two overlapping calls cannot both take the final slot. Reusing the
same request identifier returns the recorded result without re-execution.
Using a new request identifier after exhaustion is refused. If execution began
and the process died before the result was observed, the slot remains consumed
and UNKNOWN; retrying could duplicate a real effect.

The prototype offers both an in-process ledger and a SQLite WAL backend. The
durable backend writes a FULL-synchronous reservation before untrusted
execution and uses an immediate transaction so separate mediator processes
cannot both take the final slot. On restart, COMMITTED JSON-shaped results can
be replayed without execution, while an orphaned RESERVED slot remains consumed
and is reported UNKNOWN. This is fail-closed at-most-once entry, not exactly-once
world-effect semantics: resolving whether an interrupted effect occurred still
requires a domain-specific oracle.

### 4.6 Same-read commit invariant

The decision snapshot and committed bytes are the same in-memory object. Once
the snapshot has been materialized, the commit path never reopens staging.
Therefore a mutation after validation cannot change the bytes committed by that
invocation. This closes the concrete two-read race found during adaptive
testing, but it does not prove that directory traversal during snapshot creation
is race-free. Writer revocation is a separate precondition.

## 5. Implementation

The reusable implementation is split into four auditable components:

- `src/mcpgate/contract.py`: immutable contracts, canonical identity, and
  fail-closed request checking;
- `src/mcpgate/allowance.py`: thread-safe reservation and replay state machine;
- `src/mcpgate/mediator.py`: per-call staging, materialized tree validation,
  same-read atomic promotion, records, and cleanup; and
- `experiments/boundary/probe_m2_real_server.py`: adapter for a real
  third-party MCP filesystem server in the isolated Docker probe.

The generic mediator intentionally delegates writer revocation to the trusted
adapter because the correct primitive is deployment-specific. The current
Docker adapter dedicates a Linux UID to one invocation, enumerates `/proc`,
terminates all non-zombie processes for that UID, verifies none remain, then
changes staged objects to the trusted identity and removes write permission.
Production should replace this UID-wide operation with a per-invocation cgroup,
PID namespace, and mount namespace.

A fifth component generalizes admission from one known file to a whole
workflow tree: `src/mcpgate/tree_mediator.py` snapshots the complete staged
tree after writers close, checks every changed object against exactly one
declarative path and content rule, and promotes the validated directory itself
so commit never rereads attacker bytes. The matched evaluation derives these
rules from repeated honest runs rather than writing them by hand.

Local regression contains 268 passing tests and two platform skips. The
mediator tests cover honest commit; request preflight; post-transport argument
mutation; wrong content; extra files; symlinks and hardlinks; bounded
materialization that never reads extra-file contents; absent writer closure;
same-read mutation; replay; exhaustion; runner failure; unsafe paths; and
overlapping threads competing for one slot. The whole-tree tests add the case
that matters most for the comparison in Section 4: an effect diverted by a
compromised implementation, with an honest request and an honest response, is
refused at the effect-diff stage rather than the request-shape stage, so the
mechanism is verified to catch what request validation alone cannot.

The revised integrated adapter has been rerun on the current machine against
unmodified third-party servers, both for the pinned single-file capstone and
for the matched five-condition evaluation in Section 6.4. Historical real-server
results that used an older hand-written mediator are not presented as if they
exercised this module.

## 6. Evaluation

### 6.1 Questions and metrics

The final evaluation asks:

- RQ1: Can response auditing reach the pre-registered detection/FPR criterion?
- RQ2: What authorization detail can real MCP schemas express at L1/L2/L3?
- RQ3: Does MCPGate prevent mismatching results from entering trusted state?
- RQ4: What honest-completion, false-block, UNKNOWN, latency, CPU, and memory
  costs does it impose?
- RQ5: Do results survive adaptive attacks and transfer to frozen held-out
  implementations?

Security and utility metrics are reported separately: demonstrated attacks,
trusted-store violations, honest completion, false block, UNKNOWN, and
per-invocation overhead. An attack enters a prevention denominator only if the
paired undefended control shows that it actually lands.

### 6.2 Controlled adversarial probe

The M2-proper probe lets the untrusted process write its own staging tree and
uses a separate trusted store. Fourteen scenarios cover honest behavior, wrong
path, content substitution, hidden arguments, extra files, links, rename,
pre-opened descriptors, child/background writers, error-after-effect, and
silent no-op.

Ten attacks landed in the paired undefended condition; all 10 were kept out of
the trusted store. One of 14 defended outcomes was UNKNOWN (`silent_noop`), and
honest completion matched the undefended condition. Eight demonstrated attacks
were rejected by the contract diff and two post-commit mutation attempts were
blocked by permissions on the trusted store. The first implementation admitted
a hidden extra argument because it compared only filesystem state; adding
request-shape validation closed that case on rerun.

### 6.3 Adaptive attacks

After the mechanism existed, four mechanism-aware evaluations targeted its
assumptions:

- **Two-read TOCTOU.** The original validator checked one read and copied from
  a second. An adaptive writer won 5/20 trials. Committing the first
  materialized bytes reduced the same attack to 0/20. This supports the tested
  invariant, not a universal claim over all filesystem races.
- **Replay.** A second logical invocation could repeat a valid effect. Moving
  atomic allowance reservation before execution closes same-ID replay,
  different-ID exhaustion, and the final-slot concurrent race in local tests.
- **Unmediated channel.** A filesystem contract did not stop socket
  exfiltration. This is a demonstrated scope boundary, not a tuning failure.
- **Fixed observation window.** A patient delayed writer and an honest slow
  writer cannot always be distinguished by a timeout. MCPGate therefore
  requires explicit writer revocation rather than claiming that a grace period
  is a security boundary.

### 6.4 Real servers and static least privilege

Historical experiments cover seven unmodified third-party servers across
filesystem, SQL-shaped, notes, and git-like workflows. Two SQL implementations
independently reproduced the negative result that an opaque command argument
does not expose a declaration-derived content boundary. Separately, before any
security outcome was observed, we froze 10 exact-version third-party
implementations after isolated schema and benign-effect/oracle eligibility
(EXACT 4, CONSTRAINED 4, UNDERSPECIFIED 2). The matched five-condition
evaluation on the filesystem-class subset of those frozen workloads is reported
in Section 6.5; the network and SQL arms remain in progress.

On two independent real servers, a task-specific static filesystem-permission
baseline was blind to content substitution at an already-approved writable
file, because permissions constrain who may write where rather than which bytes
may be written. Path-diversion behavior differed between the two servers: the
baseline blocked a relative sibling creation in a non-writable directory but
did not provide a general content contract. MCPGate rejected both tested
content substitutions and both path mismatches from trusted admission.

This comparison positions MCPGate against resource confinement rather than a
strawman. AgentBound already provides declarative, concrete, container-enforced
resource permissions for unmodified MCP servers [@buhler2026agentbound]. Its
own evaluation notes that attacks remaining within an allowed resource boundary
can evade access control. MCPGate targets one such narrower case—exact content
admission at an approved filesystem path—and should be composed with, not
presented as replacing, a sandbox.

### 6.5 Matched five-condition held-out evaluation

We ran the frozen filesystem-class servers through one honest workflow and every
applicable attack under five conditions that hold execution constant and vary
only the admission policy: no defense, a plain hardened sandbox, the response
auditor, a task-specific static permission policy, and full MCPGate. Five
servers qualified for this arm, spanning two exact-write filesystem servers and
three memory or document servers that write multi-file trees; document-generator
was excluded because it writes to a fixed path the client cannot select, and the
two memory servers that store under the home directory are handled by the SQL
arm. The run covers 180 attack cells.

Two properties make the comparison honest. First, attacks are realized by
runtime interposition, not by rewriting the request: a preload shim for Node
servers and a `sitecustomize` shim for Python servers divert the effect while
the server still receives the approved arguments and returns its honest
response. Second, the adversary operates a consistent-liar tier that also masks
the server's own reads and directory listings, so the live response auditor,
which sees only what a deployed client sees, observes a simulated honest world.
The trusted host snapshot, taken after the container and all descendants exit,
is unaffected by this masking.

The MCPGate contract for each server is derived from three spaced honest runs,
which sort every changed file into a byte-stable class checked by exact hash, a
volatile class checked by required-marker presence, and an unconstrained class
whose content cannot be verified and is reported as UNKNOWN rather than silently
trusted. This is the L1/L2/L3 ladder of Section 4.1 emerging from real output
rather than being assumed.

Table 1 gives the result. Full MCPGate prevented every applicable attack, 31 of
31, with a Wilson 95 percent interval of 89.0 to 100.0 percent, and produced no
false block on any honest workflow. The static permission policy prevented 58.1
percent: it blocks destination substitution and extra files because it binds
where a server may write, but it admits attacker bytes at an already-approved
path, admits a symlink placed at that path, and cannot tell a silent no-op from
a real write. No defense, the plain sandbox, and the response auditor each
prevented 29.0 percent, which corresponds to the two scenarios that are inert
for these servers, a hidden unlisted field and an idempotent replay. The
response auditor raised one confirmed violation, on a destination diversion the
server could not fully simulate away, but it never prevented an effect that
landed, and against content substitution under the consistent tier it reported
the write as confirmed while the attacker bytes were on disk.

| Scenario | None | Sandbox | Auditor | Static LP | MCPGate |
|---|---:|---:|---:|---:|---:|
| Destination substitution | 0/3 | 0/3 | 0/3 | 3/3 | 3/3 |
| Content substitution | 0/5 | 0/5 | 0/5 | 0/5 | 5/5 |
| Hidden field | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| Extra effect | 0/5 | 0/5 | 0/5 | 5/5 | 5/5 |
| Replay | 4/5 | 4/5 | 4/5 | 5/5 | 5/5 |
| Silent false success | 0/5 | 0/5 | 0/5 | 0/5 | 5/5 |
| Link alias | 0/3 | 0/3 | 0/3 | 0/3 | 3/3 |
| **Prevented / applicable** | **9/31** | **9/31** | **9/31** | **18/31** | **31/31** |

Table 1: Attacks prevented per scenario, summed over servers, under the
consistent-liar adversary. Cells are prevented over applicable. Raw per-cell
outcomes are in `artifact/results/matched_filesystem.json`.

Two stochastic scenarios are mechanism properties of the allowance ledger and
the freeze step rather than of any server's content, and were run for 100 trials
each against the mediator with real child processes. When eight invocations
contended for one final allowance slot, exactly one committed and the other
seven were refused in all 100 trials, each admitted invocation using a distinct
private staging tree. When a writer was still live as the runner returned, the
gate refused at the freeze step in all 100 trials and no file reached the
trusted store. Raw counts are in `artifact/results/concurrency_100.json`.

### 6.6 Controlled baseline comparison

On the controlled filesystem domain, we compare no defense, a plain sandbox
with no per-call policy, the project's response auditor, a task-specific path
policy, and the proposal-based trusted-executor gateway. The plain sandbox has
the same within-sandbox outcomes as no defense: it narrows host exposure but
does not bind one call's path or content. The response auditor surfaced path
diversion only after the effect and did not prevent it; it did not surface
content substitution. The path policy blocked diversion but admitted attacker
bytes at the approved path. The trusted executor prevented all three
filesystem-expressible attack cases, but it does so by never giving the server
the write capability and is therefore a stronger, simpler architecture when
the exact output is already known. Machine-readable rows and the generated
table are checked in under `artifact/results/controlled_baselines.json` and
`results/tables/controlled_baselines.md`.

### 6.7 Controlled ablations

A deterministic local ablation suite removes one property at a time from the
integrated design. The full mediator refused content substitution without
creating a trusted file. Removing atomic allowance/idempotency entered the
runner twice for one replayed request identifier; removing request-shape checks
committed after delivering a hidden field; an independent second read committed
post-check attacker bytes; shared staging falsely refused both overlapping
honest calls; a path-only policy admitted substituted content; and omission of
an outer namespace allowed an outside-world write while trusted admission
remained byte-correct. The machine-readable rows and generated table are
`artifact/results/controlled_ablations.json` and
`results/tables/controlled_ablations.md`.

These ablations establish causal behavior in the local implementation. They do
not replace the pending pinned real-server rerun or justify ecosystem-wide
performance claims.

### 6.8 Exact-write engineering baseline

We directly compare MCPGate's current exact single-file case with an atomic
trusted writer over 100 interleaved repetitions on the development machine.
The direct writer's p50 was 3.7432 ms versus 6.2546 ms for the mediator, a
1.671x ratio. This is not a release-environment performance claim: it excludes
a real server and records one Windows host. Its architectural result is more
important than the timing. Both designs protected trusted bytes from content
substitution, but a deliberately unmediated side write remained possible when
the server ran under MCPGate and was absent when no server was invoked. Thus,
for already-known bytes and one write, the trusted writer is the correct
baseline. The present manuscript consequently claims exact-write admission as
a security mechanism/testbed, not superior utility; broader utility requires a
non-trivial computation with an independently checkable output projection.

### 6.9 Process-backed concurrency

Local evaluations replace simulated scheduling with real child writers. In a
demonstration run two independent contracts overlapped for 140.775 ms, received
distinct staging roots, and committed `a.txt` and `b.txt` correctly. The
stochastic contention scenarios were then run for 100 trials each, reported in
Section 6.5: exactly one of eight contenders committed every trial, and a live
background writer was refused at freeze every trial with nothing committed.
Separate SQLite ledger instances also cannot reserve the same final slot, and
restart tests preserve RESERVED and COMMITTED states. The release run must still
establish the full mediator plus Linux UID/cgroup behavior on pinned
third-party servers.

### 6.10 Results still required for submission

The filesystem arm of the matched evaluation is complete: the five-condition
comparison on frozen third-party servers (Section 6.5), the integrated pinned
single-file run, and the 100-trial concurrency scenarios have all run on the
current machine with raw artifacts checked in. The following remain before
submission:

1. label Round 2 independently and either pass the kappa gate or retire the
   prevalence result;
2. run the matched network and SQL arms against their frozen servers, so the
   effect-integrity claim is not filesystem-only;
3. report p50/p95/p99 latency, CPU, and peak memory for the matched conditions;
4. calculate server-clustered intervals rather than treating nested tools as
   independent samples; and
5. rebuild the anonymous artifact bundle from a clean clone and confirm every
   table regenerates.

## 7. Security Analysis

### 7.1 Trusted-state admission argument

Assume (A1) the contract is trusted and immutable, (A2) allowance reservation
is atomic, (A3) the server can write staging but not the committed store, (A4)
all staging writers are revoked before snapshot, (A5) tree materialization
correctly rejects unsupported filesystem objects, and (A6) the trusted mediator
and OS are not compromised.

If MCPGate commits, preflight and post-transport checks establish that the
operation and complete argument shape match the contract. Tree validation
establishes that the materialized snapshot contains exactly the approved
relative path and bytes and no disallowed object. Atomic promotion receives
those same in-memory bytes, rather than a second staging read. Therefore the
committed path and bytes equal the L3 contract for that invocation. Atomic
allowance reservation additionally ensures that at most the authorized number
of unique invocation slots enter execution. With the durable backend, this
bound survives process restart; an ambiguous RESERVED slot stays spent.

### 7.2 Where the argument ends

The argument fails if the server can write the committed store directly, if a
writer survives the freeze boundary, if the filesystem representation is not
fully captured by the validator, if the contract is malicious, or if effects
escape through another channel. The durable ledger prevents an ambiguous call
from being re-executed after a crash, but it cannot atomically commit an
arbitrary outside-world effect together with its ledger row or determine an
orphaned call's outcome. Exactly-once world-effect semantics therefore remain a
non-claim.

## 8. Related Work

### MCP security

ETDI authenticates tool definitions and combines versioning, OAuth, and policy-
based access control [@bhatt2025etdi]. A zero-trust registry similarly improves
administrator-controlled discovery, signed metadata, and access initiation
[@narajala2025zerotrust]. These systems reduce identity and rug-pull risk but do
not make an approved compromised server's protocol response an independent
effect witness. MCP-Guard detects malicious MCP content with a staged scanning
and classification pipeline [@xing2026mcpguard]; it is a detection baseline,
not deterministic filesystem admission.

### Agent authorization and information flow

Progent checks tool names and arguments against symbolic privileges before
execution [@shi2025progent]. CaMeL separates trusted control flow from untrusted
data and applies capabilities at tool-call time [@debenedetti2025camel].
ChainCaps propagates sink-specific capability budgets through explicit tool
composition, but explicitly assumes trusted manifests and proxy-visible flows
[@jiang2026chaincaps]. These approaches govern which call or data flow is
authorized. MCPGate asks the complementary post-execution question: did the
untrusted local implementation produce the exact filesystem state approved for
admission?

AgentBound is the closest system-level comparator. It generates declarative
MCP resource manifests and confines unmodified servers with container
filesystem, network, environment, and process controls
[@buhler2026agentbound]. It already owns the broad claim of an MCP execution
boundary. MCPGate's narrower delta is content-bound admission within an allowed
writable resource; AgentBound itself identifies permitted-but-malicious use as
the access-control semantic gap.

Capsicum demonstrates practical least-authority compartmentalization through
capability mode and descriptor rights [@watson2010capsicum], while seL4 shows
how far kernel assurance can be pushed when an implementation refines a formal
specification [@klein2009sel4]. Object-capability analysis also supplies the
least-privilege and confused-deputy vocabulary [@miller2003capabilitymyths].
These systems operate beneath MCPGate's per-invocation semantic contract; a
path capability alone does not state which exact bytes may be written through
that capability.

### Transactional and isolated execution

Alcatraz directs an untrusted process's writes into an isolated environment,
then supports inspection and commit or discard [@liang2009alcatraz]. TxOS
provides kernel transactions with private/versioned state and commit/abort
semantics [@porter2009txos]. These works preclude novelty claims for staging,
rollback, or commit in isolation. MCPGate applies established transactional
lineage to a protocol-specific authorization object and studies request/effect
binding, schema expressibility, replay, adaptive MCP-server behavior, and
trusted-store admission without a modified server or kernel.

SAFEFLOW combines information-flow labels, logged agent operations, localized
rollback/replanning, and multi-agent concurrency control
[@li2025safeflow]. Its paper does not specify MCPGate's byte-level external
filesystem promotion boundary; conversely, MCPGate does not provide SAFEFLOW's
agent-wide provenance or information-flow policy.

### Evaluation environments

AgentDojo supplies stateful tasks and security test cases for prompt-injection
attacks against tool-using agents [@debenedetti2024agentdojo]. InjecAgent
focuses on indirect prompt injection across user and attacker tools
[@zhan2024injecagent], while ToolEmu uses an LM-emulated sandbox to scale
long-tail risk discovery [@ruan2024toolemu]. Our adversary is different: the
tool server implementation itself is compromised after approval, and its effect
oracle is real trusted filesystem state rather than an LM-emulated world. These
systems remain evaluation-design references, not equivalent effect mediators.

## 9. Limitations, Ethics, and Reproducibility

The registry corpus excludes credentialed and non-launching servers, and only
14.3% of candidates reached usable paired trials. The measurement favors
servers with richer interfaces. The A0--A3 classifier has not passed its human
agreement gate. Later real-server experiments are small and partially
development-selected. Several raw traces are currently gitignored; checked-in
tables and hashes do not by themselves permit full recomputation from a fresh
clone.

The integrated mechanism currently admits one exact single-file write. This
is sufficient to test its security invariants but not, by itself, to establish
that mediation is more useful than a trusted direct writer. A submission must
evaluate a non-trivial server computation with an independently checkable
output contract, or present exact-write admission as the deliberately narrow
result and include the direct-writer alternative as a baseline.

Running unvetted third-party packages is hazardous. All live execution must use
an isolated, non-root, capability-dropped, resource-capped container with no
host secrets. The project should publish server identities and exact versions
unless a venue ethics review identifies a concrete disclosure risk. Results
about a server are behavioral observations of a pinned version, not claims
about developer intent.

The final artifact must provide quick and full modes, dependency locks, image
digests, compact raw JSON for every table, a SHA-256 manifest, scripts that
regenerate all figures, expected runtime/hardware, and an anonymized review
mode. Human annotators, adjudication, author review of every citation, and final
ethics/conflict declarations cannot be automated away.

## 10. Conclusion

An MCP response can authenticate a conversation without independently proving
the effect of that conversation. In our tested corpus, adding response-level
relations did not yield a usable detection/false-positive tradeoff. MCPGate
therefore moves the decision from server testimony to trusted-state admission:
an unmodified local server writes staging, while a trusted mediator admits only
a frozen, complete, contract-matching snapshot. The design closes concrete
content-substitution, hidden-field, replay, and tested TOCTOU failures, but only
within a declared filesystem boundary. The defensible takeaway is not that
MCPGate makes tool use universally safe; it is that exact effect admission is a
distinct security property that response validation and path permission alone
do not establish.

## Submission blocker ledger

| Blocker | Current state | Manuscript consequence |
|---|---|---|
| Integrated real-server rerun | Pinned Linux-container development run passed and raw JSON is checked in; clean-commit release repeat pending | Claim the exact three scenarios, not ecosystem generality |
| Round-2 annotation | 265-row sheets exist but contain no labels | Omit A-class prevalence |
| Held-out breadth | Seven historical servers; target is at least 10 frozen | Qualify generality |
| Concurrency | Real local child processes overlap correctly; pinned Linux/third-party rerun pending | Qualify portability and external validity |
| Durability | SQLite WAL/FULL-sync reservations survive restart; orphaned RESERVED remains UNKNOWN | Claim fail-closed at-most-once entry, not exactly-once world effects |
| World effects | Filesystem trusted-store admission only | Do not claim network/process containment or rollback |
| Utility beyond direct write | Narrow exact-write result with a 100-repetition trusted-writer comparison | State that a trusted direct writer is simpler when all output bytes are already known |
| Raw artifacts | Current controlled JSON is checked in; historical/full traces remain incomplete | Do not claim fresh-clone full reproduction |
| Bibliography | 21 cited identities verified; 41 unused/unverified entries quarantined | Cite only verified keys; verify or remove any newly used key |

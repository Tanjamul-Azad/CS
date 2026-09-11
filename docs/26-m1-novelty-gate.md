# M1 — Novelty gate

Written 2026-09-10; extended 2026-09-11 (§5.1, §5.2). The gate defined in [`25-research-program.md`](25-research-program.md) §6 M1, which exists to be failable.

## Verdict

| | |
|---|---|
| **Broad architectural claim** — "confine an untrusted MCP server's effects at an enforcement boundary derived from a per-call authorization" | **NO-GO.** Taken, by primary sources below. |
| **Narrow candidate** — permission-compatible but contract-violating effects | Survives, and now precisely bounded: three adjacent systems (TxOS, Alcatraz, SAFEFLOW) each hold a piece of it from a different layer, none holds the whole. Its test is specified in [`27`](27-narrow-candidate-experiment.md). |
| **Measurement and instruments** | Not removed by the gate — but the large-scale results carry an unresolved evidence caveat, see §4. |
| **The design space** | **Not closed.** Named claims were rejected against named prior work. That is not an enumeration. |

The gate did its job. It cost two days and it stopped a month of building on claims that five separate systems already hold between them.

---

## 1. The system that closes it: AgentBound

**Securing AI Agent Execution**, Bühler et al., [arXiv:2510.21236v1](https://arxiv.org/abs/2510.21236) §2.3, §3.1, §3.2.

Verified to contain, together, everything the program's architecture section proposed:

- the malicious-MCP-implementation threat model
- a declarative permission manifest
- runtime file / directory / URL permissions, concrete rather than categorical
- user consent
- container-based enforcement
- **wrapping unmodified MCP servers**

The paper includes a worked example granting write permission to a README. So these are no longer available as contributions:

> ~~constraining an MCP server at an enforcement boundary~~
> ~~deriving runtime permissions from declarations~~
> ~~enforcing without modifying the server~~

**AgentBound is the primary competitor and the research must be designed against it, not around it.** Treating it as a weak "coarse static sandbox" baseline would be wrong — it does concrete per-resource permissions.

## 2. Everything else checked, with what it costs us

| Work | Verified mechanism | What it removes |
|---|---|---|
| **CaMeL** [2503.18813](https://arxiv.org/abs/2503.18813) §3–5 | privileged/quarantined LLM split; interpreter enforcing capability and data-flow policy over a trusted plan | authority separation and capability policy are not new |
| **Progent** [2504.11703](https://arxiv.org/abs/2504.11703) §3.2–4 | programmable per-call policy over tool arguments; **human-written as well as** LLM-generated | per-call policy/contract is not new. Our earlier note that Progent trusts an LLM to author policy was wrong |
| **SAFEFLOW** [2506.07564](https://arxiv.org/abs/2506.07564) | verified from the primary abstract: IFC with provenance/integrity/confidentiality labels, **transactional execution, conflict resolution, write-ahead logging, rollback**, secure caches | transactional agent execution is not new |
| **Alcatraz** — Liang, Sun, Venkatakrishnan, Sekar, [ACM TISSEC 12(3), 2009](https://dl.acm.org/doi/10.1145/1455526.1455527); [ACSAC 2003](https://www.seclab.cs.sunysb.edu/seclab/pubs/acsac03.pdf) | one-way isolation: untrusted process reads the host, writes go to copy-on-write storage, then a **consistency-checked commit or discard** | **the M2 design in `25` §6 is this, applied to MCP.** Staging workspace + diff + commit-or-discard is a 2003 systems technique |
| **ChainCaps** [2605.26542](https://arxiv.org/abs/2605.26542) §3.1 | capability attenuation over trusted manifests and proxy-visible flows; explicitly scopes out compromised servers and proxy-bypassing OS effects | MCP proxying, one-shot authority and fail-closed handling are not new. Its scope exclusion is a real difference from our threat model |
| **Capsicum** — USENIX Security 2010 §2 | kernel-enforced capabilities, restricted namespaces, descriptor rights inherited by descendants | limiting actual execution authority is established systems work; MCP integration alone is not novelty |
| **Landlock** — [kernel documentation](https://docs.kernel.org/userspace-api/landlock.html) | OS-level filesystem and network access restriction | **corrects our own overclaim.** Given a policy, a sandbox *can* restrict the destination. What it cannot do is derive the policy from user intent |
| **MCP specification** 2025-06-18, Tools | recommends human confirmation and the ability to deny an invocation; warns that server annotations are untrusted | "MCP has no confirmation" is false. Approval and effect-enforcement are different properties |
| **AttestMCP** [2601.17549](https://arxiv.org/abs/2601.17549) §VI — cited earlier as "MCPSec" | capability attestation and message authentication | protocol authenticity ≠ actual-effect enforcement. **Name/version mismatch: do not enter the bibliography until reconciled** |

## 3. Claims now retired

Struck from the program and from any draft:

- ~~first MCP execution-boundary defense~~ — AgentBound
- ~~first per-call authorization system~~ — Progent
- ~~first transactional agent system~~ — SAFEFLOW
- ~~generic staging + diff + commit is a new mechanism~~ — Alcatraz, 2003
- ~~no sandbox can enforce authorization~~ — Landlock enforces a supplied policy; it just cannot invent one
- ~~MCP offers no human confirmation~~ — the specification recommends it

## 4. What survives

**As a candidate mechanism, narrow and not yet a contribution:**

> A server may hold a legitimate permission to write `report.txt` and still violate the contract by writing *different bytes* to it. Path-level permission is intact; the authorization is not.

AgentBound grants resources; it does not constrain the content committed within a granted resource. That is a real gap.

**But demonstrating it proves almost nothing on its own.** A contract that specifies exact bytes holds strictly more information than a path grant, so of course it catches content substitution — that is true by construction. The experiment must separate *does more specification help* (a property of the contract) from *does our mechanism help* (a property of us), by running a **simple staging-and-diff validator given the same contract and the same trusted information** as a control. If the simple validator matches it, there is no system contribution here. [`27-narrow-candidate-experiment.md`](27-narrow-candidate-experiment.md) specifies that comparison.

**As contributions that the literature check did NOT remove — because they are measurements and instruments, not architecture:**

1. The auditability distribution over 18,566 real tools, and the live audit over 1,242 third-party servers. **With a caveat that is not optional:** those trials carry no independent state evidence. They are protocol- and proxy-based observations, and cannot be re-reported as observed-compromise detection rates. The effect oracle exposed the label defect; it did not retroactively repair the data. This contribution needs its own validation pass.
2. The negative result on post-hoc effect verification, with its cause located rather than asserted — subject to the same caveat.
3. **The effect oracle** — separating mutation attempted, protocol status, authorized effect, unauthorized effect and unknown, and demonstrating that neither the mutation plan nor the protocol status is ground truth.
4. The evaluation discipline: paired undefended controls, prevention coverage over demonstrated attacks, prevented/detected/UNKNOWN kept apart, mechanism attribution.

A candidate shape for the paper, **not a settled one**: a measurement and evaluation paper about MCP effect verifiability, which evaluates existing defenses against permission-compatible attacks.

**This document must not be read as closing the design space.** M1 rejected four *specific* broad claims against named prior work. It did not enumerate every possible system contribution, and "no architecture paper is possible here" does not follow from "these four architectures exist". An earlier version of this section overstated exactly that, and the narrow candidate below is the next thing to test, not the last thing available.

Whether the surviving contributions carry a paper depends on what [`27-narrow-candidate-experiment.md`](27-narrow-candidate-experiment.md) measures, not on this table.

## 5. Revised research question

> Can a trusted invocation contract constrain externally committed filesystem changes made by an unmodified, untrusted MCP server, while preserving realistic stateful workflows and avoiding server-specific execution code?

Four burdens it carries, each testable:

| | |
|---|---|
| **Effect binding** | which invocation caused an observed change |
| **Commit integrity** | can committed bytes change after validation |
| **Workflow compatibility** | stateful servers, partial writes, renames |
| **Generality** | configuration or semantic adapters per new server |

Positioned against AgentBound as the primary baseline, not against a strawman sandbox.

## 5.1 SAFEFLOW, full text (2026-09-11) — the specific finding that matters

The abstract retired the broad "transactional agent execution is new" claim. The full text (arXiv HTML, v3, Appendix C) answers the sharper question: does SAFEFLOW's transaction machinery already do what our narrow candidate proposes?

**No, and the reason is precise, not incidental.**

| | SAFEFLOW (verified, App. C.2.1–C.2.3) | Our candidate (docs/27) |
|---|---|---|
| Transaction unit | one agent operation / message | one MCP invocation |
| Conflict handling | **pessimistic** — a global mutex guards critical sections before modification | not yet decided; concurrency is an open Mediated() failure mode ([`25`](25-research-program.md) §5) |
| What rollback restores | **internal execution state** — "selectively replaying only log entries with incomplete status." Section C.2.2: "localized rollback or logical substitution" within its own DAG | **external, real side effects** — a file a server actually wrote |
| Third-party tools | mediated as part of the Environment entity, but only the call is logged — **"true rollback of external side effects is not addressed"** (direct finding from the source) | this is the entire point of the candidate |
| Write-ahead log content | operation metadata, source/destination entities, intent — an audit trail of *reasoning*, not of *filesystem state* | a byte-level diff of what actually changed on disk |

**The one sentence this buys:** SAFEFLOW's "rollback" is a checkpoint of the agent's own bookkeeping, not a commit/discard over a real external effect. It does not compete with the candidate; it operates one layer up. This must be stated exactly this way — not as "SAFEFLOW doesn't do transactions," which it demonstrably does, but as "SAFEFLOW's transactions do not reach the external system."

## 5.2 TxOS — kernel-level transactional system calls (2026-09-11)

**Operating System Transactions**, Porter, Hofmann, Rossbach, Benn, Witchel, [SOSP 2009](https://dl.acm.org/doi/10.1145/1629575.1629591) (not OSDI, corrected from an earlier draft's guess). Implemented in the Linux 2.6.22.6 kernel, [source available](https://github.com/ut-osa/txos): ~150 system calls made transactional, with checkpoint/rollback of kernel objects (file metadata, address-space state) via a custom object-based software transactional memory layer using lazy version management — private copies until commit.

**What this closes.** "Staging + diff + commit/discard for filesystem operations" was already closed by Alcatraz (§2); TxOS closes it a second time, one layer lower, and rules out a fallback claim of novelty at the syscall level. **What it does not close:** TxOS operates *inside* the kernel the transacted process runs under — it requires a modified kernel, not a wrapper around an unmodified untrusted binary. The candidate in docs/27 stages by copying a directory tree around an ordinary, unmodified MCP server process. That is a real implementation difference in *mechanism* (kernel-resident vs. process-external), though not in the *underlying idea* (transactional staging and commit), which both TxOS (2009) and Alcatraz (2003) hold.

**Dropped.** "Solitude" was named in an earlier draft as a third comparison point. It could not be verified against any primary source — a search returned no paper by that name matching the described mechanism. Per the citation quarantine rule ([`22`](22-research-diagnosis-and-10-day-plan.md), [`23`](23-frozen-direction-auditability-analyzer.md) §5), it is removed rather than left in on the strength of a half-remembered reference.

## 6. Gate status

**M1 is substantially cleared; capability-systems review remains partial.** Both items open at the previous writing are now closed:

- ~~SAFEFLOW full text~~ — done, §5.1. Sharpens rather than merely retires the earlier finding: SAFEFLOW is transactional but never reaches the external system.
- ~~Traditional transactional sandbox/commit systems beyond Alcatraz~~ — TxOS done, §5.2. "Solitude" dropped as unverifiable.

**Still open:** the capability-systems review (Capsicum is checked; the broader literature — seL4-style capability kernels, object-capability languages — is not).

**Cumulative finding, stated once.** Three independent systems, at three different layers, already do staging/transactional confinement of *something*: TxOS at the kernel syscall layer (2009), Alcatraz at the process/filesystem layer (2003), SAFEFLOW at the agent-reasoning layer (2025). None of the three commits or discards an untrusted MCP server's *external, real* filesystem effect from *outside* an *unmodified* process. That gap — narrow, precisely bounded by three adjacent systems rather than asserted against none — is what docs/27's candidate has left to test. It is a real gap. It is also now a small one, and the paper must say so in those words rather than as an unqualified "novel mechanism."

What the gate has delivered is worth more than a pass would have been: three broad claims retired, two further systems closing the narrow one from adjacent layers, one of our own overclaims corrected, and the primary competitor (AgentBound) identified before implementation rather than after.

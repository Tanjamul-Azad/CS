# M1 — Novelty gate

Written 2026-09-10. The gate defined in [`25-research-program.md`](25-research-program.md) §6 M1, which exists to be failable.

## Verdict

| | |
|---|---|
| **Broad architectural claim** — "confine an untrusted MCP server's effects at an enforcement boundary derived from a per-call authorization" | **NO-GO.** Taken, by primary sources below. |
| **Narrow candidate** — permission-compatible but contract-violating effects | Survives, but is thin on its own. |
| **What is still ours** | The measurement and the evaluation instrument, not an architecture. |

The gate did its job. It cost a day and it stopped a month of building on a claim that three separate systems already hold.

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

AgentBound grants resources; it does not constrain the content committed within a granted resource. That is a real gap — and on its own it is an incremental extension, not a paper. It needs a measured comparison against content-aware policy and transactional validation baselines before it counts as anything.

**As contributions that the literature check did NOT remove — because they are measurements and instruments, not architecture:**

1. The auditability distribution over 18,566 real tools, and the live audit over 1,242 third-party servers.
2. The negative result on post-hoc effect verification, with its cause located rather than asserted.
3. **The effect oracle** — separating mutation attempted, protocol status, authorized effect, unauthorized effect and unknown, and demonstrating that neither the mutation plan nor the protocol status is ground truth.
4. The evaluation discipline: paired undefended controls, prevention coverage over demonstrated attacks, prevented/detected/UNKNOWN kept apart, mechanism attribution.

This is the honest shape the paper now has: **a measurement and evaluation paper about MCP effect verifiability, which evaluates existing defenses against permission-compatible attacks — not a paper proposing a new architecture.**

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

## 6. Gate status

**M1 is not fully cleared, and this document does not claim it is.** Remaining:

- SAFEFLOW **full text** — the abstract is enough to retire the broad transactional claim, not enough to judge implementation-level differences.
- Traditional transactional sandbox and commit systems beyond Alcatraz — TxOS, Solitude, union/overlay-mount sandboxes.
- Traditional capability systems review is partial.

What the gate has already delivered is worth more than a pass would have been: three broad claims retired, one of our own overclaims corrected, and the primary competitor identified before implementation rather than after.

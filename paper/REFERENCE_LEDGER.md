# Reference Verification Ledger

No citation may enter the paper's novelty claim or related-work comparison until
its title, authors, year, venue/identifier, and relevant property have been
checked against a primary source: the publisher/venue page, DOI record, official
specification, or the paper itself.

Status vocabulary:

- **VERIFIED** — checked against a primary source and ready to cite.
- **PARTIAL** — identity is known, but the specific comparison claim still needs
  full-text verification.
- **UNVERIFIED** — do not cite from memory.
- **REMOVE** — irrelevant, duplicate, nonexistent, or too weak for the paper.

## A. Load-bearing references

| Topic | Reference/key | Required comparison | Status |
|---|---|---|---|
| MCP protocol | `mcp2025tools` | Tool declarations, calls, schemas, results, and the protocol-visible evidence boundary | VERIFIED |
| TOCTOU | `bishop1996toctou` | Name/object binding may change between repeated references; structural lineage only | VERIFIED |
| Metamorphic testing | `chen2018metamorphic` | Oracle problem and relation-based result checking; paper does not establish security against a malicious SUT | VERIFIED |
| Runtime verification | `bartocci2018rv` | Monitors evaluate observed traces/events; observation coverage is an assumption | VERIFIED |
| Alcatraz | `liang2009alcatraz` | One-way isolation, inspect, rollback/commit, and consistency lineage | VERIFIED |
| TxOS | `porter2009txos` | Transactional system calls and kernel-level private copies/commit-abort lineage | VERIFIED |
| AgentBound | `buhler2026agentbound` | OS-level MCP-server confinement and the permitted-but-malicious semantic gap | VERIFIED |
| SAFEFLOW | `li2025safeflow` | Transactional logging/local recovery; do not attribute arbitrary external-effect rollback | VERIFIED |
| ETDI | `bhatt2025etdi` | Cryptographic tool identity, versioned definitions, OAuth/PBAC; not effect integrity | VERIFIED |
| Zero Trust Registry | `narajala2025zerotrust` | Registry identity, signed metadata, discovery/access initiation; explicitly not compromised-tool behavior | VERIFIED |
| Progent | `shi2025progent` | Deterministic policy checks over tool names/arguments before execution | VERIFIED |
| CaMeL | `debenedetti2025camel` | Trusted-query control/data-flow separation and capabilities at tool-call time | VERIFIED |
| ChainCaps | `jiang2026chaincaps` | Monotonic capability attenuation under trusted manifests and proxy-visible explicit flows | VERIFIED |
| MCP-Guard | `xing2026mcpguard` | MCP-specific prompt/attack detection pipeline; not an effect mediator | VERIFIED |
| AgentDojo | `debenedetti2024agentdojo` | Dynamic tool-agent security evaluation environment, not effect mediation | VERIFIED |

## B. Supporting foundations

The following should be retained only if used directly in the final prose:

- capability security and confused-deputy literature;
- TUF/in-toto/Sigstore for supply-chain identity, clearly separated from runtime
  effect integrity;
- intrusion/anomaly detection only where it explains operating points;
- Byzantine/N-version literature only for the unavailable-independent-witness
  comparison; and
- property-based testing only if the adaptive/ablation generator uses it.

The existing `paper/references.bib` contains 62 entries, most explicitly marked
`[U]`. Those markers are correct warnings, not publication-ready metadata.

## C. Completed verification records

### `mcp2025tools`

- **Primary URL:** https://modelcontextprotocol.io/specification/2025-11-25/server/tools
- **Identity:** Model Context Protocol specification, “Tools,” revision
  2025-11-25.
- **Claim checked:** `tools/list` exposes name, description, and `inputSchema`;
  `tools/call` carries a tool name and arguments and returns server-authored
  content/`isError`; tool annotations are untrusted unless the server is
  trusted.
- **Exact source location:** Tools §§ Protocol Messages and Data Types.
- **Does not support:** that declared schemas or returned content prove the
  server's external effect.
- **Verified:** 2026-09-21.

### `bishop1996toctou`

- **Primary URL:** https://www.usenix.org/legacy/publications/compsystems/1996/spr_bishop.pdf
- **Identity:** Matt Bishop and Michael Dilger, “Checking for Race Conditions
  in File Accesses,” *Computing Systems* 9(2), pp. 131–152, Spring 1996.
- **Claim checked:** a name-to-object binding can change between repeated
  references, creating a file-access race.
- **Exact source location:** abstract and paper metadata on the author's UC
  Davis page; publisher copy linked there.
- **Does not support:** calling the distributed declaration/implementation gap
  a classical TOCTOU instance with identical mechanics; our use is analogy and
  lineage.
- **Verified:** 2026-09-21.

### `chen2018metamorphic`

- **Primary DOI:** https://doi.org/10.1145/3143561
- **Identity:** T. Y. Chen et al., “Metamorphic Testing: A Review of Challenges
  and Opportunities,” *ACM Computing Surveys* 51(1), Article 4, pp. 4:1–4:27,
  2018.
- **Claim checked:** metamorphic relations express necessary properties across
  source/follow-up inputs and outputs and can alleviate the oracle problem.
- **Exact source location:** abstract; §1, pp. 1–2 of the author manuscript.
- **Does not support:** sound detection when the system under test is an
  adaptive adversary controlling every observed output.
- **Verified:** 2026-09-21.

### `liang2009alcatraz`

- **Primary DOI:** https://doi.org/10.1145/1455526.1455527
- **Identity:** Zhenkai Liang, Weiqing Sun, V. N. Venkatakrishnan, and R. Sekar,
  “Alcatraz: An Isolated Environment for Experimenting with Untrusted
  Software,” *ACM TISSEC* 12(3), Article 14, 37 pages, 2009.
- **Claim checked:** one-way isolated execution keeps writes out of host state,
  allows inspection, then rolls back or commits accepted changes; it also
  defines commit consistency and discusses state-based commit.
- **Exact source location:** abstract; §§1.1–1.2; §§4.1–4.2.
- **Does not support:** novelty for staging/commit itself, nor automatic semantic
  approval of an MCP effect. It is direct architectural lineage that the paper
  must credit.
- **Verified:** 2026-09-21.

### `porter2009txos`

- **Primary DOI:** https://doi.org/10.1145/1629575.1629591
- **Primary full text:**
  https://www.sigops.org/s/conferences/sosp/2009/papers/porter-sosp09.pdf
- **Identity:** Donald E. Porter, Owen S. Hofmann, Christopher J. Rossbach,
  Alexander Benn, and Emmett Witchel, “Operating System Transactions,”
  *SOSP 2009*, pp. 161–176.
- **Claim checked:** TxOS implements transactional system-call execution in a
  modified Linux kernel and uses private/versioned kernel state so updates are
  isolated until commit or abort.
- **Exact source location:** abstract and §§1–3 of the SOSP implementation
  paper. The related HotOS position paper is not used as the load-bearing
  implementation citation.
- **Does not support:** an application-layer MCP contract or unmodified remote
  server integration; TxOS changes the OS abstraction.
- **Verified:** 2026-09-21.

### `shi2025progent`

- **Primary DOI:** https://doi.org/10.48550/arXiv.2504.11703
- **Identity:** Tianneng Shi et al., “Progent: Securing AI Agents with Privilege
  Control,” arXiv:2504.11703v3 (submitted 2025, revised 2026).
- **Claim checked:** symbolic policies constrain tool names and arguments; every
  tool call is checked deterministically; expansions require approval while
  safe narrowing may proceed.
- **Exact source location:** abstract; §§4.1–4.3 and §6 of v3.
- **Does not support:** post-execution verification that a compromised tool
  server actually honored an allowed call. This is the decisive comparison to
  MCPGate's effect-admission layer.
- **Verified:** 2026-09-21.

### `debenedetti2024agentdojo`

- **Primary DOI:** https://doi.org/10.52202/079017-2636
- **Identity:** Edoardo Debenedetti et al., “AgentDojo: A Dynamic Environment
  to Evaluate Prompt Injection Attacks and Defenses for LLM Agents,” NeurIPS
  2024 Datasets and Benchmarks Track, volume 37.
- **Claim checked:** an extensible, stateful evaluation environment containing
  97 realistic tasks and 629 security test cases for tool-using agents over
  untrusted data.
- **Exact source location:** official proceedings abstract and paper §1.
- **Does not support:** MCP-specific declaration analysis or enforcement of a
  server's real filesystem effects.
- **Verified:** 2026-09-21.

### `buhler2026agentbound`

- **Primary DOI:** https://doi.org/10.1145/3808103
- **Primary full text:**
  https://programming-group.com/assets/pdf/papers/2026_AgentBound-Securing-Execution-Boundaries-of-AI-Agents.pdf
- **Identity:** Christoph B{\"u}hler, Matteo Biagiola, Luca Di Grazia, and Guido
  Salvaneschi, “AgentBound: Securing Execution Boundaries of AI Agents,”
  *Proceedings of the ACM on Software Engineering* 3 (FSE), Article FSE096,
  24 pages, 2026.
- **Claim checked:** AgentManifest declares resource capabilities and AgentBox
  transparently confines unmodified MCP servers with container-level
  filesystem, network, environment, and process controls.
- **Exact source location:** §§2.3, 3.2--3.3, and 4.2; especially p. 5 and
  pp. 15--16.
- **Does not support:** preventing malicious behavior that stays within an
  allowed resource boundary. The paper calls this the semantic-gap or
  unauthorized-misuse problem and reports permitted-endpoint parameter misuse
  and SQL injection as examples. MCPGate's distinct question is whether an
  allowed filesystem invocation produced the exact approved content/path
  before that state is admitted to the trusted store.
- **Verified:** 2026-09-21.

### `li2025safeflow`

- **Primary DOI:** https://doi.org/10.48550/arXiv.2506.07564
- **Identity:** Peiran Li et al., “SAFEFLOW: A Principled Protocol for
  Trustworthy and Transactional Autonomous Agent Systems,”
  arXiv:2506.07564v3, 2025.
- **Claim checked:** SafeFlow combines information-flow labels with
  transactional logging, status tracking, dependency-aware localized rollback,
  replay/replanning, and multi-agent concurrency control.
- **Exact source location:** abstract; §§3.2 and C.2; Appendix A. Version v3 is
  cited because arXiv warns that former versions contain unrelated content or
  could not be converted correctly.
- **Does not support:** atomic undo of an arbitrary non-transactional external
  world effect. Its prose describes logged actions, local recovery, and
  compensating-style rollback; therefore the MCPGate paper will not portray it
  as proving general external-effect rollback.
- **Verified:** 2026-09-21.

### `jiang2026chaincaps`

- **Primary DOI:** https://doi.org/10.48550/arXiv.2605.26542
- **Identity:** Xiaochong Jiang et al., “ChainCaps: Composition-Safe Tool-Using
  Agents via Monotonic Capability Attenuation,” arXiv:2605.26542v4; AIWILD at
  ICML 2026.
- **Claim checked:** a transparent MCP proxy propagates sink-specific budgets
  by intersection so authority cannot increase through explicit tool
  composition.
- **Exact source location:** abstract and arXiv publication/version metadata.
- **Does not support:** hidden/implicit flows, untrusted manifests, or data
  movement the proxy cannot see; the authors explicitly limit their claims to
  explicit-flow composition safety under trusted manifests and proxy-visible
  movement. It therefore complements rather than subsumes post-execution
  filesystem effect admission.
- **Verified:** 2026-09-21.

### `bartocci2018rv`

- **Primary DOI:** https://doi.org/10.1007/978-3-319-75632-5_1
- **Identity:** Ezio Bartocci, Yli{\`e}s Falcone, Adrian Francalanza, and Giles
  Reger, “Introduction to Runtime Verification,” in *Lectures on Runtime
  Verification*, LNCS 10457, pp. 1–33, Springer, 2018.
- **Claim checked:** runtime verification evaluates executions through
  generated/collected events and traces, making the monitor's observation
  surface part of the assurance boundary.
- **Does not support:** inferring a hidden external effect from a trace wholly
  controlled by the system under test.
- **Verified:** 2026-09-21.

### `watson2010capsicum`

- **Primary URL:**
  https://www.usenix.org/legacy/events/sec10/tech/full_papers/Watson.pdf
- **Identity:** Robert N. M. Watson, Jonathan Anderson, Ben Laurie, and Kris
  Kennaway, “Capsicum: Practical Capabilities for UNIX,” USENIX Security 2010.
- **Claim checked:** Capsicum adds capability mode and fine-grained descriptor
  rights to commodity UNIX, removes access to ambient global namespaces, and
  supports application compartmentalization.
- **Does not support:** deriving an MCP per-call content contract or validating
  which bytes an allowed writer produced. Applications must be adapted to use
  Capsicum's primitives.
- **Verified:** 2026-09-21.

### `klein2009sel4`

- **Primary DOI:** https://doi.org/10.1145/1629575.1629596
- **Primary URL:**
  https://sel4.systems/Research/pdfs/sel4-formal-verification-os-kernel.pdf
- **Identity:** Gerwin Klein et al., “seL4: Formal Verification of an OS
  Kernel,” SOSP 2009, pp. 207–220.
- **Claim checked:** machine-checked functional correctness connects an
  abstract kernel specification to the C implementation, under stated compiler,
  assembly, and hardware assumptions.
- **Does not support:** protocol-level contract derivation or external-effect
  admission for an unmodified MCP process.
- **Verified:** 2026-09-21.

### `miller2003capabilitymyths`

- **Primary URL:**
  https://papers.agoric.com/assets/pdf/papers/capability-myths-demolished.pdf
- **Identity:** Mark S. Miller, Ka-Ping Yee, and Jonathan Shapiro, “Capability
  Myths Demolished,” 2003.
- **Claim checked:** distinguishes ACL and capability interpretations and
  analyzes least privilege, confinement, revocation, and confused-deputy
  properties.
- **Does not support:** staging, commit/discard, or schema-derived effect
  validation; it supplies conceptual vocabulary rather than an MCP mechanism.
- **Verified:** 2026-09-21.

### `greshake2023injection`

- **Primary DOI:** https://doi.org/10.1145/3605764.3623985
- **Identity:** Kai Greshake et al., “Not What You've Signed Up For:
  Compromising Real-World LLM-Integrated Applications with Indirect Prompt
  Injection,” AISec 2023, pp. 79–90.
- **Claim checked:** retrieved untrusted data can carry instructions that steer
  an LLM-integrated application and its API/tool calls.
- **Does not support:** the post-approval malicious-server threat model; its
  adversary injects data/instructions into the agent's context.
- **Verified:** 2026-09-21.

### `zhan2024injecagent`

- **Primary DOI:** https://doi.org/10.18653/v1/2024.findings-acl.624
- **Identity:** Qiusi Zhan, Zhixiang Liang, Zifan Ying, and Daniel Kang,
  “InjecAgent,” *Findings of ACL 2024*, pp. 10471–10506.
- **Claim checked:** the benchmark contains 1,054 indirect-prompt-injection test
  cases spanning 17 user tools and 62 attacker tools.
- **Does not support:** independent observation or confinement of a compromised
  tool implementation's filesystem effects.
- **Verified:** 2026-09-21.

### `ruan2024toolemu`

- **Primary URL:** https://openreview.net/forum?id=GEcwtMk1uA
- **Identity:** Yangjun Ruan et al., “Identifying the Risks of LM Agents with
  an LM-Emulated Sandbox,” ICLR 2024 (Spotlight).
- **Claim checked:** ToolEmu uses an LM to emulate tools/sandbox state for
  scalable risk testing and validates findings through human evaluation.
- **Does not support:** treating an LM-emulated world as ground truth for an
  untrusted real server's external side effects.
- **Verified:** 2026-09-21.

### `bhatt2025etdi`

- **Primary DOI:** https://doi.org/10.48550/arXiv.2506.01333
- **Identity:** Manish Bhatt, Vineeth Sai Narajala, and Idan Habler, “ETDI:
  Mitigating Tool Squatting and Rug Pull Attacks in Model Context Protocol
  (MCP) by using OAuth-Enhanced Tool Definitions and Policy-Based Access
  Control,” arXiv:2506.01333v1, 2025.
- **Claim checked:** cryptographic identity verification, immutable versioned
  tool definitions, explicit permissions, OAuth, and context-aware policy-based
  access control.
- **Exact source location:** abstract and paper introduction.
- **Does not support:** that an authenticated, unchanged declaration proves the
  invoked server produced the declared external effect.
- **Verified:** 2026-09-21.

### `narajala2025zerotrust`

- **Primary DOI:** https://doi.org/10.48550/arXiv.2504.19951
- **Identity:** Vineeth Sai Narajala, Ken Huang, and Idan Habler, “Securing
  GenAI Multi-Agent Systems Against Tool Squatting: A Zero Trust Registry-Based
  Approach,” arXiv:2504.19951v1, 2025.
- **Claim checked:** administrator-controlled registration, centralized
  discovery, signed metadata, policy filtering, and JIT credentials.
- **Exact source location:** abstract; §§IV–V; limitations §VII-C.
- **Does not support:** runtime behavioral integrity of an approved but
  compromised tool; the paper itself says its scope is primarily discovery and
  access initiation and not tool vulnerabilities.
- **Verified:** 2026-09-21.

### `debenedetti2025camel`

- **Primary DOI:** https://doi.org/10.48550/arXiv.2503.18813
- **Identity:** Edoardo Debenedetti et al., “Defeating Prompt Injections by
  Design,” arXiv:2503.18813v2, 2025.
- **Claim checked:** CaMeL extracts control/data flows from a trusted query and
  uses capabilities and tool-call security policies to limit unauthorized data
  flows even when model inputs are untrusted.
- **Exact source location:** abstract and paper architecture/security sections.
- **Does not support:** verification that a separately compromised MCP server
  honors an allowed effect; its principal adversary is prompt injection into
  the agent's data/control flow.
- **Verified:** 2026-09-21.

### `xing2026mcpguard`

- **Primary DOI:** https://doi.org/10.18653/v1/2026.findings-acl.240
- **Identity:** Wenpeng Xing et al., “MCP-Guard: A Multi-Stage Defense-in-Depth
  Framework for Securing Model Context Protocol in Agentic AI,” *Findings of
  ACL 2026*, pp. 4877–4889.
- **Claim checked:** a three-stage detection pipeline combines static scanning,
  neural/E5 detection, and LLM arbitration; MCP-AttackBench has 70,448 samples.
- **Exact source location:** ACL Anthology abstract; paper method and appendix.
- **Does not support:** deterministic post-execution effect mediation or a
  guarantee that server-reported results equal world state. It is a detection
  baseline/property comparison, not equivalent architecture.
- **Verified:** 2026-09-21.

## D. Verification record format

For each reference moved to VERIFIED, record:

```text
BibTeX key:
Primary URL/DOI:
Title:
Authors:
Venue/year:
Pages/version:
Claim supported:
Exact section/page checked:
What it does NOT support:
Verified by/date:
```

This ledger will be updated together with `references.bib`; a reference is not
considered fixed merely because its arXiv identifier resolves.

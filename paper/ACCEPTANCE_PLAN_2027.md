# EffectSeal: plan to a competitive USENIX Security 2027 submission

Written 2026-10-08. Target: USENIX Security 2027, Cycle 2 (registration
2027-01-19, paper 2027-01-26, artifacts 2027-01-29, all AoE). From today this
plan replaces the dates in `EXECUTION_CALENDAR.md`. It builds on the
pre-registered design in `NETWORK_SQL_EXTENSION_PLAN.md` (N3 contract,
broker, frozen attacks) and does not repeat it.

## 1. Why this plan exists

The current manuscript is sound but narrow. A USENIX reviewer will raise four
points, and each one has a fix below:

| Reviewer objection | Fix in this plan |
|---|---|
| "Most real MCP servers call remote APIs; files and SQLite are a toy scope." | Workstream N: network-effect admission on real API servers (Sec. 3) |
| "Is the rug-pull threat real? No incident is cited." | Workstream R: real incidents, led by `postmark-mcp` 1.0.16 (Sec. 4) |
| "Baselines are your own re-implementations." | Workstream B: run the real tools at their strongest settings (Sec. 5) |
| "4 held-out servers and 12.5% false blocks are not convincing." | Workstream H: new dev cycle, then a larger frozen held-out batch (Sec. 6) |

Rough outlook: as submitted today, USENIX acceptance is about 10–20%. With N, R
and B done well it moves to roughly 25–35%. These are judgment calls, not
measurements.

## 2. The headline case: postmark-mcp 1.0.16

This single real incident matches the paper's thesis almost exactly. It should
become the running example in the introduction.

- A publisher released `postmark-mcp` on npm, copying Postmark's official
  server. Versions 1.0.0–1.0.15 were clean; 1.0.16 (17 Sep 2025) added one line
  that BCC'd every outgoing email to an attacker address.
- The tool declarations, the agent's call (`sendEmail(to=...)`), and the
  server's response ("email sent") all stayed honest. Only the effect changed.
- Predicted outcome per defense (to be measured, not assumed):

| Defense | Decides on | Stops the BCC? (prediction) |
|---|---|---|
| mcp-scan / Snyk Agent Scan tool pinning | hash of tool descriptions | No: descriptions unchanged |
| Progent-style call policy | the call and its arguments | No: the call is the approved one |
| AgentBound / ToolHive / sandbox-runtime | allowed hosts | No: request goes to the allowed Postmark host |
| Docker MCP Gateway `--block-secrets` | secret-looking payloads | Probably no: a BCC address is not a secret |
| LLM judge, response auditor | transcript | No: transcript is honest |
| EffectSeal-N (request template) | the outgoing request itself | Yes: the pinned template has no `Bcc` field |

Ethics: do not download the malicious package. Rebuild it from the official
MIT-licensed source (`github.com/ActiveCampaign/postmark-mcp`) plus a
one-field change, send only with Postmark's test token or to a local mock,
and point the BCC at a sink we own.

## 3. Workstream N: network-effect admission

### 3.1 Design (extends the N3 contract with pin-time templates)

Network sends cannot be undone, so admission happens **before** each request
leaves, not after the call.

1. **No direct egress.** The server container keeps `--network=none` plus one
   route to a trusted broker (`HTTPS_PROXY`). Raw TCP, UDP, and DNS are denied,
   as the existing broker tests already show.
2. **TLS termination.** The broker terminates TLS with a per-run CA injected
   into the container (`NODE_EXTRA_CA_CERTS`, `SSL_CERT_FILE`,
   `REQUESTS_CA_BUNDLE`). Servers that pin certificates are excluded by a
   written rule and counted.
3. **Credential injection.** The server receives a dummy API token. The broker
   swaps in the real one on approved requests only. A malicious server
   therefore never holds the user's credential, so token theft fails by
   construction.
4. **Request templates.** At pin time, record the honest requests under
   perturbed arguments and anti-unify them with the existing
   `template_inference.py` over a canonical view: method, host, path template,
   sorted query, canonical JSON body, allowed headers, request count. Slack is
   computed per field, as for files.
5. **Pre-send check.** Each write request (POST/PUT/PATCH/DELETE) must match
   exactly one rule in the instantiated template or it is refused and the call
   is marked refused/UNKNOWN. GETs pass only through read templates with a
   count bound. A call whose later request is refused may have already sent an
   earlier one; report this as "partial", never hide it.
6. **Ledger and replay.** Reuse `SQLiteAllowanceLedger`; one allowance per
   approved write request.
7. **Independent oracle.** The effect is the request that leaves the broker.
   Capture it on the far side, with a sink or mock API and packet capture,
   never from the server's response.

### 3.2 Formal model

Extend `formal/EffectSeal.tla` with an irreversible `Send` step. Invariant: every
transmitted write request matches the contract. Ablations that must
produce counterexamples: check-after-send, server-held credential (token
exfiltration), split reservation, no replay guard.

### 3.3 Servers (frozen by a written rule before any outcome)

Pick servers with free test modes or easy mocks. Candidate pool, to be
selected by rule:

- Postmark (official ActiveCampaign server; Postmark test token)
- GitHub (official `github/github-mcp-server` or a popular Node server;
  throwaway repo)
- Notion (official Node server; free workspace)
- Stripe agent toolkit MCP (test mode)
- Slack, Linear, Sentry, Resend/SendGrid (free tiers)

Run bulk experiments against **record-replay mocks** of each API, so the
artifact runs without keys. Confirm a subset live against the real API, and
report both.

Target: 5–6 development servers and 4–6 held-out network servers.

### 3.4 Attacks (source-level rug-pull diffs, modeled on real incidents)

For network servers, realize attacks as small diffs to real source code, like
postmark-mcp, rather than library hooks. This also works for Go servers.

| ID | Attack | Real-world anchor |
|---|---|---|
| N-A1 | Add BCC/CC recipient | postmark-mcp 1.0.16 |
| N-A2 | Swap recipient, repo, or owner | effect diversion |
| N-A3 | Change body or payload | content substitution |
| N-A4 | Extra write on the **same** host (e.g. add collaborator, create gist with data) | defeats host allow-lists |
| N-A5 | Exfiltrate to a different host | domain allow-list catches it; include for fairness |
| N-A6 | Read and send the API token | blocked by credential injection |
| N-A7 | Replay or duplicate send | allowance |
| N-A8 | Silent no-op with success reply | completion vs confinement |
| N-A9 | Reverse shell at startup | JFrog's PyPI MCP packages; confinement test |

### 3.5 Success criterion (pre-register before scored runs)

Zero unapproved write requests leave the broker. At least 95% honest
completion on development servers. Held-out false blocks reported with 95%
intervals. Every direct-egress bypass is blocked.

**Go/no-go gate N (2026-11-18):** if this is not met on at least 5 servers,
network becomes a single postmark case study in the Discussion, not a
contribution. The paper then uses framing (b) in Sec. 8.

## 4. Workstream R: real incidents and measurement

### 4.1 Incidents to cite

Verify each against the primary source and add it to `REFERENCE_LEDGER.md`
before it enters `references.bib`. Several numbers differ between news sources:
cite the primary report and avoid the disputed counts.

| Incident | What it shows | Primary / best source |
|---|---|---|
| postmark-mcp 1.0.16 (Sep 2025) | rug pull after 15 clean versions; honest reply, diverted effect | Postmark statement, 25 Sep 2025: postmarkapp.com/blog/information-regarding-malicious-postmark-mcp-package. Koi's original post (koi.ai/blog/postmark-mcp-npm-malicious-backdoor-email-theft) now redirects to Palo Alto Networks, so cite a Wayback snapshot. News: The Hacker News, 2025/09 "first-malicious-mcp-server-found". |
| @lanyer640/mcp-runcommand-server (Sep 2025) | clean first release, malicious update a month later | JFrog, 19 Oct 2025: research.jfrog.com/post/3-malicious-mcps-pypi-reverse-shell/ (also covers 3 PyPI MCP packages with reverse shells) |
| MCPoison, CVE-2025-54136 (Aug 2025) | Cursor bound trust to the config **name**, not to what runs | Check Point Research: research.checkpoint.com/2025/cursor-vulnerability-mcpoison/ |
| EscapeRoute, CVE-2025-53109/53110 (Jul 2025) | official filesystem server's own path and symlink checks were bypassable | Cymulate: cymulate.com/blog/cve-2025-53109-53110-escaperoute-anthropic/ (maps to the paper's link-alias attack) |
| CVE-2025-6514 mcp-remote (Jul 2025) | a malicious server can reach code execution on the client | JFrog advisory: research.jfrog.com/vulnerabilities/mcp-remote-command-injection-rce-jfsa-2025-001290844/ |
| s1ngularity / Nx (Aug 2025) | malware drove local AI CLIs to hunt secrets | GitGuardian: blog.gitguardian.com/the-nx-s1ngularity-attack-inside-the-credential-leak/ |
| Clinejection, cline@2.3.0 (Feb 2026) | stolen publish token produced an unauthorized release of an agent tool | Snyk analysis; The Hacker News 2026/02 "cline-cli-230-supply-chain-attack" |
| SANDWORM_MODE / McpInject (Feb 2026) | npm worm writes rogue MCP servers into agent configs | Socket report (find primary URL); heise.de/-11190731; The Hacker News 2026/02 |

Use the last three in Background as "how honest packages become malicious":
stolen maintainer tokens turn a trusted package into a rug pull at scale.

### 4.2 Academic related work to add (verified on arXiv, 2026-10-08)

- Zhao, Liu, Ruan, Li, Liang. *When MCP Servers Attack: Taxonomy, Feasibility,
  and Mitigation.* arXiv:2509.24272, Sep 2025. Malicious servers as
  adversaries; 12 attack categories; scanners insufficient.
- Huang et al. *From Component Manipulation to System Compromise:
  Understanding and Detecting Malicious MCP Servers.* arXiv:2604.01905, Apr
  2026. 114 PoC malicious servers; Connor detector (a detection baseline to
  discuss).
- Li, Gao. *A First Look at the Security Issues in the Model Context Protocol
  Ecosystem.* arXiv:2510.16558, Oct 2025 (v2 Apr 2026). 67,057 servers across
  six registries.
- Padilla. *Exposed by Design: A Dynamic Security Assessment of Internet-Facing
  MCP Servers at Scale.* arXiv:2608.00150, Jul 2026. Remote servers; supports
  the local-versus-remote scope argument.
- MCP-38 threat taxonomy, arXiv:2603.18063 (verify authors).
- Progent is now titled *Progent: Securing AI Agents with Privilege Control*
  (arXiv v3, 14 May 2026); update the bib entry.

### 4.3 Two cheap measurements (motivation, about 1 week)

- **M1 – local versus remote.** Re-harvest the official registry
  (`/v0.1/servers`) and count entries with `packages` (npm/PyPI/OCI, stdio)
  versus `remotes`. Then, among local servers, estimate how many make outbound
  HTTP (declared API-key env vars; HTTP client dependencies). This turns "most
  servers need the network" into a number, and it bounds EffectSeal's
  reachable share honestly.
- **M2 – rug-pull exposure.** For npm/PyPI-backed servers: releases in the last
  90 days, publisher or maintainer changes, and launch configs that float to
  `@latest` (`npx -y pkg`). This measures how often the code behind an
  approved server changes.

## 5. Workstream B: strong, comparable baselines

Rule: configure every baseline at its **strongest** setting, freeze the
configs before scored runs, and publish them. A weak baseline gets the paper
rejected faster than a weak result.

| Baseline | Category | Availability (checked 2026-10-08) | Strongest configuration |
|---|---|---|---|
| **AgentBound** (Bühler et al., FSE 2026) | declared permissions + container | Zenodo artifact v2: doi 10.5281/zenodo.19571298 | its auto-generated manifest, then hand-tightened to the minimum that passes honest runs |
| **mcp-scan / Snyk Agent Scan** | rug-pull detection by tool pinning | open source (Invariant Labs, now Snyk) | pin at approval; rescan before every launch |
| **Progent** | call-level privilege policy | paper only on arXiv; no code link found. Check `github.com/sunblaze-ucb`; else email the authors; else keep a faithful re-implementation and say so | strictest per-task policy |
| **ToolHive `--isolate-network`** | L7 egress allow-list proxy | open source (Stacklok) | `allow_host` = exactly the vendor API host and port |
| **Anthropic sandbox-runtime (`srt`)** | OS sandbox + domain allow-list | open source, npm `@anthropic-ai/sandbox-runtime` | write only to the workspace; allow only the API domain |
| **Docker MCP Gateway** | gateway, `--block-network`, `--block-secrets` | open source (`github.com/docker/mcp-gateway`) | both flags on |
| **LLM judge** | transcript monitor | API | current judges, plus one non-OpenAI model so the result is not vendor-specific |
| Response auditor, static least privilege | ours | in repo | unchanged |
| EffectSeal ablations | ours | in repo | destination-only; content-blind; no credential injection |

For files, the same table applies with AgentBound, srt, and ToolHive in place
of the current plain sandbox. Report each baseline's honest-run false blocks,
not only attacks stopped.

## 6. Workstream H: fix template false blocks, then a bigger held-out batch

1. New development cycle (allowed, documented in Appendix C): validity check
   during pinning (perturbed call must not become a silent no-op),
   side-file-aware views (SQLite WAL), more varied long-text training.
2. Re-freeze the library hash.
3. **Held-out batch 3:** at least 10 new file/SQLite servers selected by a
   written rule, plus the network held-out set. Report false blocks with
   server-level intervals.
4. Keep batch 2's 12.5% in the paper as history; never overwrite it.

## 7. Timeline (16 weeks)

| Week | Dates | Deliverables | Gate |
|---|---|---|---|
| 1 | Oct 8–14 | This plan committed; network pre-registration v2 (attacks, servers rule, baseline configs); fetch AgentBound artifact, mcp-scan, ToolHive, srt, Docker gateway; Progent code check / email; start citation ledger | — |
| 2 | Oct 15–21 | Broker: TLS termination, CA injection, credential injection, canonical request view; postmark honest run end to end in container | **G1:** postmark honest workflow passes through broker |
| 3 | Oct 22–28 | Request templates in `template_inference.py`; pre-send check; ledger; unit tests; M1 + M2 measurement | — |
| 4 | Oct 29–Nov 4 | Pin 5–6 network dev servers; mocks recorded; postmark 1.0.16 reconstruction; N-A1..A9 attack diffs; TLA+ `Send` extension | — |
| 5 | Nov 5–11 | All baselines installed and configured (files + network); configs frozen and committed | — |
| 6 | Nov 12–18 | Network matched evaluation (dev) with all baselines | **G2:** network success criterion met, or fallback |
| 7 | Nov 19–25 | Template dev cycle (Workstream H steps 1–2); file baselines re-run with AgentBound/srt/ToolHive | — |
| 8 | Nov 26–Dec 2 | Held-out batch 3 (files) + network held-out, frozen and scored | — |
| 9 | Dec 3–9 | Real agents with network servers (postmark, GitHub tasks; GPT + one non-OpenAI model); live-API confirmation subset | — |
| 10 | Dec 10–16 | Overhead (p50/p95 per request); 100-trial races for network allowance; LLM judges incl. non-OpenAI | **G3:** all scored runs frozen; no new experiments after Dec 16 |
| 11–12 | Dec 17–30 | Rewrite: new intro (postmark), threat model + network, RQ for network, results, related work, ethics; new figures; page cuts | — |
| 13 | Dec 31–Jan 6 | Artifact: clean Linux clone reproduces everything; mocks let reviewers run without API keys | — |
| 14 | Jan 7–13 | Internal review by the supervisor and one outside reader; claim and citation audit | **G4:** every number traced to a JSON file |
| 15 | Jan 14–20 | Anonymous export; artifact URL; **registration Jan 19** | — |
| 16 | Jan 21–26 | Final proof; upload by Jan 25; **deadline Jan 26** | — |

## 8. Paper changes

**Framing.** (a) If gate G2 passes: "EffectSeal admits file, database, and
network effects of local MCP servers." (b) If not: keep files/SQLite as the
contribution, add the postmark case study, and argue scope with M1: local,
high-integrity state is where rug pulls do lasting damage, and vendor-hosted
remote servers are as trusted as the API they front.

**Page budget.** The 13-page body is full. To fit about 1.5 pages of network
material:

- shorten Sec. 3 (registry auditor details to an appendix), about −0.5 page;
- drop or shrink Fig. 2 (two worlds), about −0.4 page;
- merge Fig. 6 into Table 5, about −0.3 page;
- trim Sec. 5 and Related Work, about −0.3 page.

**Scope statement.** Say plainly that remote, vendor-hosted MCP servers are out
of scope, because no client-side boundary can see inside them. Give the M1
share.

**Ethics appendix.** Update it for the rebuilt malicious package, test-mode
APIs, a sink address, and no messages to real people.

## 9. Things not to do before January

- No IEEE S&P (17 Nov): too soon for N, B, and H.
- No PostgreSQL, process-spawn mediation, or user study.
- No claim about remote servers.
- No new experiment after Dec 16 (gate G3).

## 10. Risks

| Risk | Mitigation |
|---|---|
| TLS termination breaks some servers (pinned certs, odd SDKs) | exclusion rule written in advance; count and report exclusions |
| Vendor rate limits or terms of service | mocks for bulk runs; live runs small, own accounts only |
| AgentBound artifact hard to run | budget 3 days; if it fails, use its manifests with our container and say so |
| Progent code unavailable | faithful re-implementation, stated clearly; the paper already does this |
| Network partial effects confuse results | report "partial" as its own outcome |
| Time | gates G2 and G3 are hard; fallback framing (b) is ready |

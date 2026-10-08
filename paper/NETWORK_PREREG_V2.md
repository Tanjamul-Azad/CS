# Pre-registration: network-effect admission (RQ-N), version 2

Committed 2026-10-08, before any scored network run. It supersedes the RQ6
section of `NETWORK_SQL_EXTENSION_PLAN.md` in two places: contracts for new
calls come from pin-time **request templates** (not exact request bytes), and
the broker **terminates TLS and injects credentials**. Everything else in that
plan (no direct egress, bypass suite, oracle, go/no-go rule) still holds.
Changes after this commit are recorded as dated amendments at the end; scored
results are never overwritten.

## Question

When an untrusted local MCP server can reach the network only through a
trusted broker, does admitting each outbound request against a pin-time
request template stop network effect diversion that every compared defense
misses, at an acceptable cost to honest calls?

## Mechanism under test

`src/mcpgate/request_templates.py` (canonical request view, inference,
instantiation, slack) and `src/mcpgate/egress_proxy.py` (per-run CA, TLS
termination, absolute-form handling, credential injection, `CallGate`).
Unit evidence: `tests/test_egress_proxy.py` (13 tests, passing at commit).

## Server selection rule (frozen now)

Candidates come from the official MCP registry (`/v0.1/servers`), harvested once
and hashed. A candidate qualifies if all of these hold:

1. it has a `packages` entry (npm or PyPI) with stdio transport;
2. it has at least one tool whose honest effect is an outbound HTTP write
   (POST/PUT/PATCH/DELETE) to one vendor API;
3. the vendor offers a free test mode, sandbox account, or documented API
   that we can mock from recorded honest traffic;
4. it uses an open-source license and installs from a pinned version;
5. its HTTP client honours `HTTPS_PROXY`/`HTTP_PROXY` and the injected CA,
   checked in one honest probe (servers that pin certificates are excluded and
   counted);
6. one honest workflow completes against the test mode or mock.

Order: seeded shuffle (seed `20261008`) over qualifying candidates. The first 6
that pass all checks form the development set; the next 6 form the held-out
set. Exclusions are logged with the failed rule. `ActiveCampaign/postmark-mcp`
is added to the development set by name, because its real incident motivates
the attacks; it is reported separately so the shuffled sets stay unbiased.

## Workloads

Per server: one exemplar call per write tool, chosen from its README before any
attack run. Pin-time training: the exemplar plus 4 perturbations
(`perturb_arguments`, seed fixed per server). Test calls: 12 per server with
unseen arguments (4 short, 4 natural-language, 4 three-times-longer text).

## Attacks (source-level diffs to the pinned version)

Each attack is a minimal diff applied to the server's own source, modeled on the
postmark-mcp 1.0.16 one-line change. The MCP declaration and the server's
response stay byte-identical to the honest version.

| ID | Attack |
|---|---|
| N-A1 | add a Bcc/Cc/extra recipient to the approved write |
| N-A2 | change the recipient, repository, owner, or target object |
| N-A3 | change the payload or body content |
| N-A4 | extra write request to the same allowed host |
| N-A5 | extra request to a different host |
| N-A6 | put data into the credential header, or send the token elsewhere |
| N-A7 | send the approved write twice |
| N-A8 | send nothing, reply success |
| N-A9 | reverse shell or direct socket at startup (confinement test) |

An attack **landed** if, with no defense, the far-side oracle records a
request that differs from the honest one.

## Conditions (configs frozen and committed before scored runs)

| Condition | Configuration |
|---|---|
| No defense | server with direct network |
| Domain allow-list (our broker) | admit any request to the vendor host and port |
| ToolHive `--isolate-network` | `allow_host` = vendor host, `allow_port` = 443 |
| Anthropic sandbox-runtime | network allow-list = vendor domain; writes = workspace |
| Docker MCP Gateway | `--block-network --block-secrets` |
| AgentBound | artifact manifest, hand-tightened to the minimum honest set |
| mcp-scan / Snyk Agent Scan | tools pinned at approval, rescanned before each launch |
| Progent-style policy | strictest per-task argument policy |
| LLM judge | two models from different vendors, prompt from `docs/48` |
| EffectSeal-N | request template, TLS termination, credential injection |
| EffectSeal-N, no credential injection | ablation |

A third-party baseline that cannot be installed or run is reported as such,
with the reason, and is not replaced silently.

## Oracle

The effect is what leaves the boundary. Primary oracle: the record kept by the
far-side mock API (or the vendor's test-mode activity log for live runs).
Secondary: packet capture on the broker's upstream interface. The server's
MCP response is never used.

## Outcomes and metrics

Per call: ADMITTED, REFUSED, PARTIAL (an earlier request was sent before a
later one was refused), INCOMPLETE, UNKNOWN. Reported: landed attacks
prevented, honest completion, false blocks, partials, template slack per tool,
per-request latency p50/p95/p99. Intervals: server-clustered bootstrap, or
server-level Wilson interval when every cell succeeds.

## Success criterion

On the development set: zero unapproved write requests leave the broker,
honest completion of at least 95%, and every N-A9 bypass blocked. On held-out:
results are reported whatever they are, with intervals. If fewer than 5
servers can be run by 2026-11-18 (gate G2 in `ACCEPTANCE_PLAN_2027.md`),
network is reported as a postmark case study only.

## Ethics

No malicious package is downloaded. Attack versions are built locally from
the official source plus a one-feature diff. Live sends use vendor test modes
and addresses we own. No email or message reaches a real person. Artifacts
include mocks, so reviewers need no API keys.

## Amendments

(none yet)

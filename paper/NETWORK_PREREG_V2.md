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

**2026-10-08 (after the Postmark pilot, before any other server).**

1. *Postmark pilot.* `experiments/network_postmark_pilot.py` ran the named
   development server (official ActiveCampaign/postmark-mcp, v2.1.1). In that
   run the server container mounted the whole CA directory, including leaf
   keys. Leaf keys now live in `private/` and later runs mount only `ca.pem`.
   This does not change any decision the broker made.
2. *mcp-scan version.* Current releases (snyk-agent-scan 0.6.x) refuse to run
   without a `SNYK_TOKEN`. We use mcp-scan 0.3.39, the last release line whose
   tool pinning runs locally. A positive control (description change) confirms
   that its pinning works in our setup.
3. *AgentBound logging.* AgentBound's entrypoint prints startup lines on
   stdout, which MCP uses for protocol messages. The harness sends those
   `echo` lines to stderr; the iptables enforcement is unchanged. The diff is
   saved in each result's `meta.json`.
4. *Baselines in the pilot.* The pilot measured no defense, a domain
   allow-list in our broker, AgentBound (real artifact), mcp-scan, and
   EffectSeal-N. ToolHive, sandbox-runtime, Docker MCP Gateway, Progent, and
   the LLM judges are still to run.

**2026-10-09 (before server selection runs).**

5. *Selection procedure, made executable.* `experiments/network_select_servers.py`
   implements the selection rule over the 2026-10-08 harvest
   (`data/raw/registry_latest_2026-10-08.jsonl.gz`, hash in
   `artifact/results/m1_local_remote_2026-10-08.raw.sha256`). Rule 1 is read
   as: npm or PyPI package, stdio transport, at least one declared secret
   environment variable. Servers that require positional package arguments are
   excluded. Rule 3 (test mode or mockable API) is met by a generic recording
   mock that echoes written objects. Rule 6 is checked by calling up to three
   write-like tools (by name; not read-only, not destructive, no delete) with
   arguments generated from the input schema, as an agent would fill them.
   The README-based exemplar in "Workloads" is replaced by these
   schema-generated arguments, because 12 servers cannot be hand-curated
   without seeing their behavior first. A server qualifies when one such call
   returns without error and sends at least one POST/PUT/PATCH to exactly one
   host. Screening stops at 12 qualifiers or 200 candidates.

**2026-10-09.** 6. *Harness fix, selection restarted.* The first selection run
(`network_selection_20261009-*`, first five candidates) built invalid Docker
tags for scoped npm packages (`@scope/name`), which wrongly excluded them as
install failures. The tag is now sanitized, and selection restarts from rank 0
in a new result directory; the aborted run's log is kept unchanged.

**2026-10-09.** 7. *Container cleanup, selection restarted again.* Closing an
MCP session's stdin did not stop every server container, so containers from
earlier sessions kept running (idle) in the broker's namespace. They sent no
requests after their session (every attack request happens inside its own
call), so the Postmark pilot and AgentBound decisions are unaffected, but the
leak consumed memory during screening. Server containers are now named and
removed after each session, and only `ca.pem` is mounted into them. The second
selection run (stopped at rank 19, three qualifiers) is kept; selection
restarts from rank 0 in a new result directory.

**2026-10-09.** 8. *Per-candidate timeout, resumed.* Selection run 3 hung at rank
21 on a tool call that never returned. Screening now has a 120-second
watchdog: a candidate whose session does not finish in time is recorded as not
qualified. Run 3 resumes in the same directory from rank 21; ranks 0–20 are
kept as logged (the rule and the order are unchanged).

**2026-10-09.** 9. *Matched evaluation method.* `experiments/network_matched_eval.py`
pins each selected server (exemplar plus perturbations; fields whose
perturbation errors are held fixed), runs K honest test calls with unseen
arguments behind the EffectSeal-N gate, and measures the attack side as a
transformation of each captured honest request rather than by modifying any
server. The eight transformations realize Table N-A1..N-A8 (add field, change
value, append text, extra same-host request, extra other-host request,
credential-header channel, duplicate send, silent no-op). Each defense is then
asked whether it admits the variant: EffectSeal-N by its instantiated request
template; the destination policy (what ToolHive, AgentBound, and a domain
allow-list all decide on, as the Postmark matched pilot confirmed) by whether
the request host is the approved one. This measures what each check admits
without running per-server malicious code, so it is fully reproducible from the
captured traffic and the inferred templates.

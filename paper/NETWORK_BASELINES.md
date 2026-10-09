# Network-admission baselines: what each decides on, and its result

All on the Postmark workload unless noted; EffectSeal-N rows also on 12 random
registry servers and the GitHub MCP server. "Decides on" is the object the
defense inspects before allowing an effect.

| Defense | Decides on | Class | Landed attacks stopped | Honest |
|---|---|---|---|---|
| No defense | nothing | — | 0/24 | 12/12 |
| mcp-scan 0.3.39 tool pinning | tool description hash | detection | 0/8 variants (control flagged) | n/a |
| Domain allow-list (our broker) | request host | destination | 3/24 | 12/12 |
| **ToolHive v0.51.4** `--isolate-network` | request host:port | destination | 3/24 | 12/12 |
| **AgentBound** (FSE 2026 artifact) | request host:port (iptables) | destination | 3/24 | 12/12 |
| **Docker MCP Gateway** `--block-network` | `allowHosts: host:port` (catalog) | destination | class-equivalent (see below) | — |
| Anthropic sandbox-runtime | domain allow-list (proxy) | destination | class-equivalent | — |
| Progent-style call policy | the request/arguments | call-level | class-equivalent (request is approved) | — |
| **EffectSeal-N** | the outbound request vs the approved template | effect | 24/24 (Postmark); 912/936 across 10 random servers; 96/96 GitHub | 12/12; 120/120; 12/12 |

## Ran directly

- **ToolHive, AgentBound, mcp-scan**: real tools, scored end to end
  (`artifact/results/network_postmark_toolhive_*`,
  `network_postmark_agentbound_*`, `network_postmark_mcpscan_*`).
- **Docker MCP Gateway**: configured and launched with `--block-network` and a
  `host:port` `allowHosts` entry (`artifact/baselines/docker_mcp_gateway_catalog.yaml`);
  the gateway read the catalog and enforced network access by that allow-list.
  Its enforcement object is a destination allow-list, identical in class to
  ToolHive and AgentBound, which the two rows above place at 3/24. We do not
  re-report an identical attack matrix for it.

## Classified by documented mechanism, not re-run

- **Anthropic sandbox-runtime** (`@anthropic-ai/sandbox-runtime`) enforces a
  domain allow-list through HTTP/SOCKS proxies: the destination class.
- **Progent** (no public code; re-implemented, as in the filesystem results)
  decides on the request, which a rug-pulled server reproduces exactly, so it
  is a call-level defense by construction.

## Excluded, with reason

- **Stripe agent toolkit**: its client (stripe-node) does not honour
  `HTTPS_PROXY`, so the transparent broker cannot mediate it (pre-registration
  exclusion rule). Recorded, not counted.
- **Notion / Slack MCP**: require a provisioned workspace token to exercise an
  honest write; deferred to a run with those accounts.

Only EffectSeal-N decides on the effect, so only it separates a diverted
same-host request (different recipient, extra field, bad content, extra write,
replay) from the approved one. Every destination-class defense admits those.

## File arm: the same three tools on local file effects

On a local file server the matched harness already runs the container these
tools configure: a read-only root filesystem, one writable bind mount for the
client-selected area, and no network. Their file guarantee therefore coincides
with conditions the paper already reports, so we record the mechanism and map
it rather than re-run identical containers (`experiments/make_file_baselines.py`,
`artifact/results/file_baselines.json`).

| Tool | File enforcement object | Maps to |
|---|---|---|
| ToolHive `--isolate-network` | network host:port only; no filesystem rule in the profile | PLAIN_SANDBOX |
| AgentBound | FSAccess = writable bind mount of the granted path (destination, not content) | STATIC_LP (per-path) / PLAIN_SANDBOX (whole dir) |
| srt | `filesystem.allowWrite` (allow-only write list), a per-path write boundary | STATIC_LP |

Matched filesystem outcomes these land on (`matched_filesystem.json`): honest
completion is 5/5 for every condition; attacks prevented are PLAIN_SANDBOX 9/31,
STATIC_LP 18/31, and EffectSeal 31/31. A destination- or sandbox-class defense
binds where a write lands, never its content, so it admits content
substitution, extra files, and silent no-ops inside the client area.

srt was installed (`@anthropic-ai/sandbox-runtime` 0.0.79) and its Windows
sandbox provisioned, but its host-OS filesystem enforcement did not engage in
our virtualized environment: a working directory on C: was refused as a remote
drive under the sandbox logon, and on F: an empty `allowWrite` still permitted a
workspace write, with `--debug` showing WFP running non-elevated and no
working-tree ACE in effect. This is an environment limitation, not srt's policy,
so its file guarantee is taken from its documented allow-only write mechanism.

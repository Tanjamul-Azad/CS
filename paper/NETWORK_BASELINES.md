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

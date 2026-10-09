# Self-review against published top-venue papers (2026-10-09)

Comparators read for structure and evaluation style (their text is not reused):

- **RLBox**, "Retrofitting Fine Grain Isolation in the Firefox Renderer",
  USENIX Security 2020, Distinguished Paper. Isolation retrofitted into a real
  system; evaluated on six real libraries; deployed in production Firefox.
- **in-toto**, "in-toto: Providing farm-to-table guarantees for bits and bytes",
  USENIX Security 2019. Supply-chain integrity; security evaluated against 30
  historical supply-chain compromises; real deployments.
- **Terrapin**, USENIX Security 2024, Distinguished Paper (already a structural
  model in VENUE_AND_WRITING_STANDARD.md): root cause, concrete attack,
  prevalence measurement, mitigation.
- **Cloak, Honey, Trap**, USENIX Security 2025: defenses against LLM agents,
  evaluated on 11 CTF machines, open-source tool.
- **IsolateGPT**, NDSS 2025: execution isolation for LLM-based agentic systems
  (hub and spokes), overhead under 30% for three quarters of queries.

Concurrent or adjacent work found in this pass that the paper does not yet cite:

- **TrustShiftProbe** (arXiv:2608.23763, 24 Aug 2026): "staged trust" attacks,
  i.e. MCP servers that behave benignly and then switch. Its defense (SHIELD)
  audits server-to-agent payloads against baselines from clean windows and cuts
  attack success from 69.5% to 42.7%. This is the response channel; our attack
  keeps the response honest and changes the effect, and Theorem 1 predicts why a
  response audit has a ceiling. Must be cited and contrasted.
- **Parasites in the Toolchain** (IEEE S&P 2026): injected instructions in
  external data chain legitimate MCP tools into exfiltration. The intent-to-call
  layer; complementary.
- **IsolateGPT** (NDSS 2025): isolation between LLM apps, not admission of a
  tool's effect.

## Figures

| Aspect | Top papers | Ours | Gap and action |
|---|---|---|---|
| First-page figure | Core idea at a glance | Data-driven postmark teaser | None |
| Architecture | One overview figure | Two-phase, two-path figure | None |
| Concrete artifact | RLBox shows code before and after | Templates are only described in prose | **Add a worked example**: the inferred postmark request template, its holes and slack, and the refused Bcc variant |
| Security reasoning | in-toto maps attacks to protections | TLC table only | **Turn the TLC table into a capability table**: adversary capability, the mechanism that stops it, and the invariant or experiment that shows it |
| Multi-model agents | n/a | Agent figure shows the OpenAI runs only | Optional: add the Llama runs to the agent figure |
| Style | Consistent vector figures | Consistent Okabe-Ito, validated palette | None |

## Writing

| Aspect | Top papers | Ours | Action |
|---|---|---|---|
| Running example | Terrapin follows one attack throughout | postmark-mcp throughout | None |
| Density | Results paced over sections | Intro and abstract carry many numbers with different denominators | Keep the intro to three headline numbers; leave the rest to results |
| Security analysis | Explicit section or table | Spread over design and TLC | Capability table (above) |
| Shorthand | Defined once | Cleaned in the last pass | None |

## Positioning

| Aspect | Top papers | Ours | Action |
|---|---|---|---|
| Real-world relevance | in-toto: 30 historical compromises | One measured incident | **Incident coverage table**: each documented MCP incident, what changed, and which defense would stop it, marking measured versus analytical |
| Concurrent work | Cited and contrasted | TrustShiftProbe, Parasites, IsolateGPT missing | **Add all three** |
| Deployability | RLBox in production Firefox; in-toto in products | Library plus harness; no client integration | State the deployment path (pin per version, exemplar, re-pin on update) in Discussion; a production client integration is future work |
| Novelty statement | One crisp insight | "Authorize effects, not calls" plus templates with slack | Keep; avoid "combination" framing as the headline |

## Evaluation

| Aspect | Top papers | Ours | Action |
|---|---|---|---|
| Scale | RLBox six libraries in a real browser; in-toto 30 incidents | 7 local, 4 held-out local, 10 network servers | **New held-out local batch from npm search** (experiment B) |
| Attack realism | Real attacks or real incidents | Network registry attacks are request transformations; only postmark end to end | **Real malicious versions for 2-3 registry servers** (experiment A) |
| Open problems | Stated, sometimes partly addressed | Pin-time poisoning unsolved | **Cross-session template comparison** (experiment C), with its adaptive limit reported |
| Intervals | Reported for headline rates | Matched and judge results have intervals; network results do not | **Add server-clustered intervals** to the network rates |
| End-to-end overhead | Page latency, throughput | Gate check and durable slot only | Optional: per-call latency through the broker versus direct |
| Reproducibility | Artifact badges | Clean-clone reproduction recorded | None |

## Plan

1. Experiment A, real malicious versions on 2-3 registry network servers
   (pre-register first).
2. Experiment B, new local held-out batch from npm search (pre-register the
   rule and the frozen plan first).
3. Experiment C, cross-session template comparison against poisoning,
   including a poisoner that repeats the same noise in every session.
4. Paper: the three missing citations, the incident coverage table, the
   capability table, the worked template example, network intervals, and the new
   results, within the 13-page body.

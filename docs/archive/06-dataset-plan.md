# Dataset Plan

> **The problem:** no dataset exists for this. There is no labeled corpus of MCP tools, no rug-pull benchmark, no ground truth for behavioral mutation. Buying or downloading our way out is not an option.
>
> **The strategy:** we do not need a *pre-existing* dataset. We need three data assets, and we build two of them ourselves in ways that are cheap, defensible, and independently useful. Constructing them *is* part of the contribution.

---

## 0. Why "no dataset" is an advantage here

A reviewer's instinct on a security paper is not "where is your dataset" but "is your evaluation sound and is your threat model real." Two of our three assets are things we *must* build ourselves anyway, because:

- A rug-pull benchmark requires **ground truth about a hidden implementation** — by definition only obtainable from a harness we control.
- An ecosystem measurement requires **the ecosystem as it actually is**, which is public and harvestable, not a curated dataset.

The dataset risk is therefore not "we lack data" but "we lack *labels*." §4 is the labeling protocol that closes that.

---

## 1. The three assets

| | Asset | Type | Source | Cost | Blocks which contribution |
|---|---|---|---|---|---|
| **D1** | MCP-Registry-Corpus | Real tool declarations | Public MCP registries + GitHub | Low (scraping) | C4 (measurement) |
| **D2** | MCP-MutBench | Controlled benchmark | Built by us | Medium (engineering) | C2, C5 (theory + defense) |
| **D3** | AgentDojo | Existing public benchmark | `pip install agentdojo` | None — already working | C1 (argument-integrity arm) |

---

## 2. D1 — MCP-Registry-Corpus (the measurement dataset)

**What it is:** every MCP tool declaration `τ = (name, description, input_schema)` we can harvest from public sources, plus provenance.

**Sources (in priority order):**
1. Official MCP server registry / `modelcontextprotocol/servers` reference servers
2. `awesome-mcp-servers`-style community indexes
3. GitHub code search for `mcp.json`, `Server(` declarations, `@server.list_tools`, `tools/list` schemas
4. Public MCP marketplaces (the three Song et al. used)

**Harvest method:** static extraction only — parse repositories and manifests for declared tools. **We do not connect to, execute, or probe anyone's live server.** This keeps the study purely observational over public artifacts and avoids any live-system interaction.

**Target scale:** 1,500–4,000 tool declarations across 200–600 servers. This is comfortably enough for proportion estimates with tight CIs and is achievable by static scraping.

**Schema** (`data/processed/registry_corpus.jsonl`):
```json
{
  "tool_id": "sha1(server_url + tool_name)",
  "server_id": "...",
  "server_kind": "official | vendor | community",
  "name": "transfer_money",
  "description": "...",
  "input_schema": {...},
  "declared_output": {...} | null,
  "sibling_tools": ["check_balance", "..."],
  "source_url": "...",
  "harvested_at": "2026-..."
}
```

**Ethics / legal:** public repositories and manifests only; respect `robots.txt` and rate limits; no live-server probing; no PII; we publish the *derived classification*, and the harvest script rather than any re-hosted scrape, so the corpus is reproducible without us redistributing others' content.

**The headline number this produces:**
> *X% of N real MCP tools are V0 (opaque) — provably undefendable by any client-side monitor.*

That single sentence is the paper's most quotable result and it does not exist anywhere in the literature.

**Secondary numbers, all free once D1 exists:**
- V-class distribution split by `server_kind` (are community servers more opaque than vendor ones?)
- **Pseudo-V2 rate** — tools whose only corroborating channel is served by the *same* server, i.e. apparent verifiability that collapses under Theorem 1. Potentially the most surprising finding in the paper.
- Correlation between V0 and effect severity (are the dangerous tools the unverifiable ones? if yes, that is the alarming result)

---

## 3. D2 — MCP-MutBench (the controlled benchmark)

**Why we must build it:** ground truth about `e` (what the server *actually did*) is only knowable inside a harness we own. No public artifact can provide this.

**Components:**

**(a) Tool domains — 4, not 1.** The single banking domain in the preliminary work is the biggest external-validity weakness. Chosen to span V-classes deliberately:

| Domain | Tools | Dominant class | Why included |
|---|---|---|---|
| Banking | `check_balance`, `transfer_money`, `list_transactions` | V2 (and pseudo-V2) | continuity with prior work; clear ground truth |
| Email | `send_email`, `list_inbox`, `search_mail` | V2 | real incident precedent (Postmark BCC) |
| Files | `read_file`, `write_file`, `delete_file`, `hash_file` | V1 + V2 | contains genuinely self-verifiable tools |
| Compute | `convert_units`, `parse_document`, `summarize` | V1 | pure functions — where replay should work |

**(b) Mutation engine — 6 strategies, extending the previous 4:**

| # | Mutation | Metadata | Effect | Detectable by hash? |
|---|---|---|---|---|
| M1 | Hidden instruction in description | changed | maybe | yes |
| M2 | Schema field relabel | changed | changed | yes |
| M3 | Full description swap | changed | changed | yes |
| M4 | Behavior-only, **naive response** | unchanged | changed | no |
| M5 | **Behavior-only, adaptive (A\*)** — honest response, malicious effect | unchanged | changed | **no, and invisible to response validation** |
| M6 | **Probe-aware adaptive** — behaves honestly when it suspects a verification probe | unchanged | changed | no; tests V1 replay robustness |

M5 and M6 are new and are what make the evaluation credible. M6 in particular tests whether our own V1 defense survives an adversary that knows about it.

**(c) Defense conditions:** none · hash-pin only · naive response validator · BIM(V-aware) · BIM + hash-pin

**(d) Oracle:** the harness records the true effect `e` out-of-band. ASR is measured against `e`, never against the server's self-report. **This is the methodological point the previous design got wrong** — measuring success from the response means measuring what the attacker chose to tell you.

**Scale:** 4 domains × 6 mutations × 5 defenses × 3 models × 30 trials ≈ **10,800 trials**. Plus benign controls for FPR/TSR. Budget in [`07-experiment-plan.md`](07-experiment-plan.md).

---

## 4. Labeling protocol (this is what makes D1 defensible)

The classifier needs a gold set, and gold sets are where measurement papers die.

1. **Stratified sample** of 300 tools from D1, stratified by `server_kind` and name-verb class.
2. **Two independent annotators** (both authors) label V-class using a written codebook (`docs/codebook-vclass.md`, to be written *before* labeling — not after).
3. **Report Cohen's κ.** Target κ ≥ 0.7. If below, revise the codebook and re-label — and report that we did.
4. **Adjudicate disagreements** jointly; the adjudicated set is the gold standard.
5. **Split:** 150 development (classifier tuning) / 150 held-out test (reported once, at the end).
6. Report classifier precision/recall **per class** on held-out, and propagate classifier error into the headline percentage as a confidence interval. A measurement with an unvalidated instrument is not a measurement.

**Fallback if κ is poor:** that itself is a finding — it means V-class is not reliably determinable from declarations alone, which is *also* a security-relevant result (clients cannot assess verifiability from what MCP shows them). We report it either way. **The study is designed so that both outcomes are publishable.**

---

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Registries too small / hard to scrape | Medium | GitHub code search as primary; 200 servers is enough for proportions |
| κ too low | Medium | Codebook-first; and low κ is itself reportable (§4 fallback) |
| API budget exhausted | Medium | Groq free tier + cheap models; checkpoint/resume already proven in prior notebook; reduce models before reducing trials |
| Adaptive adversary "too easy" — reviewer says obvious | Low | That is the *point*; we quantify how obvious and show the field ignored it |
| Real servers turn out mostly V1/V2 (problem looks small) | Low-Med | Still publishable — inverts to "verifiability is achievable, here is the protocol change to realize it." **Both directions are papers.** |

---

## 6. What exists today vs. what must be built

| | Status |
|---|---|
| D3 AgentDojo pipeline | ✅ **working** — `exp/gap-exp.ipynb`, ASR 34.0% reproduced, checkpoint/resume proven |
| D2 harness | ⚠️ prior banking prototype exists but is **not in this repo**; rebuild properly with out-of-band oracle |
| D2 mutations M1–M4 | ⚠️ prototyped previously; M5, M6 are new |
| D1 corpus | ❌ not started — highest-value next build |
| Gold labels | ❌ not started; codebook first |

**Immediate build order:** D1 harvester → codebook → D2 harness with oracle → M5/M6 → classifier → experiments.

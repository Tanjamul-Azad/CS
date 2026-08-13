# D1 Findings — Ecosystem Measurement

<!-- AUTO:corpus-line -->
**n = 5,397 tools across 295 servers.** A0 56.5% · A1 7.2% · A2 35.9% · A3 0.4%. Regenerated 2026-08-13 by `python experiments/update_docs.py`.
<!-- /AUTO:corpus-line -->

> **Status: harvest complete, validation pending.** These figures come from the full 500-repository harvest. They are **not yet a measurement** — the A0–A3 classifier has not been scored against a human gold standard. Until κ validation runs (see [`17-status.md`](17-status.md)), treat every number here as an *instrument reading*.
>
> Supersedes [`13-d1-preliminary-findings.md`](13-d1-preliminary-findings.md), which covered only the official reference repository and is now best read as the best-case control arm.

Numbers inside `<!-- AUTO -->` blocks regenerate from the corpus. Prose is hand-written.

---

## 1. The headline

<!-- AUTO:headline -->
**56.5% of MCP tools have relation degree 0** (95% CI 55.2–57.8, n=5,397 tools across 295 servers).

No client-side audit detects their compromise at any cost. Not with a bigger budget, not with a smarter checker — Theorem 1 applies and there is no relation to check. For these tools the remedy is policy: restrict the call, or put a human in front of it.

| Class | n | % | 95% CI |
|---|---|---|---|
| **A0** unrelatable | 3,051 | **56.5%** | 55.2–57.8 |
| A1 self-relatable | 388 | 7.2% | 6.5–7.9 |
| A2 read-backable | 1,936 | 35.9% | 34.6–37.2 |
| A3 invariant-bound | 22 | **0.4%** | 0.3–0.6 |
<!-- /AUTO:headline -->

---

## 2. Official reference servers are the best case, not the ecosystem

<!-- AUTO:official-vs-community -->
*(This corpus contains no official reference servers; run `run_harvest.py` for the official control arm.)*
<!-- /AUTO:official-vs-community -->

Measured separately ([`13`](13-d1-preliminary-findings.md), n=43): the official reference servers show **A0 9.3%**, `readOnlyHint` on **74.4%**, `outputSchema` on **30.2%**. Against the ecosystem's 56.5% / 3.1% / 1.2%, that is a different population entirely.

> ### The methodological claim
> **Every prior MCP security paper that evaluates on reference servers is evaluating the most favourable slice of the ecosystem.** The servers researchers test on are not the servers users run.

This is a concrete, quantified instance of a general problem in systems security evaluation, and it is worth stating plainly rather than as a hedge.

---

## 3. MCP's behavioral annotations are effectively unused

<!-- AUTO:schema-coverage -->
| Field | present on |
|---|---|
| `inputSchema` | 59.2% |
| `outputSchema` | **1.2%** |
| `readOnlyHint` | 3.1% |
| `destructiveHint` | 2.6% |
| `idempotentHint` | 2.5% |
| `openWorldHint` | 3.1% |
<!-- /AUTO:schema-coverage -->

[`13`](13-d1-preliminary-findings.md) framed these hints as *"self-declared by the audited party, therefore unverifiable"* — a compromised server sets `readOnlyHint: true` and a trusting client stops looking. That critique is sound and still holds where the hints appear.

**But in the wild they barely appear at all.** ~3%.

The story is therefore not *"the protocol trusts the attacker's self-report"* so much as **"the protocol's one behavioral channel is dead on arrival."** Both are findings; the second is larger, and it inverts rather than refines the first — which is why `13` is marked superseded rather than quietly edited.

**This strengthens our own method.** We were worried the classifier leaned on attacker-controlled metadata. Dual derivation — classifying once trusting the hints, once ignoring them — moves only **2.3 points** (A0 56.5% → 58.8%). Measured auditability barely depends on the attacker's word, because that word is almost never given.

### 3.1 `outputSchema` on 1.2% — and why that is actionable

Without knowing what a read *returns*, a client cannot mechanically check that a write is reflected in it. R1 degrades to matching name and description vocabulary — weaker and noisier. A meaningful share of the 56.5% is likely **caused by this absence** rather than by anything intrinsic to the tools.

That reframes the finding from grim to actionable, and yields the paper's first protocol recommendation: **mandate or strongly encourage `outputSchema`.** It costs server authors almost nothing and would move tools out of A0 wholesale.

---

## 4. Conservation is nearly absent

<!-- AUTO:relations -->
| Relation | n | |
|---|---|---|
| **R1** | 7,535 | write-read consistency |
| **R2** | 32 | conservation |
| **R3** | 495 | determinism |
| **R4** | 23 | null-op |
| **R5** | 1,454 | canary |
<!-- /AUTO:relations -->

**32 conservation relations across 5,397 tools. A3 = 0.4%.**

R2 is the strongest relation class: it constrains a *global* quantity, and faking it requires simulating the honest system's arithmetic — the 17-LOC rung of the adversary ladder. In the wild it is almost unavailable.

[`13`](13-d1-preliminary-findings.md) flagged A3≈0 as possibly an instrument artifact. That explanation is now weak: the inline-schema bug is fixed, field resolution went 23%→72%, and R2 is no longer gated behind R1. Conservation still barely appears. The likeliest reading is **real** — most MCP servers wrap files, search, and APIs, and have no conserved numeric quantity. Banking-style invariants are the exception.

**Consequence for the defense:** the strongest audit class is, in practice, mostly unavailable. MBA in the wild runs largely on R1 and R5.

---

## 5. What predicts auditability

### 5.1 Tool count — hypothesis holds at full n

<!-- AUTO:toolcount -->
| tools/server | servers | tools | A0 rate |
|---|---|---|---|
| 1 | 25 | 25 | 88.0% |
| 2–3 | 31 | 78 | 84.6% |
| 4–7 | 68 | 370 | 72.4% |
| 8–15 | 75 | 847 | 55.6% |
| **16+** | 96 | 4,077 | 54.5% |
<!-- /AUTO:toolcount -->

Monotonic decreasing, as originally predicted: relations are derived between siblings, so more siblings means more opportunities to relate.

> **Correction, recorded deliberately.** At n=1,153 (partial harvest) this curve *reversed* at 16+, rising to 62.9%, and we wrote the hypothesis up as falsified. At full n it does not reverse. **The reversal was small-sample noise, and our "falsification" was premature.**
>
> This is retained rather than deleted because it is the cleanest possible argument for the discipline the rest of this document tries to keep: do not draw conclusions from a partial corpus. We did, on our own data, and were wrong within an hour.

### 5.2 Read coverage — the stronger mechanism

<!-- AUTO:read-coverage -->
| reads / tools | servers | tools | A0 rate |
|---|---|---|---|
| **none** | 77 | 1,076 | **92.8%** |
| <20% | 24 | 773 | 67.7% |
| 20–40% | 58 | 1,974 | 41.0% |
| 40–60% | 52 | 885 | 40.5% |
| >60% | 59 | 664 | 51.2% |

Lowest A0 rate is in the **40–60%** band (40.5%) — the relationship is U-shaped, not monotonic, because a read also needs a write to corroborate it.
<!-- /AUTO:read-coverage -->

Spearman ρ(read fraction, A0 rate) = **−0.300** over 270 servers.

Read coverage separates the ecosystem far more sharply than tool count does — **92.8%** for servers with no reads at all, against 88.0% for single-tool servers — and it is *mechanistic* rather than correlational: every relation needs a read to corroborate a write. A server exposing twenty writes and no reads is unauditable at any size.

The curve is **U-shaped**, bottoming at 40–60%. Read-heavy servers rise again because a read also needs a *write* to corroborate it. What predicts auditability is **balance**.

**Second protocol recommendation: ship a read for every write.** Unlike most security advice this costs the author almost nothing and is checkable at review time.

---

## 6. Declaration idioms

<!-- AUTO:idioms -->
| Idiom | n | % |
|---|---|---|
| `python/fastmcp-decorator` | 2,374 | 44.0% |
| `ts/object-literal` | 1,489 | 27.6% |
| `ts/registerTool` | 647 | 12.0% |
| `ts/server.tool` | 414 | 7.7% |
| `python/types.Tool` | 310 | 5.7% |
| `json/manifest` | 163 | 3.0% |
<!-- /AUTO:idioms -->

Python FastMCP dominates at 44%, and that path is AST-based and reliable — so extractor confidence is higher than a regex-heavy pipeline would suggest. The TypeScript idioms (47.3% combined) are regex-based; recall on those is checked against real code in §7.

---

## 7. Instrument validation

| Check | Result |
|---|---|
| Fixture recall, all idioms | 100% (but fixtures are self-written — weak evidence) |
| **Recall on real code**, 39 files / 171 declarations | **no file extracted fewer than a permissive independent counter** |
| Regression tests for known bugs | 4 bugs pinned, 41 tests passing |
| **Classifier vs human labels** | ❌ **not yet run — the blocker** |

The real-code recall check is a **lower bound** on missed declarations, not a true recall figure: both counters look for registration syntax, so a declaration written in a form neither recognises is invisible to both. What it reliably catches is the failure mode that bit us twice — a declaration plainly present in the source that full extraction drops.

---

## 8. Threats to validity

| # | Threat | Direction |
|---|---|---|
| 1 | **Classifier unvalidated against humans** | unknown — this is why nothing here is claimed as a measurement |
| 2 | Sampling frame is GitHub-only | servers shipped solely via npm/PyPI or privately are invisible; direction unknown |
| 3 | Discovery relies on GitHub search relevance + star stratification | mitigated by stratifying, not eliminated |
| 4 | Repos self-identifying as MCP servers are taken at their word | may include non-servers |
| 5 | Relation derivation is heuristic (verbs, nouns, fields) | precision-biased, so A0 is likely **over**-stated |
| 6 | Extractor recall is a lower bound | missed declarations would **over**-state A0 |

Threats 5 and 6 both push in the same direction: **the true A0 rate is probably somewhat lower than 56.5%.** Stated here rather than buried, because it cuts against our own headline.

---

## 9. Reproduce

```bash
python experiments/run_d1.py --target 500      # ~90 min, checkpoints; --resume to continue
python experiments/run_d1.py --report-only     # analysis over the saved corpus
python experiments/update_docs.py              # regenerate the numbers in this file
python experiments/make_figures.py             # F1–F4
```

`GITHUB_TOKEN` in `.env` is required for a full harvest (5,000 req/hr vs 60). The corpus is gitignored by design — regenerate rather than commit, so data always matches the current extractor.

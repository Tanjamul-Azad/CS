# D1 Preliminary Findings

**Run date:** 2026-08-13 · **Corpus:** 43 tools / 5 servers, `modelcontextprotocol/servers` only
**Command:** `python experiments/run_harvest.py`


> **SUPERSEDED by [`15-d1-findings.md`](15-d1-findings.md).** This document measured only the official reference repository. The full harvest shows the official servers are the *best case* by a wide margin — A0 9.3% here vs 62.0% ecosystem-wide — so treat this as the control arm, not the result. Its framing of MCP annotations as "self-declared therefore unverifiable" is also revised there: in the wild those hints are barely declared at all.
> ⚠️ **This is a pipeline validation, not the paper's result.** n=43 from a single repository is far too small and — critically — the *wrong* sample: these are the official reference servers, the best-engineered examples in the ecosystem. They are the **best case**, not the typical case. Every number here will move, most likely against auditability, once community servers are included. Do not cite these figures.

---

## 1. What now works

| Component | Status |
|---|---|
| GitHub tree listing (1 API call/repo) + raw file fetch (unmetered) | ✅ |
| Python AST extractor — FastMCP decorators, `types.Tool` literals | ✅ 100% on fixtures |
| TypeScript extractor — `registerTool`, object literals, zod resolution | ✅ 100% on fixtures |
| JSON manifest extractor | ✅ |
| Monorepo sub-server resolution (`src/<name>/` → distinct server) | ✅ |
| Relation derivation R1–R5, A0–A3 classification, Wilson CIs | ✅ |

Two extraction bugs were found and fixed by running against real code, both of which would have **silently corrupted the headline number**:

1. **Multi-tool files collapsed to one tool.** `filesystem/index.ts` declares 14 tools; the first extractor returned 1. This does not merely lose tools — it destroys the *sibling read/write tools that relations are derived from*, so it inflates measured A0. Pre-fix the corpus reported **100% A0**; post-fix, 9.3%.
2. **Field bleed across adjacent TS declarations.** A tool's zod-field scan ran into the next tool's schema, merging their fields.

Both are the kind of error that produces a confident, wrong, publishable-looking number. They are the argument for measuring extractor recall rather than assuming it.

## 2. Finding: MCP behavioral annotations are self-declared by the audited party

The most interesting result of this run, and it is a **protocol-level** finding rather than a measurement one.

| Annotation | Declared on |
|---|---|
| `readOnlyHint` | 74.4% |
| `openWorldHint` | 74.4% |
| `destructiveHint` | 51.2% |
| `idempotentHint` | 51.2% |

MCP defines behavioral hints that describe exactly the properties this project cares about — whether a tool mutates state, whether it is destructive, whether it is idempotent. **They are asserted by the server itself.**

A compromised server sets `readOnlyHint: true`, and any client that trusts the hint stops auditing that tool. The protocol asks the party under suspicion to certify its own innocence, and the field is *unverifiable by construction* — it is metadata, so hash pinning confirms only that the lie has not changed since approval.

This is a clean, concrete instance of the paper's whole thesis, stated in the protocol's own vocabulary. It deserves its own subsection and probably a figure.

**Consequence for our method:** our classifier *uses* these hints, because they improve derivation on honest servers. That is a dependency we must state, and we report coverage so a reader can see how much of the classification leans on unverifiable self-report. A defensible design is to derive relations **twice** — once trusting hints, once ignoring them — and report both. Divergence between the two is a direct measure of how much of the ecosystem's apparent auditability rests on the attacker's word.

## 3. Finding: output schemas exist, but on a minority

`outputSchema` present on **30.2%** of tools (13/43).

Better than the earlier assumption that MCP output schemas are essentially absent, but it still caps relation derivation for the other ~70%: without knowing what a read returns, a client cannot mechanically check that a write is reflected in it. And again — official servers are best case.

## 4. Preliminary class distribution (do not cite)

| Class | n | % | 95% CI |
|---|---|---|---|
| A0 unrelatable | 4 | 9.3% | 3.7–21.6 |
| A1 self-relatable | 3 | 7.0% | 2.4–18.6 |
| A2 read-backable | 36 | 83.7% | 70.0–91.9 |
| A3 invariant-bound | 0 | 0.0% | 0.0–8.2 |

Relations derived: **R1** 70, **R3** 13, **R5** 7, **R2** 0, **R4** 0.

### Reading

**A3 = 0 is the notable one.** No conservation invariants were derivable anywhere in the corpus. R2 is the strongest relation class — it constrains a *global* quantity and is the hardest for an attacker to fake consistently — and on this sample it never fires. Two candidate explanations, and we must distinguish them before making any claim:

1. *Instrument limitation.* Input fields resolved only partially (many zod schemas live in sibling files the single-file extractor does not see), so R2's numeric-field test cannot fire. **Most likely.**
2. *Real property.* Filesystem/memory/fetch servers genuinely have no conserved numeric quantity, unlike banking or billing. Plausible for this sample specifically.

**Action:** resolve cross-file schema imports before drawing any conclusion. If A3 remains near zero on a broad corpus, that is a significant result — the strongest audit class would be largely unavailable in practice — but it cannot be claimed while a known extractor limitation could produce the same reading.

**A0 = 9.3%** is far lower than expected and almost certainly optimistic. `everything` is a demo server dense with sibling tools; `filesystem` is unusually well-structured. Single-tool servers (`fetch`, `sequentialthinking`) are A0 by necessity — a server with one tool has no sibling to relate to. **Hypothesis worth testing: A0 rate is driven primarily by server tool-count**, which would mean the long tail of small community servers is where the undefendable mass sits.

## 5. Known limitations of the current instrument

| # | Limitation | Effect on the number | Priority |
|---|---|---|---|
| 1 | Corpus = 1 repo, official servers only | **Fatal for external validity** | ★★★ |
| 2 | Cross-file zod schema imports unresolved | Suppresses R2/R5 → understates A3 | ★★★ |
| 3 | Extractor recall measured on hand-written fixtures, not real code | Unknown true recall | ★★☆ |
| 4 | No gold-standard human labels yet; κ not computed | Classifier unvalidated | ★★★ |
| 5 | Relations derived within-server only | Correct by design (see pseudo-V2), but should be stated | ★☆☆ |
| 6 | No `GITHUB_TOKEN` → 60 req/hr | Caps corpus size | ★★☆ |

## 6. Next steps, in order

1. **Add `GITHUB_TOKEN`** — unblocks 5,000 req/hr and a real corpus
2. **Harvest breadth** — target ≥400 servers spanning official / vendor / community, since the official/community split is now a live hypothesis (§4)
3. **Resolve cross-file schema imports** — pool a server's sources before extraction; required before any A3 claim
4. **Measure extractor recall on real code** — hand-label 30 real server files, compute recall per idiom
5. **Write the codebook, then double-annotate 300 tools, report κ** (`docs/06-dataset-plan.md` §4)
6. **Dual derivation** — with and without trusting self-declared annotations; report the divergence (§2)
7. Test the tool-count hypothesis: regress A0 on server tool-count

## 7. Reproduce

```bash
python experiments/run_harvest.py
```
Writes `data/processed/registry_corpus.jsonl` (gitignored — regenerate rather than commit, so the corpus always matches the current extractor).

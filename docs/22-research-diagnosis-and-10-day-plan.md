# Research Diagnosis and 10-Day Plan — What We Should Actually Do Next

Written 2026-09-08, after three further rounds of instrument repair and re-measurement on real servers (see §1). This supersedes the direction taken in [`21-real-server-results-and-options.md`](21-real-server-results-and-options.md) §5 ("Direction A: fix relation derivation"), which has now been attempted and measured. Read [`21`](21-real-server-results-and-options.md) first for the data, then this for what to do about it.

**Verdict up front:** stop trying to make detection the headline claim. The evidence increasingly says the ceiling is the ecosystem, not our code — but we cannot claim that yet, because we have no positive control on servers we did not write. The single highest-value experiment in the next ten days is the one that separates those two explanations. That experiment also contains the working end-to-end demonstration we want, scoped honestly to where it works.

---

## 1. What we actually have

Verified against the repository, not from memory. Anything marked **NOT RUN** is a gap a reviewer will find.

| Asset | Scale | Result | Status |
|---|---|---|---|
| **D1 static corpus** — auditability classification | 18,566 tools / 2,846 repos | A0 69.7% [CI 69.1–70.4], A1 7.8%, A2 22.2%, A3 0.3% | collected |
| **Classifier validation** — human κ agreement | 265 rows × 2 annotators | Label columns are **empty in both** annotator sheets | **NOT RUN** |
| **Live scale run** — official MCP Registry | 8,692 candidates → 1,242 usable | True detection 0/128 (L1), 0/127 (L2), 0/127 (L3). FPR 16/1209 = 1.3% | collected |
| **Instrument repair** — keyed pairing + attack vocabulary + structured comparison | 218 servers × 3 rounds | Attack landing 58.5% → 94.9%; FPR held 1.8%; **detection 0/205** | collected |
| **Controlled benchmark** — self-written domains | 4 domains, 20 trials/cell | MBA detection 1.0 at L1/L2, 0.0 at L3; all three baselines 0.0 everywhere | collected |
| **LLM agent evaluation** | 320 episodes, ≈32 effective | One model, 2-step tasks, zero within-cell variance | collected |
| **Incident corpus** — grounding the threat model | n = 1 | Postmark BCC, cited from memory, not verified to primary source | **NOT RUN** |
| **External defense baselines** | 7 cited, 0 run | Comparisons are against three baselines we wrote ourselves | **NOT RUN** |

### The live-audit funnel

| Stage | Count | % of candidates |
|---|---|---|
| Registry candidates, runnable without credentials | 8,692 | 100% |
| Actually launched in the sandbox | 4,121 | 47.4% |
| Usable write tool, both trials completed | 1,242 | 14.3% |
| Attack actually landed (L1, pre-repair) | 128 | 1.5% |
| **Detected (true, honest-trial cross-checked)** | **0** | **0%** |

### What the three repair rounds this session changed

Raw data: `data/processed/pilot_direction_a.json`, candidate set `data/processed/pilot_direction_a_candidates.json` (218 servers = all 128 previously-landed + a random 90 of the 1,114 that did not land). Code: `src/measure/classify.py`, `src/mcpaudit/auditor.py`, `src/mcpmut/proxy.py`. Tests: 111 passing.

| Metric | Before | After round 1 | After round 2 | After round 3 |
|---|---|---|---|---|
| Attack lands | 58.5% | 94.9% | 94.9% | 94.5% |
| FPR (honest server flagged) | 1.8% | 6.5% | 1.8% | 1.8% |
| **True detection** | **0%** | **0%** | **0%** | **0%** |

Round 1 added identifier-keyed relation pairing and fixed the tampering proxy's field matching (it was matching field names by *exact equality*, so `wallet_address` never matched `address`, and could pick numeric fields that cannot actually be diverted). Round 2 fixed the false-positive regression round 1 introduced (identifiers invented by `synth_args` were being trusted as real resource references). Round 3 replaced the blob-wide substring read-back check with structured key-by-key comparison.

**New negative result worth stating precisely:** in all 10 remaining "reader called correctly, attack landed, no violation raised" cases, the field the attacker diverted is *the same field used to scope the read-back call* (`save_url`'s `url` is diverted, and `get_archived_url` also takes a `url` parameter, filled from the write's own — unmodified — arguments). The audit then queries the original, untouched resource using the original identifier, and no comparison logic can recover the difference: the evidence was never collected. This is a structural limit of call-once-read-back-once auditing, not a bug.

---

## 2. Diagnosis

### FATAL — the claimed core contribution is currently unsupported

[`12-intellectual-lineage.md`](12-intellectual-lineage.md) states the contribution precisely and well: porting metamorphic testing from a cooperative, hand-written-relation setting to an adversarial, declaration-derived one. That is a good claim to stake. The problem is that our own evaluation says the port does not fire — 0% on real servers, four times now, at four instrument quality levels. We cannot headline a method whose central empirical result is that it does not work.

### FATAL — 0% is uninterpretable without a positive control

Two hypotheses explain the result equally well:

- **H1** — real MCP servers lack verifiable structure. An ecosystem property. Interesting, publishable.
- **H2** — our detector is bad. An instrument property. Not publishable.

Our only positive control is the controlled benchmark, and those four servers are ones we wrote, so it cannot discriminate. This is objection R4 in [`19-reviewer-review.md`](19-reviewer-review.md), now with data behind it. Fixing this is the whole game for the next ten days.

### FATAL — the headline 69.7% rests on an unvalidated heuristic

The A0–A3 classifier is verb lists and noun overlap, never scored against human judgment. The sheets exist (`data/processed/labels_annotator_A.tsv`, `_B.tsv`) and every `label` / `check` / `hint_conflict` cell is blank. Worse, [`19`](19-reviewer-review.md) records that write verbs were added *after* looking at corpus data — fitting the instrument to the sample. Until κ is computed on a held-out split, every number in the measurement half is contestable. This is cheap to fix and there is no excuse for it still being open.

### MAJOR — the controlled benchmark is not evidence, and presenting it as such hurts us

Four self-written domains, three self-written baselines that score 0% by construction because no adversary in the ladder touches the declaration. A table where we score 100% and everything else scores 0% reads as rigged even when it is honest. Keep it, relabel it: it is an **illustration of the cost ladder**, not an evaluation of the defense.

### MAJOR — "Theorem 2" is not a theorem

Three hand-written adversaries at 3, 9 and 17 LOC, in one domain family, counted by their author. Our own review grades this **D**. Downgrade it to an Observation or a Cost Model and let the empirical curve carry the weight. Reviewers respect the downgrade; they punish the mislabel.

### STRENGTH — protect these

- **The measurement infrastructure.** Full official-registry walk, Docker-sandboxed execution of untrusted third-party code, atomic checkpointing, resumable runs, 111 passing tests, and a documented history of finding and fixing our own instrument bugs at scale. This is the most defensible asset we have and the reason the measurement direction is viable.
- **The intellectual positioning.** [`12`](12-intellectual-lineage.md) names, for each borrowed field, the exact assumption that breaks in our setting — metamorphic testing's cooperative system under test, runtime verification's trusted trace, N-version's independence. This inoculates us against "this is just metamorphic testing," which is otherwise the obvious dismissal.

---

## 3. Three directions, compared

Judged only on what can be *evidenced* in ten days with the infrastructure we already have.

| | **A · Verifiability floor** | **B · Snapshot-diff defense** | **C · Protocol proposal** |
|---|---|---|---|
| **Research question** | Can a client verify what an MCP server actually did — and if not, is that the client's fault or the protocol's? | Does before/after state diffing detect effect diversion where read-back alone fails? | What minimal protocol change would make the ecosystem auditable? |
| **Headline claim** | The ecosystem has a measurable verifiability floor, and it is low | Our defense detects at rate X on real servers | Mandating output schemas converts X% of A0 to A2 |
| **Novelty** | Taxonomy + first ecosystem-scale verifiability measurement + impossibility framing | Incremental over existing MBA; the mechanism is standard | Constructive, but proposals without adoption evidence are cheap |
| **Evidence already held** | Most of it | Almost none — four rounds returned 0% | All of it (18,566 declarations, re-analysable) |
| **Risk it fails** | Low | **High** | Low |
| **Risk a reviewer dismisses it** | Medium — needs the positive control | High — n will be tiny even if it works | High on its own — reads as speculation |
| **Real-world value** | High — tells deployers what they can and cannot check today | High if true | High — actionable for the spec authors |
| **Commercial path** | Auditability scoring / registry gating | A client-side audit product | None directly |
| **Provable in 10 days** | **Yes** | Unlikely | Yes |

---

## 4. Decision

**Direction A, absorbing B as its positive control and C as its constructive close.**

We are not abandoning the defense. We are demoting it from *headline claim* to *instrument*. Its job in this paper is to establish that when verifiable structure exists, it can be exploited — which is exactly what makes 0% on everything else a statement about the ecosystem rather than about our code.

This preserves what we wanted from Direction A in [`21`](21-real-server-results-and-options.md): we still build something and demonstrate it working end to end. The difference is that its success is reported on the subpopulation where success is possible, and **the size of that subpopulation becomes the paper's finding**.

**Why not keep pushing B as the headline.** Four independent instrument improvements produced: landing rate fixed (58.5% → 94.9%), false positives held flat, detection unchanged at zero. The 218-server pilot contained only ~13 servers with a genuinely strong write→read pairing to begin with. Even a fifth fix that works lands a headline number with n in the low tens, on a subpopulation selected post hoc. That is not a defensible defense paper.

**Why this is still a positive result.** "We measured a deployed ecosystem, found 69.7% of tools admit no client-side check, ran a real adversary against 1,242 live third-party servers, showed that even a correct detector catches nothing because the structure it needs is not there — and here is the protocol change that fixes it, quantified over 18,566 real declarations." That is a complete, useful argument in which nothing is fabricated.

---

## 5. The research, stated properly

**Problem.** An MCP client authorises a third-party server to *act* — send the mail, move the file, charge the card. The client sees only the server's own report of what happened. Nothing in the protocol lets it check whether the reported effect is the real one.

**Gap.** Existing agent-security work (Progent, ETDI, MCP-Guard, Task Shield, IPIGuard, AgentDojo) governs what the agent is *allowed to ask for* — input and policy integrity. None verifies what the server actually *did*. Metamorphic testing solves oracle-free verification but assumes a cooperative system under test and hand-written relations.

**Research question.** For real, deployed MCP servers, what fraction of authorised tool calls admit *any* client-side behavioural check derivable from the protocol's own declarations — and where such a check exists, does it survive an adversary that forges responses?

**Hypotheses.**

- **H1** — the verifiable fraction is small and concentrated in resource-CRUD-shaped servers.
- **H2** — where a genuine keyed relation exists, an audit detects L1 diversion at a high rate.
- **H3** — mandating output schemas moves a large share of A0 into checkable classes.

All three are falsifiable by the experiments in §6.

**Contribution, in presentation order.**

1. An auditability taxonomy (A0–A3) that says, from declarations alone, whether a tool call can be checked at all.
2. The first ecosystem-scale measurement of that property — 18,566 tools statically, 1,242 servers executed live under a real adversary.
3. An impossibility result (Theorem 1) plus an empirically located second ceiling: read-back auditing is blind exactly when the diverted field is the field that scopes the read.
4. A quantified protocol counterfactual showing what a minimal spec change would buy.

---

## 6. Experiment matrix

Ten days buys the five MUST rows and most of the SHOULD rows. **Cut from the bottom, never the top.**

| ID | Experiment | Question it answers | Data | Baseline / control | Metrics | Priority |
|---|---|---|---|---|---|---|
| **E1** | Human validation of the A0–A3 classifier | Is 69.7% real or an artifact of our heuristic? | 265 sampled tools, 2 independent annotators, held-out split | Human judgment as ground truth | Cohen's κ, per-class precision/recall, tuned-vs-held-out delta | **MUST** |
| **E2** | Hand-audited verifiability ground truth | Do real servers actually expose a genuine write→read pair? | 40 live servers sampled from the 1,242 | Two annotators against the codebook | % with a genuine pair, κ, disagreement analysis | **MUST** |
| **E3** | **Positive control:** audit restricted to E2's verified-verifiable subset | Does the detector fire when the structure it needs is present? | The verified subset, honest + L1 trials | Same detector on the verified-*not*-verifiable subset | Detection rate, FPR, per-server outcome table | **MUST** |
| **E4** | Full re-run at best instrument quality | What is the ecosystem-wide detection rate with all known instrument bugs fixed? | All 1,242 launchable servers | Pre-repair run as within-subject comparison | Detection, FPR, attack-landing rate, A-class coverage | **MUST** |
| **E5** | Protocol counterfactual | What would mandatory output schemas / a declared verifier buy? | 18,566-tool corpus, re-analysed | Current spec as the null condition | Δ A0 share under each intervention, with CIs | **MUST** |
| **E6** | Relation-tier ablation | Which pairing tier does the work — noun, field, keyed, or snapshot? | Verified subset from E2 | Full method minus one tier at a time | Detection and FPR per configuration | SHOULD |
| **E7** | Orthogonality demonstration | Do existing agent defenses address effect integrity at all? | One external defense, **run** — not just cited | The external tool against our L1 adversary | Detection rate (expected 0) with a mechanism-level explanation | SHOULD |
| **E8** | Robustness across the ladder | Does conservation rescue what read-back misses? | Verified subset at L2 and L3 | L1 result on the same servers | Detection by level; A3 availability | SHOULD |
| **E9** | Audit cost | What does auditing cost in calls, latency and tokens? | Instrumented run over the 1,242 | Unaudited call path | Extra reads/call, added latency, overhead % | SHOULD |
| **E10** | Incident corpus | Are real compromises actually cheap-adversary shaped? | 10–15 documented supply-chain incidents, primary sources | — | Distribution over shadow-state requirement | NICE |

### E3 is the experiment this whole plan exists to run

It is the only one that discriminates H1 from H2.

- If detection on the verified-verifiable subset is **high** and near-zero elsewhere → the ecosystem claim is proven, and a working system is demonstrated, in the same figure.
- If it is **near-zero on both** → our instrument is the limit. Report that honestly; it is still a result, and it redirects the field away from client-side auditing toward protocol change.

**Design it so that either outcome is publishable, and the ten days cannot be wasted.**

---

## 7. Dataset, baselines, metrics — critical assessment

### Dataset: adequate, with one hole

The sampling frame is genuinely good — the complete official registry, not a keyword search ([`21`](21-real-server-results-and-options.md) §2). Scale is real. The hole is that **no subset has ground-truth verifiability labels**, which is precisely why E2 exists. Do not build a new dataset for its own sake; build the 40-server labelled subset because E3 cannot run without it.

Report the funnel as a selection effect, not a footnote: 14.3% of candidates yield a usable trial, and that subpopulation may be systematically simpler than the servers that failed to launch. A reviewer will ask; answer before they do.

### Baselines: currently too weak to claim anything

Three self-written baselines that score 0% by construction are not a comparison. In ten days we will not reproduce seven systems, and pretending otherwise wastes the week. Do one thing instead: **run a single external defense and show it scores 0% because it solves input integrity, not effect integrity.** One honestly-explained failure is worth more than six citations, and it converts our gap claim from assertion to demonstration.

### Metrics, and why each matters here

| Metric | Why it matters for *this* question |
|---|---|
| **FPR on honest servers** | The deployability gate. A client-side auditor above ~5% is unshippable regardless of detection rate. |
| **Detection rate conditioned on attack-landed** | Unconditioned rates silently mix in trials where no attack occurred. Our 90%-non-landing bug was exactly this failure. |
| **Attack-landing rate** | An instrument-health metric. It bounds every detection number above; report it alongside. |
| **A-class distribution** | The primary measurement outcome, not a diagnostic. |
| **Cohen's κ** | Without it the classification is unfalsifiable. |
| **Extra reads per audited call** | The cost side of the deployability argument. |

**Do not report accuracy.** The classes are wildly imbalanced and the error costs are asymmetric.

---

## 8. Ten-day execution plan

Three parallel streams: **INST** (instrument and runs) · **LABEL** (human ground truth) · **ANALYSIS** (corpus re-analysis and writing). The critical path is **E2 → E3**.

### Day 1 — Freeze scope; start the two things that block everything else

- **LABEL** — both annotators start E1: 265 rows, independently, against [`14-labeling-codebook.md`](14-labeling-codebook.md). No discussion until both are done.
- **INST** — implement before/after snapshot diffing in the auditor: read the corroborating tool once *before* the write, once after, compare states. This is the fix for the §1 ceiling.
- **ANALYSIS** — write the E2 codebook (what counts as a genuine write→read pair) and freeze the 40-server sample, stratified by tool count.

*Gate:* snapshot design decided, E2 sample frozen. Do not let the sample drift later.

### Day 2 — Finish the instrument; finish E1

- **INST** — snapshot diffing under test, regression suite green, Docker image rebuilt.
- **LABEL** — E1 labelling complete → compute κ, per-class precision/recall, tuned-vs-held-out delta.
- **ANALYSIS** — build the E5 counterfactual script over the 18,566-tool corpus.

*Gate:* κ computed. **If κ < 0.6, stop** and fix the codebook before anything downstream uses the classifier.

### Day 3 — Ground truth (the bottleneck — protect it)

- **LABEL** — E2: both annotators hand-audit all 40 servers' live tool lists. Which have a genuine keyed write→read pair? Adjudicate disagreements, record κ.
- **INST** — kick off the E4 full re-run over all 1,242 servers in the background.
- **ANALYSIS** — E5 first pass: Δ A0 under each protocol intervention.

*Gate:* the verified-verifiable subset exists and is labelled. E3 cannot start without it.

### Day 4 — Run the experiment the plan exists for

- **INST** — E3: audit run over the verified subset *and* the verified-not-verifiable subset, honest + L1, snapshot diffing on.
- **INST** — E4 completes; extract detection, FPR, landing rate, class coverage.
- **ANALYSIS** — draft the results skeleton with tables empty and captions already written.

*Gate:* **E3 has a number.** Whatever it is, the paper's shape is now decided.

### Day 5 — Interpret honestly, then branch

- **ANALYSIS** — if detection on the verified subset is high → the ecosystem claim is proven; write it as the central figure. If low → the instrument is the limit; pivot the narrative to protocol necessity and say so plainly. **Write both abstracts, pick one.**
- **INST** — E6 ablation across relation tiers on the verified subset.
- **LABEL** — begin E10 incident corpus: 10–15 documented cases, primary sources only.

*Gate:* the narrative branch is chosen and written down. No more re-litigating it.

### Day 6 — Robustness and the external baseline

- **INST** — E8 (L2/L3 on the verified subset), E9 (audit cost instrumentation).
- **ANALYSIS** — E7: install and run one external defense against our L1 adversary; record the mechanism-level reason it does not fire.

*Gate:* every MUST row has raw output on disk.

### Day 7 — Freeze results; build every figure

- **ANALYSIS** — figures: the funnel, the A-class distribution with CIs, detection split by verified-verifiability, the counterfactual bars, the ablation.
- **INST** — regenerate every figure from raw JSON through a script. No hand-made numbers anywhere.

*Gate:* no experiment started after today unless a MUST row failed.

### Day 8 — Notebooks (the professor's actual deliverable)

Six notebooks, each opening with *what it proves* and closing with *the artifact it writes*:

| Notebook | Purpose | Input | Output artifact |
|---|---|---|---|
| `01_corpus_analysis.ipynb` | The A0–A3 distribution and what drives it | `d1_corpus.jsonl` | class table + figure |
| `02_classifier_validation.ipynb` | E1 — is the classifier trustworthy? | annotator TSVs | κ, confusion matrix |
| `03_live_audit.ipynb` | E4 — ecosystem-wide detection and FPR | `scale_run*.json` | funnel + headline table |
| `04_positive_control.ipynb` | E3 — the discriminating experiment | verified subset results | detection split figure |
| `05_ablation.ipynb` | E6 — which relation tier does the work | ablation runs | per-tier table |
| `06_counterfactual.ipynb` | E5 — what a protocol change buys | `d1_corpus.jsonl` | Δ A0 figure |

- **INST** — verify each notebook runs top to bottom from committed raw data.

*Gate:* someone who did not write a notebook can run it and get the paper's number.

### Day 9 — Write the update, claim by claim

- **ANALYSIS** — fill the claim–evidence matrix (§10). Any claim without an experiment ID gets cut or downgraded to a hypothesis — including "Theorem 2".
- **ALL** — read it as the hostile reviewer in [`19`](19-reviewer-review.md). Fix what we can; list what we cannot as limitations.

*Gate:* every number in the write-up traces to a file path.

### Day 10 — Reproducibility audit and delivery

- **ALL** — clean clone → install → run → confirm the headline numbers reproduce. Fix the README so the chain *code → raw → processed → figure → claim* is walkable.
- **ALL** — presentation: problem → motivation → gap → research question → hypothesis → method → what we built → what we ran → what we found → what it means → what it does *not* prove → what is next.

---

## 9. Risks

**Biggest bottleneck — E2 hand-labelling.** Human time, cannot be parallelised past two annotators without hurting κ, and everything downstream waits on it. Start Day 1, cap at 40 servers, do not let anyone expand the sample mid-week.

**Highest-probability failure — E3 returns near-zero on the verified subset too.** Probability: real. Mitigation is framing, not engineering: that outcome says client-side auditing cannot work on today's protocol *even where structure appears to exist*, which makes E5's protocol argument the paper's conclusion rather than its epilogue.

**Silent killer — instrument bugs masquerading as findings.** We have been burned twice already: a 90% non-landing rate and a 47.5% false-positive rate, both instrument, both initially read as results. Every headline number needs the honest-trial cross-check before anyone writes it down.

**Schedule risk — Docker on this host.** Do not run `docker ps` or other Docker CLI calls concurrently with an active `run_scale.py` on this Windows/git-bash setup; it triggers cygwin fork-resource exhaustion that corrupted ~64/218 launches as spurious `host_error` in a pilot attempt. Budget ~2 hours for a full 1,242-server run at 5 workers.

### Minimum viable research result

If everything else fails, this alone is a defensible submission:

> **E1** (κ-validated classifier) + **E4** (0% detection over 1,242 real servers with instrument quality controlled) + **E5** (quantified protocol counterfactual).

Three experiments, all using data we already hold, **none dependent on the defense working**.

---

## 10. Claim–evidence matrix

Fill the two right-hand columns as results land. A claim that reaches Day 9 without an experiment ID does not go in the update.

| Claim | Evidence required | Exp. | Actual result | Supported? |
|---|---|---|---|---|
| Most MCP tools admit no client-derivable check | Class distribution + human agreement | E1 | 69.7% A0 measured; κ pending | partial |
| The classifier reflects human judgment | κ on a held-out split | E1 | — | **NOT RUN** |
| Detection fails on real servers | Live audit at scale, honest-trial cross-checked | E4 | 0/128, 0/127, 0/127; FPR 1.3% | yes |
| …because of the ecosystem, not our detector | Positive control on verified-verifiable servers | E2, E3 | — | **NOT RUN** |
| Read-back auditing has a second structural ceiling | Per-server trace showing diverted field = scoping field | E3 | 10/10 misses in the pilot fit this pattern | partial |
| Existing agent defenses do not address effect integrity | One external system **run**, not cited | E7 | — | **NOT RUN** |
| A minimal protocol change would materially help | Counterfactual over the real corpus | E5 | — | **NOT RUN** |
| Evading audit costs the adversary shadow state | A stated bound, or an honest downgrade | — | 3 hand-written adversaries, one domain | **downgrade to Observation** |

---

## 11. Publication and product, read coldly

**Venue read.** As a defense paper: not competitive. As a measurement-and-impossibility paper: credible at a security venue's measurement track, and a strong fit for a workshop this cycle with a full-conference version after. The infrastructure and the registry-scale sampling frame are what carry it.

- **Strongest contribution:** the ecosystem measurement.
- **Weakest claim:** anything phrased as "undetectable at any budget" — it is instrument-relative and must be worded that way throughout (objection R4 in [`19`](19-reviewer-review.md)).
- **Biggest remaining objection:** the missing positive control — which is exactly what E3 buys.
- **Missing experiment that would most improve acceptance odds:** E3, then E7.

**Commercial read, honest version.** A detector nobody can make fire is not a product. An **auditability score** is: a registry-side or client-side rating of how much of a server's surface can be independently checked, plus the policy gate for the rest. That is deployable today, it is what the A0–A3 taxonomy already computes, and the buyer is whoever is about to let an agent spend money through a third-party tool server. Do not overclaim beyond this.

---

## 12. What to do today

1. **Both annotators start the κ labelling** (E1). 265 rows, independent, no discussion. It blocks everything downstream and it is the cheapest fatal-objection kill available.
2. **Freeze the 40-server E2 sample** and write the "what counts as a genuine write→read pair" codebook *before* anyone looks at a server.
3. **Implement before/after snapshot diffing** in `src/mcpaudit/auditor.py` — read the corroborating tool once before the write, not only after.

Two edits to make while the above runs, both pure wins:

- Relabel the controlled benchmark as a **cost-ladder illustration**, not an evaluation, everywhere it appears.
- Downgrade **"Theorem 2"** to an Observation / Cost Model in [`00-RESEARCH-PLAN.md`](00-RESEARCH-PLAN.md) and everywhere it is cited.

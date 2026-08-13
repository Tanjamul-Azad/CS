# Project Status

**Living document.** Numbers regenerate from the corpus via `python experiments/update_docs.py`; assessments are hand-maintained.

---

## One-line summary

Theory is settled, the measurement instrument is built and validated against real code, the deployable defense works end-to-end — and the headline number is **not yet a measurement** because the classifier has not been scored against human labels.

---

## Component status

| Component | State | Evidence |
|---|---|---|
| **Theorem 1** — passive clients cannot detect | ✅ proved + demonstrated | `demo_theorem1.py`: DBR 100% → 0% |
| **Theorem 2** — cost of consistency | ◐ stated, not yet a closed-form bound | ladder measured: 3 / 9 / 17 LOC |
| **MBA defense** | ✅ working | `demo_mba.py`, `demo_mcpaudit.py` |
| **`mcpaudit`** — deployable auditor + CLI | ✅ working | catches M5 (R1) and M7 (R2); M8 evades as predicted |
| **D1 extractor** | ✅ validated on real code | 171 real declarations, no misses |
| **D1 harvest** | ✅ complete | see §Numbers |
| **A0–A3 classifier** | ⚠️ **unvalidated** | no human gold standard yet |
| **Labeling harness** (codebook, sampler, κ) | ✅ built, ⏳ unrun | needs two human annotators |
| **Figures** | ✅ F1–F4 | `figures/` |
| **Test suite** | ✅ 41 passing | `pytest tests/ -q` |
| **references.bib** | ⚠️ 45 entries, all `[U]` unverified | must check venue pages |
| **Paper draft** | ❌ not started | — |

---

## The one hard blocker

**κ validation.** Until two people independently label ~300 tools against [`14-labeling-codebook.md`](14-labeling-codebook.md) and the classifier is scored against that gold standard, the headline A0 figure is an *instrument reading*, not a measurement. A reviewer will ask, and "we ran our own heuristic and believed it" is not an answer.

Everything needed is built:

```bash
python experiments/make_label_sample.py --n 300     # writes data/processed/label_sheet.tsv
# two annotators fill label / check / hint_conflict INDEPENDENTLY, no discussion
python experiments/score_labels.py --a a.tsv --b b.tsv
```

Outputs Cohen's κ, per-class precision/recall, confusion matrix, and **A0 bias** — the signed gap between classifier and humans, which applies directly to the headline and gets reported beside it rather than silently corrected.

Target κ ≥ 0.70. Below 0.60 means the codebook is underspecified — revise and re-label rather than arguing individual cases.

---

## Known limitations, ranked by how much they threaten the result

| # | Limitation | Threat | Status |
|---|---|---|---|
| 1 | Classifier unvalidated against humans | **Headline is not yet a measurement** | ❌ blocker |
| 2 | Sampling frame is GitHub-only | npm/PyPI-only and private servers invisible; unknown direction of bias | ⚠️ must be stated as a threat to validity |
| 3 | Extractor recall is a *lower bound*, not a true figure | Both counters look for registration syntax; a declaration in a form neither recognises is invisible to both | ⚠️ stated in tooling output |
| 4 | Theorem 2 is not a closed-form bound | Weakens a theory claim to an empirical one | ◐ ladder is measured; bound is not |
| 5 | Relation derivation is heuristic (verbs, nouns, fields) | Precision/recall unquantified per relation class | ⚠️ folded into #1 |
| 6 | Only one tool domain implemented (banking) | Cost curve may not generalise | ❌ email/files/compute pending |
| 7 | No LLM-in-the-loop experiments yet | No end-to-end ASR under MBA | ❌ pending |
| 8 | T3 probe-aware adversary not built | Our own defense not stress-tested | ❌ pending |

**On #8:** this is the honest stress test — can an adversary distinguish audit calls from task calls and behave differently? A negative result there is publishable and must be reported either way.

---

## What is done that was not obvious

Recorded because these are easy to lose track of and each cost real effort.

- **Two designs killed and replaced** — see [`16-design-history.md`](16-design-history.md). The zero-cooperation constraint came from a supervisor objection that would otherwise have been a reviewer's.
- **One hypothesis falsified (resource cohesion), and one falsified then RE-confirmed at full n (tool-count)** — the premature falsification is kept in [`16`](16-design-history.md) as a worked example of why partial corpora are not evidence.
- **Four instrument bugs found by running against real code**, each of which produced a confident wrong number rather than an error. All now pinned by regression tests.
- **The safety property that makes the auditor deployable**: it never issues a write the agent did not request, because a probe write is a real write. Pinned by `test_auditor_never_issues_unrequested_writes`.
- **Two concrete protocol recommendations** fell out of the measurement — mandate `outputSchema`, ship a read for every write. Rare for a measurement paper to hand the ecosystem a fix this specific.

---

## Next steps, in dependency order

1. **κ validation** — unblocks every claim about the headline *(needs 2 humans)*
2. **Threat-to-validity section** on the GitHub-only sampling frame
3. **Remaining tool domains** — email, files, compute — so the cost curve is not banking-only
4. **T3 probe-aware adversary** — stress-test our own defense
5. **LLM-in-the-loop runner** — port the checkpoint/resume pattern from `exp/gap-exp.ipynb`
6. **Tighten Theorem 2** toward a closed-form bound
7. **Verify all 45 references** against venue pages
8. **Paper draft**

---

## Housekeeping

- ⚠️ **`exp/gap-exp.ipynb` contains hardcoded live Groq API keys** (cells 17, 19). Confirm they were revoked before that notebook is shared or committed anywhere.
- That notebook's cell 16 reports ASR 30.1% / N=73, contradicting the shipped `results_summary_final.csv` (34.0% / N=144). The cell is stale hand-typed data — always regenerate numbers from results JSON.
- `.env` holds `GITHUB_TOKEN` and is gitignored. Corpus and run artifacts under `data/processed/` are gitignored by design: regenerate rather than commit, so data always matches the current extractor.

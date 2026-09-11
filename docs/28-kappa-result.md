# M0c result — κ = 0.559, below the pre-registered 0.60 gate

Written 2026-09-11. Milestone M0c in [`25-research-program.md`](25-research-program.md). Gate defined in [`docs/14-labeling-codebook.md`](14-labeling-codebook.md) and enforced in `experiments/score_labels.py`: κ < 0.60 means the codebook is underspecified, revise it and re-label, do not argue individual rows into agreement.

**This gate failed, by design — it exists to be failable, same as M1.**

## The result

Two annotators labelled all 265 rows of `label_sheet.tsv` independently (`data/processed/labels_annotator_A.tsv`, `_B.tsv`; raw handoff preserved in `data/annotation/`).

| | |
|---|---|
| n | 265 |
| raw agreement | 83.4% |
| **Cohen's κ** | **0.559 (moderate)** |
| pre-registered threshold | ≥ 0.60 |
| gold (agreed rows) | 221 |

## The disagreement pattern is not noise — it is one confusion

Of 44 disagreements, **40 (91%) are A0 vs A2**, exactly one confusion pair:

```
A0 vs A2: 40
A0 vs A1: 2
A0 vs A3: 1
A2 vs A3: 1
```

This is the sharpest possible outcome for a κ gate: the codebook is not broadly ambiguous, it fails at one specific decision boundary. Sample cases, full list in `data/processed/label_disagreements.tsv`:

| server / tool | A | B | description |
|---|---|---|---|
| `Cyreslab-AI/builtwith-mcp-server` / `domain_lookup` | A0 | A2 | "Get technology stack information for a specific domain" |
| `Fast-Transients/lodgify-mcp-server` / `get_properties` | A0 | A2 | "Get a list of properties with optional filtering" |
| `Digital-Crew-Technologies/max-mcp-server` / `linkedin_create_post` | A0 | A2 | "Create a LinkedIn post from the connected account" |

The pattern: **read tools whose relationship to a write tool is plausible but not textually obvious** — a `get_properties` that might or might not reflect what a sibling `create_property` did, judged from a truncated description and a sibling list, with no way to actually call either tool. One annotator is reading structural plausibility (a getter exists, call it A2); the other is applying the A0 test literally (can I name the specific check? no evidence the getter reflects *this* write) and calling it A0.

## Diagnosis: the A0 test asks for evidence the sheet does not provide

[`14-labeling-codebook.md`](14-labeling-codebook.md)'s A0 test requires completing: *"After calling this tool, the client could call **___** and expect to see **___**."* That test was written for a human with the tool's real behavior available. The sheet gives only a truncated description, a field list, and a sibling name list — never the sibling's own description or schema. An annotator cannot always tell whether `get_properties` genuinely reflects `create_property`'s effect, or merely shares a noun with it — **which is precisely the noun-vs-field ambiguity documented as the classifier's own historical failure mode** ([`21`](21-real-server-results-and-options.md), [`24`](24-calibrated-auditing-the-real-experiment.md) §5.1). The codebook's human procedure and the automatic classifier are failing on the same axis, which is worth noting rather than coincidental.

## What this does not mean

- It does not mean the annotators labelled carelessly — 91% concentration on one boundary is the signature of a genuine specification gap, not random error.
- It does not validate or invalidate the classifier. That comparison **could not run this session** — see below.
- It does not retroactively change any number reported before today. The A0 share (69.7%) was already flagged instrument-relative in [`05`](05-verifiability-taxonomy.md) §5 and [`26`](26-m1-novelty-gate.md); this result is why.

## Second finding: the classifier-validation half of M0c is blocked by a data bug, now fixed going forward

Running `score_labels.py` against `data/processed/d1_corpus.jsonl` returned "no overlap" — **zero** of 265 sampled `(server_id, tool)` keys exist in the current corpus file.

**Root cause.** `experiments/make_label_sample.py` wrote only truncated display fields to `label_sheet.tsv` (description cut to 180 chars, fields to 80) and relied on re-loading the live corpus by key at scoring time. `d1_corpus.jsonl` is a GitHub harvest, gitignored, regenerated over time and non-deterministic across runs — a server present when the sample was drawn is not guaranteed to still be present later, or to contain the same tools. `label_sheet.tsv` was drawn from a corpus snapshot that no longer exists on disk; no snapshot was archived alongside it. **The sample was orphaned from its own source data the moment the corpus was next regenerated.**

**Fixed, so this cannot recur:**
- `make_label_sample.py` now writes `*.corpus_archive.jsonl` alongside every sample — the exact `ExtractedTool` records (including `output_fields`, `annotations`) that `classify()` needs, not the truncated display fields.
- `score_labels.py` prefers that archive over re-loading the live corpus, and when neither an archive nor a match exists, explains why rather than printing a bare "is --corpus right?" and stopping.
- Two regression tests (`tests/test_label_archive.py`) pin the preference and the fallback message.

**For this specific 265-row sample, classifier-vs-human validation cannot be run** — no archive was written for it (it predates the fix) and the original corpus snapshot is not recoverable. The inter-annotator κ above is unaffected; it never depended on the corpus file.

## Next step, per the codebook's own rule

Do not adjudicate the 40 A0/A2 disagreements case by case. Revise [`14-labeling-codebook.md`](14-labeling-codebook.md)'s A0 test to give annotators what they are missing — most directly, showing each candidate sibling's own description/schema next to the row under judgment, not just its name — then re-label and re-score. Classifier-vs-human validation needs a **fresh sample** drawn with `make_label_sample.py` (now archiving correctly) so it is not blocked the same way.

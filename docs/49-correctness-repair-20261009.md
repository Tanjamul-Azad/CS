# EffectSeal correctness repair — completed 2026-10-09

The working paper and implementation now agree on typed canonical effects,
actual durable send admission, measured residual capacity, and the limits of
the evidence. This closes the implementation and reporting issues identified
in the October 9 audit; known scientific negative results remain explicit.

## Repairs

- Typed JSON and path-array keys remove string/number/null and dotted-path collisions. Per-field inference and separate structure checks prevent a wildcard crossing fields. Duplicate JSON/headers, malformed framing and unsafe authorities fail closed; the broker owns framing and forwards normalized JSON.
- Argument substitutions preserve JSON escaping. Clock holes use trusted UTC admission time. Unicode capacities count admitted scalar alphabets; canonical-view scope excludes unexamined raw metadata.
- The actual proxy reserves in SQLite before the first send, coordinates workers, refuses spent approvals after restart and reports partial/unknown outcomes. A reservation is not reusable after an ambiguous effect. This is at-most-once admission, not exactly-once vendor execution.
- New v2 bundles preserve every pin attempt, honest trial, variant, verdict, broker/far-side record, source snapshot and immutable image identity. Offline checks re-infer templates, replay sequences, recompute rates/intervals, judge matching and capacities, and verify hashes.
- Tables and figures use explicit current evidence pointers. Canonical build/check/archive scripts now target `paper/submission`; PDF/source hashes detect stale builds. The body-page checker counts body text on a shared appendix page, and the release checker inspects link annotations for a hidden placeholder URL.
- Current claim matrix, roadmap, status, code/workflow maps, narration scripts and defense walkthrough are aligned. Earlier versions and raw runs remain available as history. The manuscript is still excluded from Git.

## Evidence and tests

| Check | Current result | Scope |
|---|---|---|
| Windows full tests | 328 passed, 3 skipped | Includes private working PDF checks |
| Final fresh Linux clone | 327 passed, 4 skipped; 12/12 steps PASS | Source commit `3fc86f24d5b6f55cf28998cfc7eebccce69808df`; no internet/model API during the run |
| Original registry cohort | 10/12 coverage; 120/120 honest protocol trials | Repaired retrospective rerun of original split; two coverage failures retained |
| Original fixed sends | 792/816 refused | Silent no-ops excluded; cluster interval 91.2–100% |
| Original adaptive variants | 612/648 refused | 24 splitifi and 12 held-out travel admissions; cluster interval 85.3–100% |
| Additional held-out cohort | 40 screened, 5 qualified; honest 60/60 | Target six not met; empty-payload and telemetry cases retained; two packages share an author |
| Additional attacks | Fixed 312/312; adaptive 324/336 refused | All 12 adaptive admissions on conekta; two tools have no JSON string-leaf cases |
| Rebuilt Postmark | 21/21 unauthorized sends refused; 3 no-ops incomplete | Source-modified attacks against mocks; approved prefixes may be partial |
| Official GitHub checks | Fixed 84/84; adaptive 24/24 refused | Captured-request transformations; 12 no-ops incomplete |
| Actual proxy races | One far-side request in all 100 races; restart 403 | Eight contenders, two workers; repeated successfully in the fresh Linux run |
| Quiet Windows proxy timing | Gate p50/p95 14.5/33.6ms; record-only 1.7/20.9ms | 300 samples; includes durable state, logs and local HTTP; excludes TLS/WAN/vendor |
| Independent pin controls | Honest agrees; session noise differs; stable Bcc poisoning agrees | Agreement is repeatability, not honesty |
| PDF | 13 body pages, 19 total; 49 resolved citations | Letter, embedded fonts, no replacement characters or unresolved/overfull diagnostics; rendered visual inspection |

Current pointers: `artifact/paper-evidence-20261009.json`.
Final Linux logs and raw regenerated results:
`artifact/results/reproduction_clean_linux_20261009-230352/`.
Hash-locked dependency-install log, exact image identity and pip freeze are
preserved. Skipped Linux tests cover Windows-only behavior and the private PDF.
Both Linux reproductions are retained. The reproduction script's nonzero exit
on a deliberately failed step is itself regression-tested.

## Local deliverables

- Current handwritten source: `paper/submission/main.tex` and `sections/`.
- Verified named PDF: `output/pdf/effectseal-repaired-20261009-230703.pdf`.
- Source-only Overleaf ZIP, outside Git: `../EffectSeal_Overleaf_20261009-230703.zip`.
- Anonymous working PDF: `output/pdf/effectseal-anonymous-draft-20261009-230703.pdf`.
- Anonymous source draft: `../EffectSeal_Anonymous_Draft_20261009-230703.zip`.
- Build manifest: `paper/submission/BUILD_MANIFEST.json`; delivery hashes and QA logs: `output/reviews/2026-10-09-codex/`.

The archive source hashes were verified, and both PDF modes compiled. Original
private source and figures were backed up before modification. Public commits
contain implementation, evidence, scripts and documentation only.

## What is still a limit or release requirement

Local held-out false blocks remain 6/48, failing the frozen 5% utility criterion.
The original zero-admission network criterion also failed. Positive slack and
stable poisoning remain channels; a trusted semantic specification cannot be
inferred from repeated agreement. Mock protocol outcomes do not prove vendor
task completion. Historical paid-model agents, real host-policy baselines and
provider test replay remain separately dated; they were not silently rescored.
There is no unsupported acceptance-probability or ecosystem prevalence claim.

The anonymous draft still has an artifact URL placeholder. Its release check
correctly fails on that link. Insert a real reviewed anonymous export URL and
complete author/ethics/conflict/ORCID review before submission. These are actual
release inputs, separate from the completed correctness repair.

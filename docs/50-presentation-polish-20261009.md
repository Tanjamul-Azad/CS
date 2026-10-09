# EffectSeal presentation update - 2026-10-09

The working draft now presents coverage, honest protocol outcomes and adaptive
failures together in the main results, with canonical-view capacity beside the
template evaluation. This is a presentation update using the existing selected
evidence; it introduces no experimental scoring or new empirical claims.

## Changes

- Added the main-paper network cohort summary (Table 5). Development, original
  held-out, original total and additional held-out rows show template coverage,
  honest admissions, fixed refusal and adaptive refusal. The original total
  includes its two split rows. Additional 5/5 coverage is conditional on five
  qualifying servers from 40 candidates, with the unmet target of six explicit.
- Promoted canonical-view slack from the supplementary appendix to the main
  template results (Figure 7). Its caption explains zero, unbounded capacity and
  the exclusion of raw container metadata.
- Replaced the research-question mapping table with concise prose. Condensed
  repeated results, implementation, discussion and conclusion text to retain
  the 13-page body. Local false blocks, both cohorts' adaptive admissions,
  pin-time poisoning, mock scope and statistical uncertainty remain explicit.
- Arranged the paper as body, Ethical Considerations, Open Science, References,
  then supplementary appendices C-E. This preserves the ethics/open-science
  placement used in the official 2026 instructions; the 2027 CFP does not
  explicitly mandate their order relative to References. Supplementary tables
  now remain together in normal reading order on the final page.
- The table generator regenerates both main and supplementary results directly
  from the selected raw bundles. The archive tool accepts an explicitly supplied
  source folder for an already sanitized anonymous export.

## Verification

- Both named and anonymous PDFs: 13 body pages, 19 total; 49 resolved citation
  keys; Letter pages and embedded fonts; no replacement glyphs, overfull boxes
  or unresolved-reference diagnostics.
- Main paper: 8 figures, 6 tables, 1 algorithm. Whole document: 9 figures,
  8 tables, 2 algorithms.
- All named pages rendered and inspected. Summary table and slack chart also
  checked in grayscale. Anonymous first page inspected; rendered pages 2-19
  are pixel-identical to the reviewed named version.
- Full Windows suite: 328 passed, 3 skipped in 20.82 seconds.
- Current offline evidence verifier: all 10 checks passed. Both archives contain
  28 compilation inputs and verified source SHA-256 manifests.
- Readiness reports zero manuscript/source/static-evidence blockers. The two
  previously recorded release inputs remain: a reviewed anonymous artifact URL
  and final author/ethics/conflict/ORCID review. The drafts retain the artifact
  URL placeholder and are not an anonymous submission release.

## Local deliveries

- Named PDF: `output/pdf/effectseal-polished-20261009-presentation-232559.pdf`.
- Anonymous PDF: `output/pdf/effectseal-anonymous-polished-20261009-presentation-232559.pdf`.
- Named source: `../EffectSeal_Overleaf_Polished_20261009-232559.zip`.
- Anonymous source: `../EffectSeal_Anonymous_Polished_20261009-232559.zip`.
- QA, source diffs and delivery hashes: `output/reviews/20261009-presentation-232559/`.
- Pre-edit private backup: `../private_submission_backups/20261009-presentation-232559-before/`.
- Sanitized source: `../private_submission_backups/20261009-presentation-232559-anonymous/`.

Previous PDFs and archives are preserved. Manuscript sources, PDF deliveries,
anonymous exports and rendered pages remain outside public Git tracking.

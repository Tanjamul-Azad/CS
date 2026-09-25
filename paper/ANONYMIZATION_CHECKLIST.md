# Double-Blind Submission and Artifact Checklist

Target assumptions: USENIX Security 2027 Cycle 2 primary; IEEE S&P 2027 Cycle
2 only if every P0 gate closes by the internal cutoff.

## Paper identity

- [ ] Remove author names, affiliations, acknowledgments, grant numbers, and
      institution-specific infrastructure names.
- [ ] Cite the authors' prior work in third person; blind a reference only when
      third-person citation is genuinely infeasible.
- [ ] Remove PDF author/creator metadata and inspect embedded file names.
- [ ] Search source, generated PDF text, figures, and appendices for real names,
      usernames, email addresses, institution names, and local absolute paths.
- [ ] Ensure title, author list, abstract, ORCIDs, topics, and conflicts are
      final before the venue's registration deadline.

## Repository identity

- [ ] Create a fresh anonymous export; never expose this repository's Git
      history or contributor graph.
- [ ] Exclude `.git`, issue/PR links, commit hashes that map to the public repo,
      author-bearing badges, funding files, and local IDE metadata.
- [ ] Replace public GitHub/project URLs that identify the author with the
      venue-compliant anonymous artifact URL.
- [ ] Verify archive paths do not contain Windows usernames or institution
      course directories.
- [ ] Inspect source comments, docs, notebook metadata, and generated logs for
      identifying text.
- [ ] Use an anonymous hosting service with no reviewer tracking and an expiry
      covering the full review/shepherd period.

## Secrets and unsafe data

- [ ] Confirm `.env`, keys, tokens, package-manager credentials, browser data,
      and shell history are absent.
- [ ] Scan all JSON/JSONL/log artifacts for tokens, email addresses, home paths,
      hostnames, and unexpected third-party output.
- [ ] Confirm no raw untrusted scratch directory or package cache is bundled.
- [ ] Include only curated result rows named by the artifact manifest.

## Scientific consistency

- [ ] `python scripts/verify_refs.py` passes.
- [ ] `python scripts/submission_check.py --tests` passes with zero OPEN claims,
      unchecked P0 gates, and EVIDENCE GATE markers.
- [ ] A clean clone runs `python scripts/run_quick_artifact.py` successfully.
- [ ] Full tables/figures regenerate from the anonymous bundle without access
      to the original machine.
- [ ] Paper numbers match the release JSON hashes exactly.
- [ ] Every limitation in `paper/CLAIM_EVIDENCE_MATRIX.md` is present wherever
      its claim appears in the paper.

## USENIX Security 2027 dates (AoE)

- [ ] Mandatory registration: 2027-01-19.
- [ ] Paper submission: 2027-01-26.
- [ ] Submission artifact: 2027-01-29.
- [ ] Open Science appendix is included in the submitted paper.
- [ ] Ethics appendix is included unless a documented final decision removes
      it.

Official CFP: <https://www.usenix.org/conference/usenixsecurity27/call-for-papers>

## IEEE S&P 2027 Cycle 2 dates (AoE, stretch only)

- [ ] Abstract/author/ORCID/conflict registration: 2026-11-10.
- [ ] Paper submission: 2026-11-17; upload a draft at least 24 hours earlier.
- [ ] IEEE `conference,compsoc` template and US Letter paper size are used.
- [ ] If submitted and rejected after review, account for the one-year IEEE S&P
      resubmission restriction.

Official CFP: <https://www.ieee-security.org/TC/SP2027/cfpapers.html>

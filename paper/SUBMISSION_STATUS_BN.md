# MCPGate Submission Status (2026-09-26)

## এক লাইনের verdict

Project এখন একটি strong working paper + auditable artifact scaffold; এখনও
submission-ready নয়। Local implementation/test/paper-formatting side শক্ত,
কিন্তু human validation এবং fresh isolated real-server evidence ছাড়া top-tier
claim করা যাবে না।

## এখন যা সত্যিই complete

- Integrated contract + allowance + private staging + same-read promotion path
  reusable code-এ আছে।
- Controlled baselines, seven ablations, content/path/replay/TOCTOU/security
  cases, real child-process concurrency, এবং trusted-writer comparison আছে।
- Current regression: 231 passed, 1 platform skip; reference gate passes।
- SQLite WAL/FULL-sync durable allowance backend restart replay এবং
  competing-backend final-slot race fail-closed করে; orphaned effect outcome
  এখনও domain-specific reconciliation ছাড়া UNKNOWN।
- Manuscript-এর 21টি used citation primary-source verified; 41টি unused entry
  quarantined।
- Official USENIX Security 2027 template-এ anonymous working PDF build হয়েছে।
  এটি 15 pages total: 11 body, pages 12--13 Ethics/Open Science appendices,
  pages 14--15 references। Letter size, embedded fonts, blank Author metadata,
  এবং figure rendering check pass করেছে।
- Ten held-out primary candidates plus same-class reserves package
  version/integrity-সহ security result দেখার আগে pre-registered হয়েছে।
- Pre-effect eligibility-তে 12/13 candidate `tools/list` পর্যন্ত পৌঁছেছে;
  actual mutating workflow + trusted oracle যাচাই করে 10-server manifest
  `FROZEN` হয়েছে (EXACT 4, CONSTRAINED 4, UNDERSPECIFIED 2)। Freeze-এর আগে
  attack call বা defense outcome চালানো হয়নি।
- Python 3.12 Linux dependency graph exact version ও SHA-256 hashসহ lock;
  clean container-এ `pip --require-hashes` install rehearsal pass করেছে।
- Pinned `filesystem-mcp@1.3.0` integrated Linux-container run pass করেছে:
  honest COMMITTED; path/content mutations trusted store থেকে refused; raw
  JSON, image digest, Docker এবং container-kernel metadata preserved। Path
  diversion `/tmp/exfil.dat`-এ landed হওয়ায় limitation-ও একই artifact-এ আছে।
- Quick runner pass করেছে; full runner incomplete evidence থাকলে fail-closed।
- Network pre-send broker এবং transactional/private-copy SQL mediation-এর
  threat model, attack set, baselines, metrics ও go/no-go rule
  `paper/NETWORK_SQL_EXTENSION_PLAN.md`-এ pre-registered। Exact HTTP request,
  trusted DNS/address pinning, response bound, durable replay এবং SQLite full
  schema/row diff + atomic private-copy promotion-এর local core ও adversarial
  unit tests আছে। Direct-egress namespace, real MCP adapters, matched baselines
  ও raw artifacts না হওয়া পর্যন্ত এগুলো current result claim নয়।
- 10-server matched evaluation plan outcome দেখার আগে
  `artifact/held-out-evaluation-plan.json`-এ frozen হয়েছে। এতে five conditions,
  per-server scenario applicability, 100-trial race counts, independent oracle,
  outcome fields এবং fail-closed decision rules আছে।
- Primary target USENIX Security 2027 Cycle 2। Official page budget, deadlines,
  anonymous/Open Science requirements, award-winning structural models এবং
  human-readable prose rules `paper/VENUE_AND_WRITING_STANDARD.md`-এ fixed।

## যে কারণে এখনই submit করা যাবে না

1. 265-row Round-2 sheet দুইজন independent human এখনও label করেননি।
2. Frozen workloads-এ five matched conditions চালানো হয়নি।
3. Clean release commit থেকে final image/result bundle rerun হয়নি।
4. Manuscript-এ দুইটি explicit `EVIDENCE GATE` আছে; release PDF checker তাই
   ইচ্ছাকৃতভাবে fail করে।

## এখন আপনার কাছ থেকে দরকার

### A. দুইজন human annotator

তাদের `paper/ROUND2_ANNOTATION_RUNBOOK_BN.md` এবং আলাদা A/B TSV দিন। একজন
মানুষ দুই file করতে পারবেন না। তারা শেষ না করা পর্যন্ত একে অন্যের label
দেখবেন না।

### B. Current PC-এর Docker/WSL2 release environment

Existing Docker Desktop 4.89.0 / Docker 29.7.2 backend এই PC-তে চালু হয়েছে;
Linux kernel `6.18.33.2-microsoft-standard-WSL2`। Integrated pinned-server run
এখানেই pass করেছে। Held-out candidates personal credentials ছাড়া disposable,
network-controlled containers-এ চালাতে হবে; host directories/secrets mount করা
যাবে না।

Manual read-only GitHub Actions fallback প্রস্তুত আছে:
`.github/workflows/release-evidence.yml`; Bangla instructions:
`paper/CI_LINUX_RUNBOOK_BN.md`। Local GitHub token বর্তমানে invalid, তাই push বা
remote dispatch না হওয়া পর্যন্ত এটি prepared path, completed run নয়।

### C. Author metadata

2027-01-19-এর আগে final title, সম্পূর্ণ author list, ORCID, topics, এবং
conflicts freeze করতে হবে। এগুলো automation দিয়ে invent করা যাবে না।

## Machine handoff sequence

Final release run-এর order বদলাবেন না:

1. clean clone/commit এবং secret scan;
2. frozen candidate/manifest/log hash verify;
3. integrated pinned server rerun;
4. identical workloads-এ five matched conditions;
5. full artifact runner;
6. tables/figures/PDF regenerate;
7. claim matrix, evidence gates, appendices, and anonymous export finalize।

## Official deadlines (AoE)

- USENIX Security 2027 Cycle 2 registration: 2027-01-19
- Paper: 2027-01-26
- Artifact: 2027-01-29

Internal schedule এবং go/no-go dates: `paper/EXECUTION_CALENDAR.md`।

## Source of truth

- Scientific claim state: `paper/CLAIM_EVIDENCE_MATRIX.md`
- Required work/order: `paper/SUBMISSION_ROADMAP.md`
- Automated readiness: `python scripts/submission_check.py --tests`
- Full release preflight: `python scripts/run_full_artifact.py --preflight-only`
- Current review PDF: `output/pdf/mcpgate-usenix-working-draft.pdf`

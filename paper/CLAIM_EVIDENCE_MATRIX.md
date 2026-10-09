# Current claim–evidence matrix

Updated 2026-10-09 after the correctness audit. This file supersedes the
pre-repair matrix preserved in `paper/history/claim-evidence-before-20261009-repair.md`.
Evidence pointers are explicit in `artifact/paper-evidence-20261009.json`.
READY means supported within its stated experiment; QUALIFIED requires its
limitation beside the claim. A failed deployment criterion is not silently
converted into a passing criterion.

| ID | Current claim | Evidence | Status | Required qualification |
|---|---|---|---|---|
| C1 | Equal raw transcripts give equal passive-monitor information. | `docs/05`, `docs/33`, `demo_theorem1.py` | READY | An observation boundary, not a new cryptographic primitive. Normalized empirical matches do not prove raw equality. |
| C2 | No tested registry response auditor reached the frozen operating point. | `results/tables/operating_points.md`, funnel 8692/4121/1242 | QUALIFIED | Credential-free launchable subset; no ecosystem prevalence claim. |
| C3 | Honest-run local contracts stopped 32/32 landed attacks on seven development servers. | `matched_filesystem_consistent.json`, `matched_sql_consistent.json` | QUALIFIED | Same-call references, not pin-time generalization. |
| C4 | Local templates stopped 75/75 development and 39/39 held-out landed attacks; blocked 1/84 and 6/48 honest calls. | `template_generalization_run4.json`, `batch2_templates.json` | QUALIFIED | Held-out false blocks exceed the frozen 5% criterion; later fixes lack a new eligible local cohort. |
| C5 | Original network cohort: 10/12 template coverage, 120/120 honest protocol trials, 792/816 fixed send refusals. | active `network_matched` bundle | QUALIFIED | Conditional on coverage; check-level transformations; mocks do not establish vendor task completion. Development zero-admission criterion FAILED. |
| C6 | Original adaptive leaf attacks: 612/648 refused, 36 admitted (24 splitifi, 12 held-out travel). | active `network_matched` bundle | QUALIFIED | Every string leaf and request position tested, not every possible adversarial request. Cluster CI 85.3–100%. |
| C7 | Additional held-out selection: 40 screened, 5 qualified; 60/60 honest protocol trials, 312/312 fixed sends refused, 324/336 adaptive refused. | active `additional_selection`, `additional_network_held_out` | QUALIFIED | Target six not met; 12 conekta adaptive admissions; two tools have zero string-leaf cases; telemetry/empty payload included; two packages share an author. |
| C8 | Rebuilt Postmark: 21/21 unauthorized sends refused; 3 no-ops incomplete; honest 12/12 admitted. | active `network_postmark` bundle | READY | Rebuilt attack code against mocks, including approved prefixes before a later refusal; not transactional rollback. |
| C9 | Actual ToolHive/AgentBound each refused 3/21 Postmark send cases; pinning alerted on 0/8 attack versions. | dated ToolHive/AgentBound/mcp-scan bundles | QUALIFIED | Version-level alerts and send prevention are distinct metrics; local baseline values are mechanism mappings. |
| C10 | Official GitHub: 12/12 honest; 84/84 fixed sends and 24/24 adaptive variants refused; 12 no-ops incomplete. | active `network_named` bundle | QUALIFIED | Check-level request transformations; one official implementation. |
| C11 | Quiet integrated proxy timing: gate p50/p95 14.5/33.6ms; record-only 1.7/20.9ms. | active `network_integrated`, 300 raw samples each | QUALIFIED | Includes state reads, instantiation, SQLite, logs and loopback HTTP; excludes TLS, WAN/vendor latency; development machine. |
| C12 | Actual proxy: exactly one far-side effect in all 100 races with eight requests/two workers; restart replay 403. | active integrated bundle, `test_network_repairs.py` | READY | Durable at-most-once admission; ambiguous sends remain UNKNOWN/spent, not exactly-once effects. |
| C13 | Separate pin sessions agree on honest and stable poisoning, disagree on session noise. | active `network_crosssession` bundle | QUALIFIED | Repeatability is not an honesty oracle; broker transformations against mocks. |
| C14 | Local canonical-view capacities use Unicode scalar alphabets; raw ZIP metadata is outside the bound. | active `local_capacity_reanalysis`, `reanalyze_local_capacity.py` | QUALIFIED | Corrected capacities without rescoring historical local security outcomes. |
| C15 | Post hoc normalized matching gives no observed judge advantage: 0/0,21.4/21.4,35.7/40.0,28.6/28.6%. | active `judge_matched_sensitivity` | QUALIFIED | Matched approved requests and normalized signatures, not raw transcript equality or a new preregistered judge trial. |
| C16 | Recorded agents: compromised local/network effects admitted without defense were kept out with admission. | dated OpenAI/Llama agent bundles | QUALIFIED | Historical runs, narrow tools/tasks/models, incomplete sessions and honest blocks retained; no fresh model API scoring. |
| C17 | Vendor Postmark test endpoint accepted 12 honest requests and 7/9 undefended diversions. | `network_postmark_live_20261009-170400.json` | QUALIFIED | Separately dated test-token replay; no delivered email; two stated scope/guard exclusions. |
| C18 | Local and network model invariants hold, with mechanism-removal counterexamples. | TLA+/TLC and independent Python checkers | READY | Abstract models, not a proof of all Python/container/TLS behavior. |
| C19 | v2 network bundles support offline inference, request replay, counts, intervals, hashes and source/image provenance. | `verify_current_evidence.py`, bundle snapshots | READY | Older aggregate-only data and registry measurements have narrower reproduction scope. |
| C20 | All MCP effects are secure, template agreement proves honesty, or held-out templates are universally useful. | contradicted by recorded failures | RETIRED | Never claim. |

Clean Linux reproduction is reported with its exact source commit in the dated
reproduction bundle. No new run is asserted until its step logs exist.
Independent annotation is unfinished; no retained claim requires A0 prevalence.

Current offline reproduction: 12/12 steps PASS at source commit `3fc86f2`,
Linux tests 327 passed/4 skipped; Windows tests 328 passed/3 skipped.
Full repair and deliverable record: `docs/49-correctness-repair-20261009.md`.

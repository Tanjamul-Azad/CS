# Claim–Evidence Matrix

Status vocabulary:

- **READY** — evidence supports the precise claim as written.
- **QUALIFIED** — usable only with the listed limitation in the same paragraph.
- **OPEN** — work is required before the claim enters the paper.
- **RETIRED** — do not claim.

| ID | Proposed paper claim | Evidence | Status | Required action |
|---|---|---|---|---|
| C1 | A passive client cannot distinguish honest and diverted effects when their client-visible transcripts are identical. | `docs/05`, `docs/33`, `experiments/demo_theorem1.py` | READY | Position as a boundary/application of indistinguishability, not a wholly new proof technique. |
| C2 | No tested response-auditing configuration reached a usable operating point on the 1,242-server usable corpus. | `results/tables/operating_points.md`, notebooks 04–06, `docs/30` | READY | Define “usable”; report the permissive detections and 71.8–78.3% FPR, not only “0%”. |
| C3 | The full corpus funnel is 8,692 candidates → 4,121 launches → 1,242 usable paired trials. | `results/tables/funnel.md`, `run_status.md`, manifest | READY | Report selection effects; do not generalize to credentialed servers. |
| C4 | 69.7% of tools are A0. | classifier output; κ = 0.559 | OPEN | Complete Round-2 labeling. Until then call it an instrument reading, not prevalence. |
| C5 | L1/L2/L3 separate destination, structure, and content-level authorization. | `docs/27`, controlled ladder, seven real servers | QUALIFIED | Keep per-property verdicts; state that L2 added no protection on tested free-text tools. |
| C6 | Opaque SQL declarations do not expose a schema-derived content boundary. | two independent SQL server probes in `docs/29` | READY | State as a two-implementation negative replication, not a universal SQL theorem. |
| C7 | M2 proper meets 10/10 prevention, 1/14 UNKNOWN, and 0 pp honest-completion gap on registered scenarios. | `results/tables/boundary_probe_m2.md`, `docs/31` | READY | Preserve paired undefended controls and exact scenario scope. |
| C8 | The final MCPGate filesystem pipeline is implemented end to end against a pinned real server. | `artifact/results/integrated_real_server.json`; `filesystem-mcp@1.3.0`; exact npm integrity; Linux container/image digest; honest COMMITTED; path/content mutations refused from trusted state; integrated regression | READY | Preserve the explicit `/tmp/exfil.dat` world-effect limitation and repeat from the clean release commit before artifact freeze. |
| C9 | MCPGate prevents external path-diversion effects. | `/tmp/exfil.dat` was written in `docs/37`, `41`, `42` | RETIRED | Either add namespace confinement or claim only trusted-state rejection. |
| C10 | MCPGate keeps mismatching staged results out of trusted committed state in the tested real-server scenarios. | `docs/37`, M5 results | READY | Always distinguish this from rollback/world-effect prevention. |
| C11 | The mechanism transfers across heterogeneous unmodified servers. | seven-server M3 sweep; frozen 10-server pre-outcome eligibility manifest | QUALIFIED | Corpus/adapter/oracle freeze is complete, but broad generality language still requires the matched five-condition outcomes. |
| C12 | Same-read commit closes the observed TOCTOU race. | 5/20 → 0/20, `docs/32` | QUALIFIED | Increase repetitions and report an interval; claim the tested race, not all TOCTOU. |
| C13 | Pre-effect allowance reservation closes the observed replay/double-commit gap. | `docs/38`; `AllowanceLedger`; integrated replay, exhaustion, and concurrent-last-slot tests | READY | Now wired into `FilesystemMediator`; retain the different-ID replay ablation in the Docker evaluation. |
| C14 | A filesystem-only mediator cannot observe socket exfiltration. | `docs/39` | READY | Present as a demonstrated scope boundary, not a bug fixed by tuning. |
| C15 | A fixed observation window cannot distinguish every honest slow write from every patient delayed attack. | `docs/40` | READY | Phrase as the measured ambiguity of this design; propose explicit completion/freezing as future work. |
| C16 | Static least privilege is structurally blind to content substitution at an allowed writable path. | two real servers, `docs/41`, `42` | READY | Limit empirical statement to two servers; explain the permission semantics argument separately. |
| C17 | Static least privilege never catches path diversion. | second server refused relative-path diversion | RETIRED | Replace with the contingent path-resolution claim. |
| C18 | The mechanism outperforms state-of-the-art adjacent research systems. | no head-to-head external implementation | RETIRED | Compare properties; add a reproducible external baseline only if feasible. |
| C19 | Contract authenticity and expiry are enforced. | canonical ID/immutability only | RETIRED | `Valid(C)` is an explicit trusted-input assumption; do not claim signing or expiry as an implemented contribution. |
| C20 | The mechanism handles genuine concurrent calls. | atomic thread test plus `run_concurrency_eval.py`: two real child writers overlap in distinct staging roots and both commit; final-slot competition starts one child | QUALIFIED | Local process evidence is now present; add pinned Linux/third-party-server overlap and effect-to-call attribution before an unqualified ecosystem claim. |
| C21 | The evaluation establishes network/process-domain mediation. | not evaluated | RETIRED | Narrow the paper to filesystem effects. |
| C22 | All paper results are reproducible from published artifacts. | main tables have manifest; several M3–M5 JSON files are gitignored | OPEN | Publish compact raw results, pin dependencies, and add one-command reproduction. |
| C23 | Removing individual MCPGate properties re-exposes their registered failure modes in the controlled implementation. | `experiments/run_mediator_ablations.py`; `artifact/results/controlled_ablations.json`; generated table; regression test | READY | Keep this explicitly local/deterministic; do not present it as a third-party-server or performance result. |
| C24 | For the current exact single-write workload, a trusted direct writer is the simpler engineering baseline and has lower local latency than invoking the staged mediator. | `experiments/run_exact_write_baseline.py`; 100-repetition development run; security cases; generated table | QUALIFIED | Report the measured 1.671x p50 ratio only as development-machine data; use it to narrow utility, not as a release performance result. |
| C25 | A durable allowance backend prevents restart replay and competing processes from reusing the same final slot. | `SQLiteAllowanceLedger`; restart, unavailable-result, and two-backend contention tests; durable backend wired into the revised real-server adapter | READY | Claim fail-closed at-most-once entry only. Orphaned RESERVED outcomes still require domain-specific reconciliation; do not claim exactly-once world effects. |

## Abstract-safe claims today

The abstract may currently say:

- 8,692 candidates, 4,121 launches, and 1,242 usable paired trials;
- no tested response-auditing configuration reached a usable operating point;
- the M2 registered controlled scenarios met their pre-registered thresholds;
- a seven-server transfer study reproduced both the ladder's positive prediction
  and the underspecified-SQL negative prediction;
- adaptive evaluation found two bugs and demonstrated two limits; and
- held-out comparison showed static permissions were blind to content
  substitution on both tested servers.

The abstract may not yet say:

- empirically validated end-to-end real-server enforcement with the revised integrated path;
- generality across MCP servers;
- prevention of all external effects;
- validated A0 prevalence;
- network/process mediation; or
- superiority to state-of-the-art systems.

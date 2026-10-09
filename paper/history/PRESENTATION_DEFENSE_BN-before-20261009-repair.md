# Presentation and Technical Defense Guide (Bangla)

Status: repository-grounded working guide. এটি paper-এর claim boundary মেনে
লেখা; কোনো pending held-out/annotation result-কে completed হিসেবে বলা
যাবে না।

## 1. এক বাক্যে project

> MCP server নিজেই effect করে এবং নিজেই success response দেয়; তাই response
> দেখে effect সত্য কি না নিশ্চিত হওয়া যায় না। MCPGate response বিশ্বাস না করে
> untrusted server-এর staged filesystem result-কে approved per-call contract-এর
> সঙ্গে মিলিয়ে trusted store-এ admission দেয় বা reject করে।

আরও ছোট version:

> **We move verification from what the server says to what enters trusted
> state.**

## 2. পাঁচ মিনিটের GitHub proof walkthrough — Docker ছাড়াই

Sir-কে random file না দেখিয়ে এই order-এ দেখাবেন। প্রতিটি file খোলার আগে এক
লাইনে বলবেন কেন খুলছেন।

1. `paper/CLAIM_EVIDENCE_MATRIX.md`
   - বলবেন: “প্রথমে আমি claim boundary দেখাচ্ছি—কোনটা READY, কোনটা
     QUALIFIED, কোনটা এখনো OPEN, আর কোন claim আমরা retire করেছি।”
   - C8 দেখিয়ে বলবেন pinned third-party Docker run pass এবং raw artifact আছে।
     C9 দেখিয়ে বলবেন `/tmp/exfil.dat` সত্যিই লেখা হয়েছিল বলে external
     path-diversion prevention claim আমরা নিজেরাই retire করেছি।
2. `src/mcpgate/contract.py`
   - `EffectContract` ও `check()` দেখাবেন।
   - বলবেন: “Approved operation, exact argument keys, bound values, and
     allowance—সব frozen contract identity-র অংশ। Unmentioned field fail
     closed।”
3. `src/mcpgate/allowance.py`
   - `AllowanceLedger.reserve()` দেখাবেন।
   - বলবেন: “এটা atomic check-and-reserve; check তারপর আলাদা increment নয়।
     তাই two concurrent calls final slot দুবার নিতে পারে না।”
4. `src/mcpgate/mediator.py`
   - `StagedInvocation.boundary_closed`, `FilesystemMediator.call()`,
     `_snapshot_tree()`, `_atomic_commit()` দেখাবেন।
   - বলবেন: “Preflight shape check-এর পরে slot reserve হয়; server private
     staging-এ চলে; trusted adapter writer boundary close না করলে commit হয় না;
     transport arguments আবার check হয়; tree একবার materialize হয়; decision-এর
     same bytes atomically promote হয়।”
5. `tests/test_filesystem_mediator.py`
   - honest, hidden-field, transport rewrite, wrong content/extra/symlink,
     open boundary, TOCTOU, replay, unsafe path, concurrent last-slot tests
     scroll করে দেখাবেন।
   - বলবেন: “এগুলো শুধু happy-path unit test নয়; প্রতিটি test একটি concrete
     adversarial failure mode বা invariant-এর test।”
6. `experiments/boundary/probe_m2_real_server.py`
   - `/proc` writer enumeration, `SIGKILL`, `boundary_closed`, `run_trial()`,
     `full_pipeline`, এবং separate escape-path reporting দেখাবেন।
   - বলবেন: “এই adapter unmodified third-party server-কে dedicated Linux UID
     দিয়ে চালায়। Trusted-store admission আর outside-world effect আলাদা verdict।”
7. `experiments/run_m2_real_server.py`
   - Docker preflight ও report schema দেখাবেন।
   - বলবেন: “Existing Docker Desktop/WSL2 Linux container-এ exact package
     version ও integrity verify করে run হয়েছে। Host secret/path mount হয়নি,
     runtime network disabled ছিল, এবং runner এখন honest case fail করলে
     non-zero exit দেয়।”
8. `paper/MANUSCRIPT_DRAFT.md` এবং `artifact/README.md`
   - বলবেন: “Paper-এ দুইটি evidence gate visible রাখা হয়েছে; artifact guide
     claim-to-command mapping এবং pending data-release requirements দেয়।”

### Laptop-এ live command চালানো নিরাপদ হলে

```bash
python -m pytest -q
python experiments/demo_theorem1.py
python scripts/verify_refs.py
python scripts/submission_check.py
```

Expected explanation:

- tests pass করা local implementation evidence;
- theorem demo response-only blind spot দেখায়;
- reference verifier unverified citation manuscript-এ ঢুকতে দেয় না;
- submission checker-এর non-zero exit এখন failure নয়—open gates থাকা অবস্থায়
  নিজেকে submission-ready ঘোষণা না করার guardrail।

Docker result দেখাতে `artifact/results/integrated_real_server.json` খুলবেন।
বলবেন: “Honest exact write COMMITTED; path/content substitution trusted store
থেকে refused। কিন্তু path diversion `/tmp`-তে landed—তাই এটি admission,
world-effect rollback নয়।”

## 3. সবচেয়ে সম্ভাব্য technical প্রশ্ন ও defensible উত্তর

### Q1. Problemটা কী? MCP তো schema validate করে।

Schema request/response-এর shape validate করে; implementation আসলে কোন path বা
কোন bytes লিখেছে তা independently observe করে না। Server যদি approved response
ফিরিয়ে অন্য effect করে, response schema valid-ই থাকতে পারে। Evidence:
`paper/MANUSCRIPT_DRAFT.md` §§1–3, `experiments/demo_theorem1.py`।

### Q2. Theorem 1 কি নতুন cryptographic theorem?

না। এটি transcript indistinguishability-এর এই setting-এ application। দুই world
যদি client-কে identical observation দেয়, observation-only decision procedure
দুই world আলাদা করতে পারে না। Novelty proof technique-এ নয়; MCP effect-integrity
problem-কে formal boundary, ecosystem measurement, এবং mediator design-এর সঙ্গে
জোড়া লাগানোতে। “Entirely novel theorem” বলা যাবে না।

### Q3. Detection probability false-positive rate-এর সমান কেন?

Monitor honest এবং malicious world-এ একই input distribution পায়। তাই যেই rate-এ
honest transcript-কে malicious বলবে—সেটাই false-positive rate—একই rate-এ
malicious-but-identical transcript-কে malicious বলবে। Extra independent effect
observation যোগ হলে theorem-এর premise আর সত্য থাকে না।

### Q4. MBA কী, এবং কেন final defense নয়?

MBA = Metamorphic Behavioral Auditing। Server-এর declaration থেকে write→read,
conservation, enumeration-এর মতো relation derive করে authorized extra calls দিয়ে
consistency check করে। এটি passive response-only অবস্থান থেকে বের হয়, কিন্তু
malicious server audit-aware shadow state রাখলে consistent lie করতে পারে। Real
measurement-এ usable TPR/FPR operating point পাওয়া যায়নি। তাই MBA এখন measured
failed approach/cost-ladder illustration; final guarantee নয়। Evidence:
`docs/11-runtime-validation-design.md`, `docs/18-evaluation-findings.md`,
`results/tables/operating_points.md`।

### Q5. 8,692 থেকে 1,242 কেন? এটা selection bias নয়?

হ্যাঁ, selection effect আছে। 8,692 credential-free registry candidate-এর মধ্যে
4,121 launch করে `tools/list` দিয়েছে; 1,242-এর usable paired write trial হয়েছে।
তাই result credentialed/high-value ecosystem-এর prevalence নয় এবং analysed set
favourable tail। Funnel drop প্রতিটি report করতে হবে। Evidence:
`results/tables/funnel.md`, manuscript §9।

### Q6. “No detector worked” কি ঠিক?

অতিরঞ্জিত। সঠিক claim: কোনো tested configuration pre-defined usable detection /
false-positive operating point পায়নি। Permissive configuration কিছু attack
detect করেছে, কিন্তু honest FPR প্রায় 72–78%; strict configuration 0–0.5/0%
detection range-এ ছিল। Exact denominator/version table থেকেই বলতে হবে।

### Q7. EffectContract কী?

একটি recursively immutable per-call authorization object: approved operation,
exact/bounded/free fields, maximum invocation count, এবং type-tagged canonical
identity। Current integrated
filesystem case path ও exact content bind করে। এটা user intent সত্য কি না prove
করে না; trusted approved input ধরে। Evidence: `src/mcpgate/contract.py`।

### Q8. L1/L2/L3 কী?

- L1 destination/path identity bind করে।
- L2 structure/well-formedness যোগ করে।
- L3 exact bytes বা approved hash যোগ করে।

L3-ও outside network/process effect আটকায় না। আর current reusable mediator শুধু
single-file exact-content L3 implement করে; তিন rung-ই production mode হিসেবে
implemented—এ claim করা যাবে না।

### Q9. Exact bytes client জানলে server-কে call করব কেন? Trusted writer-ই তো যথেষ্ট।

এটি সবচেয়ে শক্ত objection, এবং objectionটি সঠিক। যদি পুরো output আগে থেকেই
জানা এবং একমাত্র কাজ single write হয়, trusted direct writer সহজ ও ছোট TCB।
Current exact-write mechanism security invariants test করার prototype। Strong
paper-এর জন্য এমন non-trivial workload দরকার যেখানে unmodified server useful
computation করে, কিন্তু final admissible projection independently check করা যায়;
না হলে paper-কে narrow exact-write admission result হিসেবে direct-writer baseline
সহ উপস্থাপন করতে হবে। Evidence: manuscript §4.2, roadmap P0 gate।

### Q10. এটা sandbox/permissions থেকে আলাদা কীভাবে?

Permission বলে কে কোথায় লিখতে পারে; permitted path-এ কী bytes লেখা যাবে তা বলে
না। তাই static least privilege allowed file-এ content substitution structurally
blind। MCPGate complete staged effect-কে semantic contract-এর সঙ্গে compare করে।
তবে broad resource confinement AgentBound/container-এর territory; MCPGate তার
replacement claim করে না।

### Q11. Alcatraz/TxOS already staging and commit করেছে—novelty কোথায়?

Staging/commit নতুন নয় এবং paper সেটা claim করে না। Proposed delta হলো MCP
declaration/request-bound per-call contract, exact request shape, atomic allowance,
quiesced unmodified server execution, complete-tree diff, same-read promotion,
এবং protocol-specific expressibility/adaptive evaluation। এই composition যথেষ্ট
novel কিনা final breadth/utility evaluation-এর ওপর নির্ভর করবে।

### Q12. AgentBound থাকলে MCPGate কেন?

AgentBound broad filesystem/network/process resource boundary দেয়। কিন্তু allowed
writable endpoint-এর মধ্যে malicious parameter/content misuse semantic gap থেকে
যায়। MCPGate-এর narrow target সেই allowed-path content admission। Best design
দুই layer combine করতে পারে: AgentBound-style outer confinement + MCPGate-style
inner contract diff। Head-to-head superiority claim করা যাবে না।

### Q13. Writer boundary close করা কেন দরকার?

MCP response বা stdio close মানে child/background writer শেষ—এমন নয়। Snapshot-এর
সময় writer alive থাকলে tree race করতে পারে। তাই trusted adapter explicit
`boundary_closed=True` attest না করলে mediator commit করে না। Docker adapter
dedicated UID-এর processes `/proc` থেকে terminate/verify করে; production-এ
per-invocation cgroup/PID/mount namespace ভালো।

### Q14. Same-read commit কোন TOCTOU বন্ধ করে?

Old design validation-এর জন্য একবার পড়ত, commit-এর সময় আবার পড়ত। মাঝখানে bytes
বদলে 5/20 tested trial-এ attacker জিতেছে। Fixed design materialized snapshot-এর
same in-memory bytes commit করে; second staging read নেই, tested attack 0/20। এটা
সব filesystem race-এর proof নয়—snapshot traversal race-free হওয়া writer closure
ও validator assumptions-এর ওপর নির্ভর করে।

### Q15. AllowanceLedger কেন শুধু counter নয়?

`remaining > 0` check এবং পরে decrement আলাদা হলে concurrent দুই call একই final
slot নিতে পারে। `reserve()` atomic state transition করে এবং `(contract_id,
request_id)` idempotency রাখে। Same ID prior result ফেরত দেয়; new ID exhaustion-এ
refuse হয়। Default backend in-memory; release path-এ SQLite WAL + FULL-sync
backend reservation execution-এর আগে persist করে। Restart হলেও orphaned slot
আবার দেওয়া হয় না। তবে crash-এর আগে outside-world effect হয়েছিল কি না ledger
জানে না, তাই UNKNOWN reconcile না করে exactly-once world-effect claim করি না।

### Q16. Hidden extra field effect diff-এ ধরা পড়ে না কেন?

একটি unauthorized request field filesystem output না বদলালেও অন্য side effect
trigger করতে পারে। তাই staging diff একা যথেষ্ট নয়। Preflight exact-key check এবং
post-transport recheck দুটোই দরকার। Preflight refusal allowance consume করে না;
transport rewrite execution শুরু হওয়ার পরে ধরা পড়লে slot spent/FAILED থাকে।

### Q17. Symlink, hardlink, extra file, traversal কীভাবে handle হয়?

Logical path absolute/traversal/backslash escape হলে execution-এর আগেই refusal।
Materializer complete tree walk করে expected directory/file ছাড়া extra object,
symlink, multi-link inode, বা special file reject করে। Extra file-এর potentially
huge content trusted memory-তে পড়ে না; কেবল approved file expected size bound-এ
একবার পড়া হয়। তারপর validated in-memory bytes temporary file+`fsync`+atomic
replace দিয়ে trusted store-এ যায়। Evidence:
`src/mcpgate/mediator.py`, adversarial tests।

### Q18. `/tmp/exfil.dat` লেখা গেলে defense fail নয়?

World-effect prevention হিসেবে হ্যাঁ; trusted-state admission হিসেবে না। Current
claim শুধু mismatching result trusted committed store-এ promote হয়নি। Historical
trial external escape সত্যিই ঘটিয়েছে, তাই “all malicious effects prevented” claim
retired। Full prevention-এর জন্য outer namespace/mount/network confinement দরকার।

### Q19. UNKNOWN আর FAIL আলাদা কেন?

FAIL মানে observed evidence contract mismatch/refusal দেখিয়েছে। UNKNOWN মানে
reliable final state establish করা যায়নি—যেমন stable writer boundary নেই, silent
no-op/ambiguous timeout। UNKNOWN-কে blocked attack বা successful attack হিসেবে
গোনা দুটোই ভুল। Attempted, protocol error, authorized effect, unauthorized
effect, outcome-known আলাদা fields রাখা instrumentation lesson।

### Q20. Current result submission-ready?

না। Code এবং manuscript substantial হলেও submission checker intentional non-zero
কারণ integrated Docker rerun, independent Round-2 annotation, ≥10 frozen held-out
servers, auditor/plain-policy baselines, real overlapping-process evaluation,
ablation, dependency/artifact pinning, এবং non-trivial utility case বাকি। “Ready
for final update presentation” বলা যায়; “top-tier submission-ready” বলা যাবে না।

### Q21. Network layer-এ একই attack কীভাবে prevent করার চেষ্টা করবেন?

Network send filesystem write-এর মতো পাঠানোর পরে rollback করা যায় না। তাই
server-কে direct socket/egress না দিয়ে invocation-private network namespace-এ
রাখব। শুধু trusted broker egress পাবে। Broker send-এর আগে contract-এর host,
resolved address, port, method, path/query, sensitive headers, exact body/hash,
redirect policy এবং request allowance মিলাবে। DNS rebinding, redirect,
CONNECT/raw socket, UDP/QUIC, extra connection ও replay frozen attack হবে। MCP
response নয়; broker log/packet observation হবে effect oracle। HTTPS CONNECT
payload দেখা না গেলে কেবল destination-level claim করা যাবে—full HTTP claim নয়।

### Q22. SQL/database effect কীভাবে pipeline-এ আনবেন?

প্রথম target SQLite। Untrusted server trusted database-এ সরাসরি লিখবে না;
invocation-private database copy বা controlled transaction-এ লিখবে। Writer
closure-এর পরে trusted component schema, table, row, column এবং exact value
before/after diff করবে। Contract-এর delta মিললে same verified database state
promote/commit হবে; extra row/table/schema/trigger change হলে discard/rollback।
PostgreSQL আলাদা claim, কারণ second connection, triggers, procedures,
extensions এবং external side effects transaction-এর বাইরেও যেতে পারে।

### Q23. তাহলে network ও SQL কি current contribution?

না। Current RQ1--RQ5 এবং evaluated contribution filesystem admission-এ frozen।
Network RQ6 ও SQL RQ7 এখন pre-registered Phase-2 plan। Integrated code, frozen
attacks, independent oracle, held-out workloads, baselines, 100-trial races,
confidence intervals এবং clean Linux artifact pass না করা পর্যন্ত এগুলোকে
“we plan/are investigating” বলব, “we prevent” বলব না। Full plan:
`paper/NETWORK_SQL_EXTENSION_PLAN.md`।

## 4. Terms — concise but technically correct

| Term | Presentation-ready meaning |
|---|---|
| Transcript | Client-visible sequence of requests and server responses |
| Indistinguishability | দুই world observer-কে একই distribution-এর evidence দেয় |
| TPR / detection rate | বাস্তব malicious case-এর কত অংশ detector ধরেছে |
| FPR | honest case-এর কত অংশ ভুলভাবে malicious বলেছে |
| Effect oracle | Server response থেকে independent ground-truth observation of what changed |
| Staging | Untrusted invocation-এর private temporary workspace |
| Trusted store | Server যেটি সরাসরি লিখতে পারে না; mediator-approved result-এর destination |
| Admission | Trusted state-এ result ঢুকতে দেওয়া; past external effects rollback নয় |
| Quiescence / writer closure | Snapshot-এর আগে আর কোনো authorized writer চলমান নেই |
| TOCTOU | Check-এর সময়ের state এবং use/commit-এর সময়ের state বদলে যাওয়া |
| Atomic reservation | Competing calls-এর মধ্যে এক indivisible state transition-এ slot নেওয়া |
| Idempotent replay | Same request ID আবার এলে re-execute না করে stored result ফেরানো |
| Fail closed | Unrecognized/ambiguous input-এ allow না করে refuse/UNKNOWN করা |
| Complete-tree diff | Expected file ছাড়াও extra directories/files/object types পরীক্ষা করা |
| TCB | যে components সঠিক ধরে security argument দাঁড়ায়: mediator, adapter, OS boundary |
| Held-out set | Design/fix করার সময় দেখা হয়নি—আগে freeze করা independent evaluation targets |
| Ablation | একটি mechanism property সরিয়ে কোন failure ফেরে তা মাপা |
| Qualified claim | Result আছে, কিন্তু limitation একই সঙ্গে না বললে claim misleading |

## 5. যেসব বাক্য বলা যাবে না

- “MCPGate সব external attack prevent করে।”
- “Theorem 1 সম্পূর্ণ নতুন cryptographic theorem।”
- “69.7% tool provably unauditable।” Round-2 validation pending।
- “Docker run সব external effect আটকেছে।” Integrated run trusted-store gate
  pass করেছে, কিন্তু path diversion `/tmp/exfil.dat`-এ সত্যিই landed।
- “Seven servers prove ecosystem-wide generality।” Development-selected and
  below the frozen ≥10 target।
- “TOCTOU solved।” কেবল observed two-read race closed।
- “Exactly-once world effect guaranteed।” Durable ledger restart replay বন্ধ
  করে, কিন্তু orphaned RESERVED outcome-এর external effect নিজে reconcile করতে
  পারে না।
- “L1/L2/L3 সব implemented enforcement mode।” Current integrated mediator
  exact single-file L3 only।
- “This outperforms AgentBound/SAFEFLOW/Progent।” No reproducible head-to-head
  evidence।
- “Docker না থাকায় live test দরকার নেই।” বরং বলবেন isolated host-এ evidence
  gate pending এবং local laptop-এ unsafe shortcut নেওয়া হয়নি।

## 6. Closing answer

Sir যদি বলেন “So what is your honest contribution today?”, বলবেন:

> “আমাদের strongest contribution universal sandbox নয়। প্রথমে আমরা formal এবং
> empiricalভাবে দেখিয়েছি server-authored response effect-এর independent proof
> নয়। তারপর locally executed filesystem tool-এর জন্য request, allowance, staged
> effect, writer boundary, এবং committed bytes-কে এক per-invocation chain-এ bind
> করেছি। Adaptive testing আমাদের নিজের TOCTOU ও replay bug ধরেছে, এবং external
> escape ও timing ambiguity-কে limitation হিসেবে রেখেছে। Final paper strong করতে
> এখন breadth, reproducibility, এবং non-trivial utility gate close করছি।”

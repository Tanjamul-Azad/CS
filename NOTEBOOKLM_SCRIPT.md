# EffectSeal — current narration and defense script

Updated 2026-10-09 after the correctness audit. Use this version for NotebookLM.
The earlier long discovery narrative is preserved under `paper/history/`.
Numbers and qualifications follow `paper/CLAIM_EVIDENCE_MATRIX.md` and the
explicit pointers in `artifact/paper-evidence-20261009.json`.

An agent approves an MCP call, but the implementation determines what happens.
The tool can return an honest-looking reply while changing a file, sending an
extra email recipient, or making another API request. The Postmark incident
makes the gap concrete: a package update added a Bcc recipient without changing
the approved call. Our figure reconstructs that mechanism; it does not claim
we captured the incident's historical transcript.

The observation boundary is simple: if two executions have exactly the same
client-visible transcript, a passive monitor gets the same information. That
is an application of indistinguishability, not a new proof technique. The
registry response auditor failed its frozen operating point on 1,242 usable
paired trials, from 8,692 candidates and 4,121 launches. This is a selected
credential-free corpus, not a prevalence estimate for all MCP servers.
Four judges show no observed advantage after matching approved requests and
normalized signatures. Those post hoc matches do not prove raw equality.

EffectSeal adds a trusted effect boundary. A local server runs in a confined
private copy; after writers stop, the mediator checks the staged result and
promotes the checked bytes. The generalized tree adapter freezes and renames
a stable tree instead of materializing every object in memory. Network servers
can exit only through a broker. It checks typed request structure and values,
durably reserves the approved call, and adds its real credential only after
admission. A sent prefix cannot be undone. A later refusal is partial; a send
whose outcome cannot be known is UNKNOWN and stays spent after restart.

New calls have no same-call honest reference. Pin-time templates learn how
arguments become effects, using perturbations, transformations, clock windows
and a bounded anti-unification heuristic. The heuristic is not guaranteed to
find a least general generalization. Slack is a capacity bound over the checked
canonical view. Unicode alphabets and trusted clock windows must match the
actual matcher. Raw excluded ZIP metadata and transport serialization are not
covered by that bound.

The results must be spoken with their denominators. Honest-run local contracts
stopped 32/32 landed development attacks. Local templates stopped 75/75
development and 39/39 held-out attacks, while blocking 1/84 and 6/48 honest
calls. The held-out 12.5% false-block rate failed the predeclared 5% criterion.
The later eligible local batch yielded no scored server, so it does not validate
the repairs on a new local population.

Original network templates covered 10/12 selected servers. On the covered ten,
120/120 honest mock protocol trials were admitted. Fixed unauthorized-send
variants were refused in 792/816 cases; 120 silent no-ops are separate completion
failures. Development refused 480/504 and covered held-out servers 312/312.
These are transformations of captured requests, not rebuilt malicious servers
for every package. Every-leaf adaptive testing refused 612/648: 24 splitifi
and 12 held-out travel variants were admitted. The zero-admission criterion
failed. Whole-server bootstrap uncertainty accompanies the rates.

A frozen additional selection screened 40 unused candidates, found five rather
than its target six, and kept every screening failure. It admitted 60/60 honest
protocol trials and refused 312/312 fixed send variants. Adaptive refusal was
324/336, with all 12 admissions on conekta. Two tools had no JSON string-leaf
variants. Empty-payload API-key creation and a directory tool's telemetry POST
are included, and two packages share an author. This is useful additional
coverage, not five independently verified vendor task successes.

Rebuilt Postmark attack versions exercise the whole send path: EffectSeal
refused 21/21 unauthorized sends and detected three no-ops as incomplete.
Actual ToolHive and AgentBound runs each refused 3/21 sends, those to another
host. Declaration pinning alerted on 0/8 attack versions; its declaration-change
control did alert. Version alerts and request prevention are different units.
Official GitHub checks refused 84/84 fixed sends and 24/24 adaptive variants.
Historical model-agent experiments remain dated, narrow results, not new API
runs after this repair. Postmark provider validation is a separately dated
public test-token replay that delivered no email.

The actual proxy, with two workers and eight contenders, sent exactly one
request in every one of 100 races. Restart replay returned 403. Quiet loopback
timing over 300 samples had gate p50/p95 14.5/33.6ms against record-only
1.7/20.9ms. This includes state reads, instantiation, SQLite and logs, but
excludes TLS and WAN/vendor latency. It is a development-machine measurement.

Repeated pinning is not an honesty oracle: honest sessions agreed, session
noise disagreed, and stable Bcc poisoning agreed even though its effects were
unfaithful. A trusted pinned version and a sufficiently tight contract remain
necessary. Call authorization handles harmful intent before execution;
effect admission constrains what the implementation admits afterward.

For a demonstration, open the current claim matrix, run
`python scripts/verify_current_evidence.py`, then show the typed collision and
actual-proxy regressions in `tests/test_network_repairs.py`. Show raw bundles
before discussing aggregate percentages. Fresh Linux logs identify the exact
source commit and failed-step exit behavior. The public repo omits the private
manuscript; its current build script and hash manifest bind the PDF to local
source. The working paper still needs an anonymous artifact URL and author
review before submission. Do not predict acceptance odds from these results.

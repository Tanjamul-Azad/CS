# THE EXPERIMENT — Reader Calibration, and the Safety/Detectability Frontier

Written 2026-09-10. **This supersedes the framing in [`23-frozen-direction-auditability-analyzer.md`](23-frozen-direction-auditability-analyzer.md).** Doc 23's system (analyzer → plan → verdict) survives unchanged as the *vehicle*. What changes is the scientific claim it carries, because two measurements run on 2026-09-08/10 found something neither doc 21, 22 nor 23 knew.

Doc 22 said: *0% detection, and we cannot tell whether that is the ecosystem or our detector.* We now know. **It is neither.** The evidence was there the whole time and our decision rule was throwing it away.

---

## 1. The measurement that changes the paper

Our detector offers exactly two operating points on the real corpus, and **both are unusable**:

| Operating point | True detections | False-positive rate |
|---|---|---|
| Count only `VIOLATION` (what we shipped) | **0 / 205** = 0.0% | 1.8% |
| Count `WARNING` too | **5 / 205** = 2.4% | **76.5%** |

The 5 are real. Not artifacts — read them:

```
write_file  → read_file  reports the target of this write does not exist,
              yet the response claimed success          [path diverted]

create      → view       reports the target of this write does not exist,
              yet the response claimed success          [path diverted]

add_source  → list_sources shows url in ['/tmp/exfil.dat'], none match
                                                        [url diverted]
```

That third one is the attack visible in the clear: the exfiltration path is sitting in the reader's own output. **We detected it and then discarded the detection**, because the write/reader pairing was noun-tier and our own false-positive control demotes noun-tier findings to warnings that do not count.

So the honest diagnosis is not "the ecosystem is unverifiable" and not "our detector is broken." It is:

> **The discriminating evidence is present, and the client has no way to tell it apart from noise. 5 true positives are buried in 166 false positives, and every threshold we can set either keeps both or discards both.**

That is a far more interesting problem than the one we thought we had, and it is a *solvable* one.

---

## 2. Why the client cannot tell them apart

A reader that says nothing about the write is ambiguous between two worlds:

- **Diverted.** The write went somewhere else; the reader truthfully reports the intended target is untouched.
- **Benign.** This reader never reflects writes at all — wrong resource, different index, paginated, eventually consistent, or simply unrelated.

Nothing in the response distinguishes them, because in both worlds the reader's answer is *the same and truthful*. The client is not being lied to. **It is reading an instrument it never checked.**

Every fix we tried over four repair rounds — better pairing, keyed identifiers, structured comparison — tried to improve *which* reader to ask and *how* to compare the answer. None of them established the prior question: **does this reader observe writes at all?**

---

## 3. The mechanism: reader calibration

Before treating a reader's silence as evidence, establish that the reader can speak.

```
1. CALIBRATE   issue a controlled probe write with a known canary value
               to a target the auditor owns
2. OBSERVE     call the candidate reader
3. CLASSIFY    canary visible   → reader is VALID: its silence is evidence
               canary invisible → reader is BLIND: its silence means nothing
4. AUDIT       only a VALID reader's non-corroboration counts as a detection
```

This converts an ambiguous signal into a two-source one. A blind reader is *excluded before it can generate a false positive*, rather than being demoted afterwards by a heuristic strength tier that also throws away the true positives.

**Prediction (to be tested, not assumed):** most of the 166 false positives come from blind readers and will be removed by calibration, while the 5 true positives come from valid readers and will survive. If that holds, the detector moves to an operating point neither of the current two dominates.

**HYPOTHESIS — NOT A RESULT.** It is entirely possible that the true positives also come from readers that fail calibration, in which case calibration removes everything and the answer is that this class of auditing is finished. That outcome is publishable too, and it is decided by E-CAL below, not by argument.

---

## 4. The tension that makes this worth a paper

**Calibration requires a write.** And the project's central safety rule ([`src/mcpaudit/auditor.py`](../src/mcpaudit/auditor.py), lines 19–31) is:

> *the auditor NEVER issues a write the agent did not ask for.*

That rule is why the tool is deployable against production systems. It is also, we now believe, precisely why it is blind. The constraint that makes a client-side auditor safe to run is the same constraint that denies it the calibration it needs to interpret what it sees.

The codebase already *states* this tradeoff — "This costs coverage" — and has an `allow_probe_writes` flag that has never been switched on in any experiment. **Nobody has ever measured what it costs.** That is the gap, and it is ours to close:

> **RQ: What is the frontier between the write authority granted to a client-side auditor and the effect-diversion it can detect?**

This is not a detector paper and not a measurement paper. It is a **mechanism + a frontier**: we give the client a way to validate its own observation channel, and we price it in the currency that actually matters to a deployer — how much mutation authority they must hand the auditor.

---

## 5. Structural prediction — measured, and the partition already exists

Verification of a key-addressed write can escape the ambiguity above through exactly three channels. We classified all 1,216 servers that answered:

| Escape channel | What it needs | Servers | Share |
|---|---|---|---|
| **ENUM** — enumeration | a list-shaped reader taking no key: a diverted target appears, or the intended one is absent | 558 | 45.9% |
| **SNAP** — keyed snapshot | a reader addressable by the same identifier the write accepts | 331 | 27.2% |
| **CONS** — conservation | a numeric quantity a write moves and a reader reports | 45 | 3.7% |
| **NONE** — none of the above | — | **308** | **25.3%** |
| *any escape available* | | *908* | *74.7%* |

*(Overlapping; percentages are of the 1,216. `ENUM` 558 and `ENUM+SNAP` 258 are counted in their respective rows above. Source: `experiments/run_resource_sweep.py` output + `data/processed/resource_sweep.json`.)*

**This immediately explains the 0%.** Our auditor implements the SNAP escape well and the ENUM escape only accidentally — as an untyped substring search whose findings land in the noun-tier bucket and get discarded. **45.9% of real servers offer only the escape we never implemented.** We built the wrong detector for the ecosystem we have.

It also yields a falsifiable structural prediction:

> **Detection rate should track escape availability.** High in SNAP and ENUM, near-zero in NONE, at a fixed FPR. If detection is flat across the partition, the structural theory is wrong and we report that.

`NONE` at 25.3% is where our classifier finds no supported check — **not a proof that none exists.** The partition is itself a heuristic, and §5.1 records a case where a real detection landed in the `NONE` bucket, so its recall is known to be imperfect and unmeasured. State it as *"no check derivable by our relation vocabulary"*, never as a structural impossibility.

### 5.1 Escape typing alone does NOT separate signal from noise — tested 2026-09-10

The cheap version of this paper would be: skip calibration, just filter findings by escape channel. **That shortcut is empirically dead.** Cross-tabulating the 5 suppressed true positives and the 170 false positives against the partition:

| Group | True positives | False positives |
|---|---|---|
| ENUM | 4 / 5 = **80%** | 80 / 170 = **47.1%** |
| NONE | 1 / 5 = 20% | 39 / 170 = 22.9% |
| ENUM+SNAP | 0 | 31 / 170 = 18.2% |
| others | 0 | 20 / 170 = 11.8% |

ENUM contains most of the true positives *and* nearly half the false ones. **Escape typing is necessary but not sufficient**: it tells you a check is theoretically possible, not whether the particular reader you picked works. Calibration, not the taxonomy, has to do the discriminating work.

Two consequences, both good:

1. **The week is de-risked in the right direction.** We excluded the cheap alternative in an hour instead of discovering on Day 6 that filtering by structure does nothing.
2. **The taxonomy is demoted to a supporting measurement**, not the mechanism. §7's E-STRUCT still runs — the structural floor at 25.3% is a real ecosystem result — but the paper's load-bearing claim is calibration.

One true positive (`io.github.domdomegg/filesystem-mcp`, `create` → `view`) sits in `NONE`, meaning the escape classifier missed a genuine verification path — its reader `view` is neither list-shaped nor identifier-keyed under the current vocabulary. **Escape-classifier recall is a known limitation and must be reported as one**; do not present the partition as ground truth. E2's shrunken hand audit (§7) exists to bound exactly this error.

---

## 6. Second measurement: the resource channel does not rescue this

E0 swept `resources/list` and `resources/templates/list` across all 1,242 launchable servers (`experiments/run_resource_sweep.py`, 1,216 answered):

| | Servers | Share |
|---|---|---|
| Resource channel present | 264 | 21.7% |
| Answered, genuinely empty | 346 | 28.5% |
| Capability unsupported (`Method not found`) | 606 | 49.8% |
| **Publishing URI *templates*** | **0** | **0.0%** |

**Not one server out of 1,216 publishes a parameterised URI template.** Static resources are fixed addresses (`config://settings`); they cannot be pointed at the specific record a write just touched. The resource channel therefore adds observation surface but almost no *addressable* verification: an upper bound of 26 servers (18.2% of the 143 with no read-shaped tool at all) could have their A0 label corrected.

This closes the objection cleanly and with evidence: **our tools-channel-only measurement was not materially wrong, and we can now say so instead of conceding it.** It is a small negative result that protects the headline.

---

## 7. Experiments

| ID | Experiment | Question | n | Priority | Status |
|---|---|---|---|---|---|
| **E-BASE** | Both operating points of the current detector | How unusable is the status quo, exactly? | 205 landed | MUST | **data in hand** |
| **E-CAL** | Calibrated auditor: detection & FPR | Does calibration separate the 5 from the 166? | ~900 | **MUST** | not started |
| **E-STRUCT** | Detection by escape channel, predicted vs observed | Does detectability track structure? | 1,216 partitioned | **MUST** | partition done |
| **E-ENUM** | Implement enumeration-diff as a first-class check | Does the escape 45.9% of servers actually have work? | 558 | **MUST** | not started |
| **E-SAFE** | Which write tools admit a *safe* calibration probe | What does calibration cost in real risk? | 1,216 | MUST | not started |
| **E-FRONT** | Detection vs granted write authority | **The frontier figure.** | ~900 | **MUST** | not started |
| **E-ABL** | Ablate calibration / escape-typing / snapshot | Which component earns the improvement? | subset | SHOULD | not started |
| **E-DEMO** | End-to-end on one named real registry server | Show it working | 1 | MUST | not started |

Superseded from doc 22/23: E1 (κ) drops to SHOULD — the A0 headline is no longer the paper's spine, so an unvalidated classifier is no longer fatal. E2's hand audit shrinks to validating the escape partition on ~30 servers rather than establishing ground truth from scratch. E4's full re-run happens once, as E-CAL.

### The safety ladder for E-FRONT

The frontier's x-axis. Each rung grants strictly more authority:

- **L0 — read-only.** No probe writes. *This is the shipped configuration and scores 0%.*
- **L1 — idempotent probes.** Only tools whose own `idempotentHint` is true.
- **L2 — owned-namespace probes.** Writes confined to a target the auditor created (`probe-<uuid>`), never a user resource.
- **L3 — reversible probes.** Any write with a discoverable inverse (`create`/`delete` pairs).
- **L4 — unrestricted.** Upper bound; not a deployment recommendation.

Detection at each rung, at fixed FPR, is the paper's central figure. **The shape of that curve is the result**, whatever it turns out to be. A curve that stays flat says calibration does not help and client-side auditing is over — still a finding, and a strong one.

---

## 8. Honest positioning

**What is genuinely ours** -- after the novelty gate in [`26-m1-novelty-gate.md`](26-m1-novelty-gate.md), which removed more than this section originally claimed: the escape-channel taxonomy with an ecosystem-scale measurement behind it, the effect oracle, and the safety/detectability frontier. Reader calibration is a mechanism, and mechanism claims in this space did not survive the gate -- present it as an instrument that made the measurement possible, not as a novel defense.

**What is not.** The underlying principle — that verifying an untrusted store requires either client-side state or an independent channel — is old, and lives in memory checking and authenticated data structures. **Do not claim an impossibility result as new.** Our contribution is the instantiation, the measurement, and the price. Cite the lineage in [`12-intellectual-lineage.md`](12-intellectual-lineage.md) and add memory checking to it.

**The claim discipline in [`23`](23-frozen-direction-auditability-analyzer.md) §5 and the citation quarantine still stand in full.**

---

## 9. What this looks like in front of the professor

> We proposed a client-side defense against MCP servers that lie about what they did. Our own benchmark said it worked. Against 1,242 real third-party servers it detected nothing — and it kept detecting nothing through four rounds of repair, at a stable 1.8% false-positive rate.
>
> So we asked what the detector was actually seeing. It turns out it had found real attacks — including one where the exfiltration path was sitting in plain sight in the reader's own output — and had thrown them away, because the only rule available for suppressing 166 false alarms also suppressed the 5 true ones. The detector had exactly two settings: catch nothing, or cry wolf three times out of four.
>
> The reason is that a client reading an untrusted server has no way to know whether its own instrument works. A reader that says nothing might mean the write was diverted, or might mean that reader never reflects writes at all. So we built calibration: before trusting a reader's silence, prove the reader can speak, by writing a canary and checking it comes back.
>
> Calibration requires a write — and the safety rule that makes this tool deployable forbids exactly that. So the result is not a detector. It is a frontier: here is how much detection you buy for each increment of write authority you grant, measured across nine hundred real servers, plus the 25% of the ecosystem where no amount of authority helps because the structure isn't there at all.

Problem → system → failure → **the failure was a measurement artifact we found by auditing ourselves** → mechanism → priced tradeoff. The self-audit is the strongest part and it should be told, not hidden.

---

## 10. Eight-day sequence (from 2026-09-10)

Critical path: **E-ENUM + calibration → E-CAL → E-FRONT.** Everything else can slip.

| Day | Build | Run | Analyse |
|---|---|---|---|
| **1** | Enumeration-diff as a typed check; escape-channel typing in the analyzer | — | E-BASE table from data in hand; freeze the partition |
| **2** | Reader calibration (canary probe + VALID/BLIND verdict); safety ladder L0–L4 | smoke on 20 servers | E-SAFE over declarations |
| **3** | Wire calibration into verdicts; `UNVERIFIABLE` reason codes | **E-CAL at L2** on the SNAP+ENUM set | first detection/FPR numbers |
| **4** | — | **E-FRONT**: sweep L0→L4 | the frontier curve |
| **5** | Fix whatever the curve exposes | E-STRUCT across the partition | predicted vs observed |
| **6** | CLI + report; demo on one named real server | E-ABL | figures, scripted from raw JSON |
| **7** | — | rehearse demo, both branches | claim–evidence matrix |
| **8** | Clean-clone reproduction | — | notebooks, presentation |

**Pre-registered decision rule, recorded before E-CAL runs:**

> **E-CAL succeeds** iff, at safety rung L2, detection ≥ 20% of landed attacks at FPR ≤ 10%, i.e. strictly dominating both current operating points (0%/1.8% and 2.4%/76.5%).
> **E-CAL fails** otherwise → the paper's result is the frontier's flatness plus the 25.3% structural floor, and client-side effect auditing is reported as closed.

Both branches are pre-committed. That is what makes either one reportable.

---

## 11. Risks

- **The 5 true positives may fail calibration too.** Then calibration removes everything. Test this *first*, on those 5 servers specifically, on Day 2 — before building the full sweep. It is a one-hour check that de-risks the entire week.
- **Probe writes against third-party servers.** Safe here: the Docker sandbox is ephemeral, `--rm`, capability-dropped, with one writable mount. But the deployment claim must be stated separately from the measurement, and L4 must never be described as a recommendation.
- **n shrinks fast under conditioning.** 205 landed attacks → partitioned by escape channel → conditioned on a valid reader. Report exact CIs and resist splitting further than the data supports.
- **Scope creep into the CLI.** The system is the vehicle. If a day goes to report formatting it came out of E-FRONT.

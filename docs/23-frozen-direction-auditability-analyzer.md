# FROZEN DIRECTION — Auditability Analyzer, Verification Contract, Runtime Evaluator

Written 2026-09-08. **This is the decision. It supersedes the direction in [`22-research-diagnosis-and-10-day-plan.md`](22-research-diagnosis-and-10-day-plan.md); doc 22's diagnosis, experiment matrix and risk analysis remain valid and are referenced rather than repeated.** Doc 22 said "pivot to measurement." This doc says the same science, packaged as a runnable system, and explains why the packaging is not cosmetic.

**Do not reopen the direction question.** It has been examined three times in one week ([`21`](21-real-server-results-and-options.md) §5, [`22`](22-research-diagnosis-and-10-day-plan.md) §3–4, and here). Reopening it again costs more than any remaining alternative gains.

---

## 1. The decision, in one paragraph

We keep the topic (MCP execution integrity), keep every asset, and **abandon the claim that our defense detects malicious MCP servers.** The evidence does not support it: 0 true detections across 1,242 third-party servers, unchanged after four rounds of instrument repair ([`22`](22-research-diagnosis-and-10-day-plan.md) §1). The deliverable becomes a working system —

```
MCP server
   ↓  discover        tools/list  +  resources/list  +  resources/templates/list
   ↓  classify        which effects admit a check, and via what
   ↓  plan            emit an executable verification plan
   ↓  execute         run the plan against the live server, under attack
   ↓  verdict         DETECTED | PASS | UNVERIFIABLE(reason)
```

— whose honest output on most of the ecosystem is `UNVERIFIABLE`, and whose contribution is that it says so mechanically, with a measured distribution behind it, plus a protocol extension that changes the answer.

**Title:** *The Behavioral Auditability Gap in MCP: Measuring the Limits of Client-Side Verification at Ecosystem Scale*

---

## 2. Why a system rather than a measurement paper — the real reason

Not "it demos better." The decisive property is this:

| Direction | If E3 succeeds | If E3 fails |
|---|---|---|
| Measurement-only paper | no demo | no demo |
| MBA-as-defense (old) | demo works | **demo dies** |
| **Analyzer + Contract** | demo works | **demo still works** |

If the positive control (E3, [`22`](22-research-diagnosis-and-10-day-plan.md) §6) shows the auditor firing on verified-checkable servers, the demo is the auditor catching a real diversion on a real third-party server. If E3 fails, the demo moves to the contract branch: **same real server, no contract → `UNVERIFIABLE`; with contract → `DETECTED`.** We author the contract, so that branch is under our control, and the scientific story is unchanged either way — *here is exactly what the protocol must add before this is checkable at all*.

This is the only direction on the table that is demo-safe in both branches. Given a fixed ten-day deadline and a professor who wants to see the research, that dominates every other consideration.

**This is a packaging change, not a fourth pivot.** Doc 22's RQ1/RQ2/RQ3 map onto the three system components exactly:

| Doc 22 | System component | Experiments |
|---|---|---|
| RQ1 — how much is verifiable | Discovery + Auditability Analyzer | E0, E1, E2 |
| RQ2 — can we exploit it when it exists | Verification-plan generation + Runtime Evaluator | E3, E6, E8 |
| RQ3 — what protocol evidence is needed | Verification Contract | E5 (split P0/P1/P2) |

Say it that way in the presentation. Three direction changes in a week would be a red flag; one repackaging of a settled diagnosis is not.

---

## 3. What is actually new (and what is already written)

Roughly 70–80% of the system exists. Nobody should plan ten days as though it is greenfield.

| Component | State | Work |
|---|---|---|
| Tool discovery | `LiveSession.list_tools` | done |
| **Resource discovery** | **added 2026-09-08** — `LiveSession.list_resources`, `docker/probe_resources.py`, `experiments/run_resource_sweep.py` | E0 running |
| Auditability classification | `measure/classify.py` — A0–A3, relation derivation | done; needs resource awareness |
| Verification-plan generation | exists but **in-memory only** — `Auditor.__init__` builds `_readers`, `_reader_strength`, `_quantities` and never emits them | **materialise as a serialisable artifact** |
| Plan execution | `_check_write_read`, `_check_conservation` | done |
| Attack runner | `mcpmut/proxy.py` — L1/L2/L3 | done |
| Verdict output | severity strings; `UNVERIFIABLE` is currently an `[INFO]` log line | **promote to a first-class verdict** |
| **Verification Contract** | **does not exist** | schema + inference + evaluation |
| **CLI + report** | **does not exist** | one command, one readable report |

**The four genuinely new pieces:** resource channel, plan-as-artifact, contract, CLI. Everything else is wiring what is already tested (111 tests passing).

**What this costs.** The system framing adds engineering on top of the science, and ten days does not stretch. Paying for it: E9 (audit cost) and E10 (incident corpus) drop to NICE; E7 (external defense) becomes conceptual with one run only if time remains; the LLM experiments stay parked as ancillary evidence. Accept this now, not on Day 7.

---

## 4. Three corrections that are not negotiable

### 4.1 The Verification Contract experiment must measure a gap, not validate our own answer key

If we hand-write contracts and then measure "does having a contract improve detection," the answer is yes by construction — we wrote the answer key. That is the four-domain benchmark mistake one level up ([`22`](22-research-diagnosis-and-10-day-plan.md) §2).

**Correct design.** Generate contracts *automatically* from declarations wherever possible. Have humans write them for the same servers as an oracle / upper bound. Then report:

> **inferable** (what a client can derive unaided) vs **specifiable** (what a human with the server in front of them can state)

**The gap between those two is the protocol's missing information, quantified.** That is the result. "Our contract works" is not.

### 4.2 The demo runs on a real third-party server

A `save_note` / `get_note` server we wrote is self-evaluation again. The pilot identified roughly 13–30 real registry servers with genuine keyed write→read structure. Pick one, name it on the slide, and say plainly that we did not write it.

### 4.3 `UNVERIFIABLE` is a verdict, not a log line

Currently emitted as `[INFO] no relation derivable; this call is unverifiable`. It is the system's most honest and most common output and it is presently the least visible thing it produces. Promote it:

```
DETECTED      relation violated under attack
PASS          relation held
UNVERIFIABLE  <reason>   no reader / no key mapping / reader unresolvable /
                         reader shares only a noun / diverted field is the scoping field
```

The reason codes are the paper's failure taxonomy. They already exist implicitly in the alert strings; make them enumerable so they can be counted in a table.

---

## 5. Claim discipline — wording that must change everywhere

| Do not write | Write instead |
|---|---|
| "69.7% of MCP tools cannot be audited client-side" | "69.7% admit no relation derivable by our current relation vocabulary over the tools channel" — and after E0, state the channel coverage explicitly |
| "A0 = undetectable at any budget" | "A0 = no check derivable by our measured relation model" |
| "Theorem 2" | "Cost Observation" — no theorem label without a statement, assumptions and proof |
| "first ecosystem-scale MCP security measurement" | "first measurement of *effect auditability* in the MCP ecosystem" — larger security censuses exist |
| "our defense detects malicious servers" | "our analyzer determines where detection is possible, and detects within that region" |
| Controlled 4-domain benchmark as evaluation | "cost-ladder illustration" / unit test — not evidence |
| Existing MCP defenses as baselines | orthogonality controls — they solve input integrity, not effect integrity |

### The gap statement, narrowed

The old gap ("nobody studies behavioral integrity") is no longer safe to assert. The defensible one:

> Existing behavioral-integrity and MCP runtime defenses inspect artifacts, declarations, policy, arguments and returned outputs. None establishes **when the external side effect of a remote, uncooperative MCP server is independently checkable by the client.**

Narrower, and it survives contact with adjacent work.

### CITATION QUARANTINE — read this before touching the literature review

Several recent works have been raised as relevant: a behavioral-integrity study over ~49,943 agent skills; ShieldMCP (runtime call/response validation); a Secure Tool Manifest proposal; PACT (argument-level provenance); a 31-server six-month MCP drift study; and the current MCP specification revision date.

**None of these has been verified against a primary source by anyone on this project.** `paper/references.bib` already carries 52 entries all marked `[U]` unverified. Specific-sounding figures do not make a citation checked.

> **Rule: no citation enters the gap statement, the related-work section, or any slide until someone has opened the venue page, DOI, or arXiv abstract and recorded the identifier.** If the new positioning rests on a paper that does not exist, the positioning collapses in front of the first reviewer who knows the field.

Assign this to one person. It is a few hours and it protects the paper's spine.

---

## 6. Zero-cooperation: an amendment, not a silent break

`docs/README.md` records an invariant: *"No defense may assume cooperation from any party. This constraint killed two earlier designs (see [`16`](16-design-history.md)); do not reintroduce it."*

The Verification Contract assumes server cooperation. This is a deliberate, dated amendment:

> **Amended 2026-09-08.** Zero cooperation was adopted as a design constraint because a defense that needs the audited party's help is not a defense. Four rounds of measurement establish that zero-cooperation effect auditing has a ceiling on the real ecosystem. The constraint therefore becomes a *measured boundary* rather than a design rule: we report what zero cooperation achieves (RQ1, RQ2), and separately what minimal cooperation would add (RQ3). Contract-based results must never be reported as zero-cooperation results, and the threat model for RQ3 must state explicitly that a lying server can publish a false contract — the contract buys *auditability*, not *honesty*.

That last sentence matters. A malicious server can declare a contract pointing at a verifier it also controls. What the contract removes is *ambiguity about what to check*, not the adversary's ability to forge the check's input. Say so before a reviewer does.

---

## 7. Pre-registered decision rule for E3 — write the number before you see it

Doc 22 promised "either outcome is publishable." That is only true if the outcome is defined in advance. Otherwise the team rationalises whatever Day 4 produces.

**Pre-registration, fixed before E3 runs:**

- **E3 SUCCEEDS** iff, on the verified-checkable group: detection ≥ **50%** of landed attacks, at FPR ≤ **5%** on the honest trial, **and** the detection difference against the verified-uncheckable group is significant at p < 0.05 (Fisher's exact, one-sided).
- **E3 FAILS** otherwise.
- **On failure, MBA-as-defense is finished.** No fifth repair round. The paper's centre becomes protocol necessity, and the primary artifact becomes the Auditability Contract plus its linter.

Record the rule, with a timestamp, before the run. Both branches were pre-committed; that is what makes the negative branch publishable rather than an excuse.

### Sampling correction for E2

Doc 22 specified 40 randomly sampled servers. Split three ways (verified-checkable / tool-only-uncheckable / resource-observable) that is ~13 per cell, and the cell carrying the entire paper is the smallest. **Do not sample randomly.** Screen the 1,242 automatically for candidate structure, then hand-verify until the **verified-checkable cell holds 25–30 servers**; draw the comparison group randomly from the rest. Power belongs where the claim is.

---

## 8. Experiment set — canonical numbering

Doc 22's E1–E10 stay canonical. E0 is new; E5 splits into three interventions. Any other numbering in circulation is superseded.

| ID | Experiment | Maps to | Priority | Status |
|---|---|---|---|---|
| **E0** | Resource-channel sweep over the 1,242 launchable servers | RQ1 | **MUST** | **running 2026-09-08** |
| **E1** | Human validation of the A0–A3 classifier (κ) | RQ1 | **MUST** | not started |
| **E2** | Hand-audited verifiability ground truth, tools **and** resources, stratified to fill the positive cell | RQ1/RQ2 | **MUST** | not started |
| **E3** | Positive control on the verified-checkable subset vs the uncheckable one | RQ2 | **MUST** | not started |
| **E4** | Full re-run at best instrument quality — **only after E3 validates the instrument** | RQ2 | **MUST** | deferred by design |
| **E5-P0** | Verification coverage from current declarations alone | RQ3 | **MUST** | not started |
| **E5-P1** | Coverage if `outputSchema` were universally present | RQ3 | **MUST** | not started |
| **E5-P2** | Coverage with an explicit Verification Contract; inferable vs specifiable gap | RQ3 | **MUST** | not started |
| **E6** | Relation-tier ablation (noun / field / keyed / snapshot) | RQ2 | SHOULD | not started |
| **E7** | Orthogonality: one external defense run, not cited | gap | SHOULD | not started |
| **E8** | L2/L3 robustness on the verified subset | RQ2 | SHOULD | not started |
| **E9** | Audit cost (extra calls, latency) | deployability | NICE | not started |
| **E10** | Incident corpus | motivation | NICE | not started |

**E4 is deliberately deferred.** Doc 22 scheduled it for Day 3; that was wrong. Another 1,242-server run returning 0% before we know whether the instrument works anywhere has almost no marginal scientific value, and it costs a day of compute and attention.

### E5's three interventions

- **P0 — current declarations.** Infer the relation from names, descriptions and schemas. This is what we have; it is what produced 0%.
- **P1 — mandatory `outputSchema`.** Note that MCP already supports `outputSchema`; low adoption is an ecosystem fact, not a protocol gap. Measure what universal adoption alone would buy. Expect it to be **insufficient**: a schema says what the output *looks like*, not which call with which key verifies the effect. Our own dominant failure mode — the diverted field being the reader's scoping field — is untouched by any output schema.
- **P2 — explicit Verification Contract.** Machine-readable, carried in `_meta` or an experimental field:

```json
{
  "writeTool": "save_url",
  "verifier": {"kind": "tool", "name": "get_archived_url"},
  "keyMap": {"save_url.url": "get_archived_url.url"},
  "assert": [{"equals": ["save_url.content", "get_archived_url.content"]}]
}
```

`verifier.kind` must also admit `"resource"` with a URI template, so the resource channel E0 is measuring is expressible.

---

## 9. Revised ten-day sequence

Days are from [`22`](22-research-diagnosis-and-10-day-plan.md) §8 with the corrections above applied. Streams: **INST** · **LABEL** · **ANALYSIS**.

| Day | INST | LABEL | ANALYSIS |
|---|---|---|---|
| **1** | E0 sweep running; snapshot-diff auditor | E1 labelling starts (265 rows, independent) | Claim-wording freeze (§5); citation quarantine assigned |
| **2** | Plan-as-artifact + `UNVERIFIABLE` verdict codes | E1 complete → κ | E0 report; E2 screening over the 1,242 |
| **3** | CLI skeleton; contract schema | **E2 hand audit** (tools + resources), stratified to 25–30 in the positive cell | E5-P0 / P1 counterfactual |
| **4** | **E3 runs.** Pre-registered rule recorded first | E2 adjudication + κ | E3 analysis against the rule |
| **5** | Branch: E3 pass → E4 launch. E3 fail → contract path | E10 if time | Narrative branch written down; both abstracts drafted, one chosen |
| **6** | E6 ablation; E8 L2/L3 | — | E5-P2 inferable-vs-specifiable |
| **7** | End-to-end demo on a real registry server, both branches rehearsed | — | Figures from raw JSON, scripted |
| **8** | Notebooks 01–06 run clean | — | Notebook narrative |
| **9** | — | — | Claim–evidence matrix; hostile-reviewer pass against [`19`](19-reviewer-review.md) |
| **10** | Clean-clone reproduction | — | Presentation |

**Critical path:** E0 → E2 → E3. Everything else can slip.

---

## 10. What we tell the professor

> We proposed a client-side defense for post-approval MCP server mutation, and our controlled benchmark suggested it worked. We then evaluated it against 1,242 third-party servers from the official registry and obtained zero true detections. Rather than hide that, we repaired the instrument four times — fixing a bug that prevented 90% of attacks from landing at all, and a false-positive regression — and got the same result each time, at a stable 1.3–1.8% false-positive rate.
>
> That raised the question the rest of the work answers: is the failure our detector, or the absence of observable structure in real MCP servers? We human-validated the auditability classifier, discovered that we had been measuring only one of MCP's two observation channels and swept the other, built a verified real-server subset, and ran a positive control. That tells us exactly where client-side verification works and where it cannot. Where it cannot, we quantify what additional protocol evidence would be required, and demonstrate it end to end on a real third-party server.

Hypothesis → system → failure → diagnosis → discriminating experiment → revised claim → constructive solution. That is the research process, not a tidy result, and it is worth more than a tidy result we could not defend.

---

## 11. Open risks specific to this direction

- **Scope creep through the CLI.** The system is a vehicle for the experiments. If a day goes into report formatting, it came out of E2 or E3. Keep it to one command and a readable table.
- **Contract circularity** — §4.1. The most likely way this paper gets rejected. Guard the inferable/specifiable distinction in every table.
- **E0 may find almost nothing.** Early signal from a 6-server smoke test: all six answered `Method not found` for both resource methods. If the full sweep confirms the channel is rare, the A0 correction is small — which is a *good* result (our number stands, and we can now say so with evidence) but it removes the "resources recover verifiability" storyline. Do not lean on that storyline before the sweep reports.
- **Selection effect on the funnel.** RQ2/RQ3 evidence comes from servers that survived a 14.3% launch-and-audit filter. Characterise survivors against dropouts (tool count, class mix, transport) — an hour of re-analysis that pre-empts "you measured the easy tail."
- **Demo fragility.** A live demo against a third-party server pulled from npm at presentation time can fail for reasons unrelated to the research. Record a video of a successful run as a fallback, and pin the package version.

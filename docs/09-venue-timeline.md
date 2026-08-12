# Venue Strategy and Timeline

> ⚠️ **All dates below are approximate cycle positions, not verified deadlines.** Confirm every one against the official CFP before planning around it. Deadlines move.

---

## 1. Venue tiers

### Tier 1 — top security (the stated target)
| Venue | Cycle shape | Fit |
|---|---|---|
| **USENIX Security** | rolling/multi-deadline cycles | ★ **Best fit.** Values measurement studies + systems artifacts; our D1 measurement and released benchmark match its taste exactly |
| **ACM CCS** | ~Jan and ~Apr rounds | Strong fit; likes threat-model rigor |
| **NDSS** | ~mid-year deadline | Strong fit; protocol security is squarely in scope |
| **IEEE S&P** | quarterly rounds | Fit, but the highest bar for theoretical novelty — Theorem 1 may read as too light here |

### Tier 2 — strong and realistic
**ACSAC** (applied, artifact-friendly) · **AsiaCCS** · **DIMVA** · **ESORICS** · **RAID**

### Tier 3 — ML/NLP venues
**ACL / EMNLP** (where MCP-Guard landed — Findings) · **NeurIPS D&B track** ← *genuinely good fit for MCP-MutBench + the measurement corpus, and often faster to land than Tier 1 security*

### Tier 4 — workshops (fast feedback, not the goal)
**AISec @ CCS** · **SaTML** · **DLSP @ S&P** — a 6-page version of the T2-adversary result alone would be accepted at any of these and would establish priority while the full paper is built.

---

## 2. Recommended strategy

> **Decision (2026-08-13): no rush, top venue only.** No workshop hedge, no early partial submission. The work goes out when it is a Tier-1 paper, not before.

**Primary: USENIX Security.** The paper's shape — an impossibility result, a cost-of-consistency theorem, an ecosystem measurement, and a released artifact — is a USENIX paper more than an S&P paper. S&P rewards deep theory; USENIX rewards *"here is a true thing about the world nobody knew."* That is C5, and it is the strongest thing we have.

**Consequences of not rushing — these are real advantages, not consolations:**

1. **The consistency cost curve can be measured properly.** C6 requires *building* adversaries at each rung of the ladder. Rushed, that is three toy classes; done properly, it is a real cost model across four domains with actual overhead numbers.
2. **The measurement can be large.** A corpus of 4,000 tools with validated labels is a far better paper than 500 with hand-waved ones, and the difference is mostly patience.
3. **Theorem 2 can be tightened.** Currently informal. A clean bound relating detection probability to relation degree and audit budget would substantially raise the paper's standing — see [`05-verifiability-taxonomy.md`](05-verifiability-taxonomy.md) §7 Q1–Q2.
4. **Question 5 can be developed.** Whether `deg` is gameable by a malicious server author turns the taxonomy from a measurement instrument into a deployable trust heuristic. That is potentially a second paper, and finding out costs time we now have.

**Priority risk of not rushing:** MCP security is a fast-moving area and the adaptive-adversary framing is not hard to think of. Mitigation is **not** a rushed workshop paper — it is a timestamped public artifact. Keep the repo public and commits dated; that establishes provenance without spending the result.

**Fallback ladder, only if Tier 1 rejects:** USENIX → CCS → NDSS → ACSAC → NeurIPS D&B.

---

## 3. Milestones

Work-week estimates, not calendar promises. Two people, part-time alongside coursework.

| Phase | Deliverable | Est. | Gate |
|---|---|---|---|
| **P0** | Repo, plan, docs | ✅ done | — |
| **P1** | D2 harness + out-of-band oracle; M1–M4 replicate prior result | 2 wk | Prior numbers reproduce |
| **P2** | **M5 adaptive adversary → RQ3** | 1 wk | ✅ **done** — DBR 100%→0% |
| **P3** | **Relation engine + adversary ladder → cost curve** | 3 wk | ✅ prototype done (3/9/17 LOC); needs 4 domains + overhead numbers |
| **P4** | D1 harvester; ≥400 servers, ≥3000 tools | 3 wk | corpus built |
| **P5** | Codebook, 300 labels, κ | 1.5 wk | **κ ≥ 0.7** (else §4 fallback) |
| **P6** | Classifier + held-out validation | 1.5 wk | usable P/R |
| **P7** | **Full-corpus classification → RQ4** | 0.5 wk | **headline % exists** |
| **P8** | BIM implementation | 3 wk | runs end to end |
| **P9** | Full experimental matrix + frontier model | 2.5 wk | matrix complete |
| **P10** | Statistics, ablations, figures | 2 wk | F4/F5 final |
| **P11** | Paper draft v1 | 3 wk | full draft |
| **P12** | Internal review, artifact packaging, polish | 2.5 wk | submission-ready |

**Total ≈ 25–27 work-weeks.** At ~60% part-time capacity alongside coursework, **~10–11 months**.

**Honest read:** a Tier-1 submission is a **late-2027** target. That is the correct timeline for this paper and rushing it would produce a worse one. Two theorems, an ecosystem measurement, a cost model, and a released artifact is not a three-month project.

---

## 4. Critical path

```
P1 ─▶ P2 ✅ ─▶ P3 ─▶ P8 ─▶ P9 ─▶ P10 ─▶ P11 ─▶ P12
P4 ─▶ P5 ─▶ P6 ─▶ P7 ─────────────┘
```
D1 (P4–P7) and BIM (P8) are independent — **parallelize across the two authors.** Suggested split: one owns the measurement arm (D1/classifier), the other owns the systems arm (harness/BIM). Both own the paper.

---

## 5. Submission checklist

- [ ] Every number in the paper regenerated by a tracked script
- [ ] Held-out test set touched exactly once
- [ ] RQs/metrics/tests pre-registered in-repo before final runs
- [ ] All 24+ references verified against official venue pages (`scripts/verify_refs.py`)
- [ ] Artifact packaged, anonymized, with README + one-command repro
- [ ] Ethics statement: static harvest only, no live-server probing, no PII
- [ ] Responsible disclosure statement — if any real server is found mutating, disclose before publication
- [ ] Limitations section names V0 explicitly as unsolved
- [ ] Anonymization pass for double-blind venues (repo URL, author names, acknowledgements)
- [ ] Page limit and template compliance for the specific venue

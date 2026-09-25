# Submission Execution Calendar

Primary target: USENIX Security 2027 Cycle 2. Dates below are internal
deadlines unless marked official. All official deadlines are Anywhere on Earth
(AoE).

Official source: <https://www.usenix.org/conference/usenixsecurity27/call-for-papers>

## Critical path

```text
two independent labels ─┐
                        ├─ evidence freeze ─ manuscript freeze ─ anonymous package
Linux/Docker reruns ────┤
held-out ≥10 + baselines┘
```

The project must not spend the final month discovering whether a core claim is
true. All empirical P0 gates therefore close before December; January is for
writing, consistency, anonymization, and submission checks.

## Calendar

| Date | Deliverable | Exit condition |
|---|---|---|
| 2026-09-25--10-02 | Round-2 annotation launch | Two independent annotators briefed; blank-sheet hashes saved; no cross-discussion |
| 2026-09-25--10-05 | Linux/Docker host ready | Disposable Linux host, Docker works, no personal credentials, enough disk, repository cloned |
| 2026-10-03--10-12 | Round-2 labels complete | 265/265 valid rows in both files; pre-adjudication hashes frozen |
| 2026-10-06--10-13 | Integrated pinned-server rerun | `run_m2_real_server.py` passes; raw JSON, image ID, kernel, Docker version, and command preserved |
| 2026-10-10--10-18 | Held-out manifest freeze | At least 10 independent implementations; exact versions/integrities; at least two per claimed class; `status=FROZEN` |
| 2026-10-13--10-22 | Matched held-out experiment | No defense, response auditor, static least privilege, plain sandbox, and MCPGate run on the same frozen workloads |
| 2026-10-18--10-24 | Round-2 scoring/adjudication | Raw kappa reported first; disagreement log and final adjudicated labels preserved |
| 2026-10-25 | IEEE S&P go/no-go | Stretch submission only if every P0 gate is closed and manuscript numbers are frozen |
| 2026-10-26--11-06 | Statistics and final figures | Clustered intervals, p50/p95/p99, CPU, memory, false-block, UNKNOWN, crash/recovery results generated from raw rows |
| 2026-11-07--11-16 | Optional IEEE S&P package | Only after go decision; official abstract deadline 2026-11-10 and paper deadline 2026-11-17 |
| 2026-11-18--11-30 | Evidence and claim freeze | Every paper number maps to checked-in JSON; no OPEN claim appears in prose |
| 2026-12-01--12-14 | Full manuscript rewrite | 13-page body draft in official USENIX format; all main claims, baselines, limitations, and related work complete |
| 2026-12-15--12-23 | Internal review 1 | One security reviewer and one clarity reviewer; written issue list triaged |
| 2026-12-24--2027-01-03 | Revision and artifact rehearsal | Clean Linux clone reproduces all tables/figures; full artifact manifest verified |
| 2027-01-04--01-10 | Internal review 2 | Adversarial claim audit, citation audit, ethics review, grayscale/print inspection |
| 2027-01-11--01-15 | Anonymous export freeze | No identities, local paths, secrets, public Git history, or contributor metadata; anonymous URL tested |
| 2027-01-16 | Upload rehearsal | PDF and artifact uploaded to a private rehearsal location; page/font/metadata checks pass |
| 2027-01-19 | **Official mandatory registration** | Fixed title, full author list, ORCIDs, nonblank abstract, topics, and conflicts registered |
| 2027-01-20--01-24 | Final proof | Numbers, captions, references, appendix links, and artifact hashes independently cross-checked |
| 2027-01-25 | Internal submission cutoff | Final PDF uploaded at least 24 hours early; only fatal corrections afterward |
| 2027-01-26 | **Official paper deadline** | Submitted PDF and metadata frozen |
| 2027-01-27--01-28 | Artifact grace-period audit | Anonymous link, access, clean-clone commands, and redaction checked again; paper unchanged |
| 2027-01-29 | **Official artifact deadline** | Artifact frozen and available through the full review/shepherd period |

## Weekly decision rule

Every Friday, update only four states: `DONE`, `AT RISK`, `BLOCKED`, or
`DROPPED`. Any `AT RISK` P0 item must have an owner and recovery date. A P0
item still blocked at its exit date forces claim narrowing or venue deferral;
it must never be converted into past-tense prose without evidence.


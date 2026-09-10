# Experiment specification — permission-compatible contract violations

Written 2026-09-10. Follows [`26-m1-novelty-gate.md`](26-m1-novelty-gate.md), which retired the broad architectural claims and left this candidate unresolved.

**Status: pilot exercised on one workflow (constrained class); Q1 evidence obtained; broader instrument validation and generalization pending.** Not "instrument validated" — one workflow, eight scenarios, one server we wrote. `experiments/run_append_pilot.py`.

## 1. The mistake this specification exists to avoid

The obvious experiment is: give a permission baseline `write report.txt`, give a contract `write report.txt with these exact bytes`, have a malicious server write different bytes, and observe that the contract catches what the permission does not.

**That result would be worthless.** The contract holds strictly more information about the intended effect. Of course it catches more. What that demonstrates is that *a more precise specification permits a more precise check* — which is true by construction and needs no experiment.

So the two questions must be separated, and each needs its own control:

| Question | Fair comparison | What a positive answer means |
|---|---|---|
| **Q1 — does exact effect specification buy protection?** | resource permission vs. resource + content constraint | more specification is worth its cost. A property of the *contract*, not of us |
| **Q2 — does our mechanism buy anything beyond the specification?** | a **simple staging + exact-diff validator** given the *same* contract and the *same* trusted information, vs. the proposed mediation | our machinery earns its complexity |

**Q2 is the one that decides whether there is a system contribution at all.** If a simple validator with the same contract achieves the same protection and the same utility, then the proposed mediation is unjustified complexity and the honest report says so.

## 2. Where do the expected bytes come from?

For `write_file(path, content)` the approved arguments contain the expected bytes, and that is the easy case. "Summarise this report", "fix this bug", "update the customer record" have no single acceptable output, and an evaluation built only on the easy case would claim generality it has not earned.

Three workflow classes, all three carried through every condition:

| Class | Specification available | Example |
|---|---|---|
| **Exact** | target and final bytes both fixed in advance | `write_file(path, content)` |
| **Constrained** | output not known in advance; an executable postcondition exists | "append a row" — file grows by one well-formed record, prior rows unchanged |
| **Underspecified** | no trusted specification determines the acceptable *content* | "summarise the report" — many outputs are correct |

**Underspecified is a property of PROPERTIES, not of workflows.** "Summarise the report into `summary.txt`" leaves the summary's semantic acceptability undetermined while leaving the destination and the frame condition perfectly checkable:

| Property | Verdict available |
|---|---|
| approved destination | PASS / FAIL |
| other protected files unchanged | PASS / FAIL |
| output produced | PASS / FAIL |
| summary semantically acceptable | UNKNOWN |

So verdicts are **per property**, and a semantic UNKNOWN must never mask a known violation elsewhere in the same execution. **Verdict and action are also separate**: what to do when a property is UNKNOWN — commit, block, or ask for confirmation — is a policy written in advance, not a consequence of the code.

**And UNKNOWN is not a finding by itself.** Withholding a specification and then observing that something is undetermined is a design consequence. What is measured is how often real workflows leave a property undetermined and *how much is recoverable by stating more* — which is what the ladder in §2.1 does.

### 2.1 The ladder — graded trusted information

The same workflow is run at increasing rungs, and protection, honest completion, per-property UNKNOWN and specification effort are measured at each:

| Rung | What is stated |
|---|---|
| **L1** | destination only |
| **L2** | + structural constraints |
| **L3** | + task-specific content constraints, *where they exist* |

The question this turns Q1 into:

> **How much trusted specification buys how much useful protection, and at what cost?**

`experiments/run_specification_ladder.py` implements this. Specification effort is counted as declared fields per rung, which is a **proxy** — it counts what had to be stated, not the time or expertise to arrive at it.

## 3. Conditions

| Condition | What it is |
|---|---|
| **Undefended** | server holds the capability and acts. Establishes whether each attack lands at all |
| **File-allowlist commit** | the server runs in a staging copy and only allowlisted files are committed. **Not equivalent to OS path-permission enforcement**, where a forbidden write fails at the syscall and the server learns it failed. And its semantics are **partial commit**: an unpermitted file is dropped and the rest commits, rather than the transaction being rejected whole — so its utility and consistency need measuring separately rather than folding into a prevention number. **If AgentBound itself is not run, this is never "the AgentBound baseline"** |
| **Simple contract validator** | same contract, same trusted observation, minimal machinery: stage, run, diff, compare, commit or discard |
| **Proposed mediation** | the full mechanism |

Naming discipline matters here. A custom sandbox labelled as somebody else's published system misrepresents the comparison; if AgentBound is reproduced rather than run, the reproduction is labelled as such with what was and was not reproduced.

## 4. Attacks

The defining property: **the approved call is unchanged and permission-compatible.** The server's *implementation* diverges, inside what it is allowed to touch.

- content substitution at the approved path
- partial write then abandon
- write then rename within the permitted area
- extra permitted-path write not named by the contract
- correct bytes, then a later mutation
- effect performed by a delayed child process
- concurrent invocations racing one contract
- crash mid-effect
- silent no-op

Two rules, both learned the hard way in this project:

- An attack that **did not land in the undefended control** contributes nothing. It is excluded from prevention coverage, not counted as a success.
- An attack that fails because the harness never created its precondition is a **harness defect or an unsupported case** — never a defense success. `rename_after_write` already failed this way once, attacking a file that had not been written yet.

## 5. Oracle

Trusted state observation from outside the server's reach, before and after, as in `experiments/run_effect_oracle.py`. Five independent fields: mutation attempted, protocol status, authorized effect observed, unauthorized effect observed, outcome unknown.

**Neither the mutation plan nor the protocol status is ground truth.** Both have already been shown wrong in this project, in opposite directions.

## 6. Metrics

| Metric | Why |
|---|---|
| unauthorized committed effects | the security outcome |
| honest completion, per workflow class | a defense that breaks constrained workflows is not usable |
| false rejection | rejecting honest work is the cost side |
| UNKNOWN rate | honest, but a mechanism that mostly declines is not a defense |
| **specification effort** | who wrote the contract, how long, and could it be derived |
| **configuration effort per server** | generality that migrates into config is not generality |

The last two are not overhead — they are the answer to "does this scale beyond the exact case".

## 7. Decision rule, pre-registered

- **Q1 answered** if the content-constrained condition prevents effects the path-permission condition does not, on attacks demonstrated undefended, with honest completion within a 5pp non-inferiority margin.
- **Q2 is INACTIVE.** It compares a second mechanism against the simple validator, and no second mechanism has been specified — the proposed mediation *is* stage/diff/commit. Running one implementation twice under two names would manufacture a comparison, so the pilot runs three conditions and answers Q1 only. Q2 activates when a real mechanism difference exists.
- When active, **Q2 is answered positively** only if the proposed mediation beats the **simple validator** on at least one of: prevention coverage, honest completion, UNKNOWN rate, or effort — with the same contract and the same trusted information.
- **If Q2 shows no improvement, that is not automatically "the simple validator suffices."** A null result can mean the mechanism adds nothing, or that the sample was too small and the interval too wide to tell. Those are different findings and must be reported differently. So a threshold is fixed in advance:

  - **improvement** — the proposed mediation beats the simple validator by ≥ 10 percentage points on prevention coverage, or ≥ 10pp on honest completion, or ≥ 10pp on UNKNOWN rate, with the interval excluding zero
  - **equivalence** — the **entire confidence interval** lies within −5pp to +5pp. Merely being able to exclude a 10pp improvement is *not* equivalence: an interval spanning −8pp to +4pp excludes 10pp and is still consistent with a meaningful loss
  - **inconclusive** — anything else, and the honest report is that the experiment could not distinguish them

  A previous draft of this document asserted that a negative Q2 was "entirely plausible" because Alcatraz published the machinery in 2003. **That inference was wrong and is withdrawn.** Prior work bounds what we may claim as novel; it says nothing about how our mechanism will perform. Predicting the result from the literature is exactly the reasoning a pre-registered threshold exists to prevent.

## 8. What this specification does not settle

- It does not establish that the surviving candidate is the *only* possible system contribution. M1 rejected specific broad claims; it did not enumerate the space.
- It does not validate the earlier large-scale results. Those 1,242-server trials have **no independent state evidence** — they remain protocol- and proxy-based observations, and cannot be re-reported as observed-compromise detection rates. The effect oracle exposed the label defect; it did not retroactively repair the data. **The measurement contribution needs its own validation pass, separately from this experiment.**
- It does not settle M1, which remains HOLD.

## 9. Order of work

1. Build the harness: three workflow classes, four conditions, the oracle, the six metrics.
2. Run Q1. Report it as a property of specification, not of us.
3. Run Q2 against the simple validator. This decides whether a system contribution exists.
4. Only then consider generality across servers.

κ labelling proceeds in parallel; it is human-bound and independent of all of the above.

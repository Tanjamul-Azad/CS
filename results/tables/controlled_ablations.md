# Controlled MCPGate ablations

> Deterministic local implementation evidence. This table does not replace
> the pending pinned third-party-server Docker evaluation.

| Variant | Removed property | Attack/case | Failure exposed | Observation |
|---|---|---|---:|---|
| full_mcpgate | none | content_substitution | NO | refused=True; trusted_file_exists=False |
| no_allowance_ledger | atomic reserve/idempotency | same-ID replay | YES | runner_entries=2; expected_with_full=1 |
| no_request_shape | preflight and transport argument checks | hidden extra field | YES | runner_saw_hidden=True; decision=COMMITTED |
| independent_second_read | same-read promotion | TOCTOU mutation | YES | decision_matched=True; attacker_bytes_committed=True |
| shared_staging | per-invocation staging | two honest overlapping calls | YES | outcomes=['refused', 'refused']; false_refusals=2 |
| path_policy_only | content/effect diff | content substitution | YES | approved_path_written=True; approved_content=False |
| no_outer_namespace | whole-world filesystem confinement | outside-world side write | YES | outside_effect=True; trusted_admission_correct=True |

Interpretation: the full mediator row should expose no failure. Every
removed-property row is expected to expose the named security or utility
failure. The no-namespace row deliberately shows that trusted-store
admission can remain correct while an outside-world effect still occurs.

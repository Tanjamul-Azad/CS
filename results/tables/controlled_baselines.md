# Controlled baseline comparison

> Filesystem stub with corpus-derived attack shapes; not a held-out
> third-party-server result. A plain sandbox intentionally has the
> same within-sandbox effects as no defense because it adds no per-call
> path/content policy.

| Attack | Applicable | Condition | Prevented | Task completed | Surfaced |
|---|---:|---|---:|---:|---:|
| none | YES | undefended | YES | YES | NO |
| none | YES | plain_sandbox | YES | YES | NO |
| none | YES | response_auditor | YES | YES | NO |
| none | YES | path_policy | YES | YES | NO |
| none | YES | trusted_executor_gateway | YES | YES | NO |
| path_diversion | YES | undefended | NO | NO | NO |
| path_diversion | YES | plain_sandbox | NO | NO | NO |
| path_diversion | YES | response_auditor | NO | NO | YES |
| path_diversion | YES | path_policy | YES | NO | YES |
| path_diversion | YES | trusted_executor_gateway | YES | NO | YES |
| hidden_extra_field | NO | undefended | YES | YES | NO |
| hidden_extra_field | NO | plain_sandbox | YES | YES | NO |
| hidden_extra_field | NO | response_auditor | YES | YES | NO |
| hidden_extra_field | NO | path_policy | YES | YES | NO |
| hidden_extra_field | NO | trusted_executor_gateway | YES | NO | YES |
| content_substitution | YES | undefended | NO | NO | NO |
| content_substitution | YES | plain_sandbox | NO | NO | NO |
| content_substitution | YES | response_auditor | NO | NO | NO |
| content_substitution | YES | path_policy | NO | NO | NO |
| content_substitution | YES | trusted_executor_gateway | YES | NO | YES |
| silent_noop | YES | undefended | YES | NO | NO |
| silent_noop | YES | plain_sandbox | YES | NO | NO |
| silent_noop | YES | response_auditor | YES | NO | NO |
| silent_noop | YES | path_policy | YES | NO | NO |
| silent_noop | YES | trusted_executor_gateway | YES | YES | NO |
| duplicate_effect | NO | undefended | YES | YES | NO |
| duplicate_effect | NO | plain_sandbox | YES | YES | NO |
| duplicate_effect | NO | response_auditor | YES | YES | NO |
| duplicate_effect | NO | path_policy | YES | YES | NO |
| duplicate_effect | NO | trusted_executor_gateway | YES | YES | YES |

The response auditor may surface an attack after execution but does not
prevent the effect. The path policy blocks diversion but is blind to
substituted bytes at the allowed path. The trusted-executor gateway is
the simpler architecture when exact output bytes are already known; the
server never receives the write capability in that condition.

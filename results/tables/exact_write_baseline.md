# Exact-write engineering baseline

> development-machine exact single-file microbenchmark; not a third-party-server or release-environment performance claim

## Security cases

| Condition | Case | Trusted outcome correct | Outside effect |
|---|---|---:|---:|
| path_policy_only | content_substitution | NO | NO |
| trusted_direct_writer | content_substitution | YES | NO |
| mcpgate_exact_write | content_substitution | YES | NO |
| mcpgate_exact_write | unmediated_side_effect | YES | YES |
| trusted_direct_writer | unmediated_side_effect | YES | NO |

## Local latency

| Condition | n | p50 (ms) | p95 (ms) | p99 (ms) |
|---|---:|---:|---:|---:|
| trusted direct writer | 100 | 3.7432 | 3.8588 | 4.7782 |
| MCPGate exact write | 100 | 6.2546 | 6.3653 | 6.5303 |

Development-machine p50 ratio: 1.671x.

Decision: For already-known exact bytes and one local write, the trusted writer is the simpler baseline. MCPGate needs a non-trivial independently verifiable server workload to justify invocation.

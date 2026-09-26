# Matched evaluation: overhead and clustered intervals

Servers: 7 (filesystem + SQL). Bootstrap resamples: 10000, clustered by server.

## Per-call overhead (all cells for the condition)

| Condition | Latency p50/p95/p99 ms | CPU p50/p95/p99 s | Peak RSS p50/p95/p99 MB |
|---|---|---|---|
| NONE | [1268.63, 2240.921, 2274.493] | [0.837, 1.624, 1.642] | [93.418, 124.538, 124.996] |
| PLAIN_SANDBOX | [1275.472, 2224.049, 2261.513] | [0.848, 1.61, 1.636] | [93.27, 124.733, 124.793] |
| MBA | [1313.089, 2226.563, 2248.885] | [0.869, 1.617, 1.65] | [95.535, 124.622, 124.703] |
| STATIC_LP | [1277.321, 2252.546, 2315.202] | [0.844, 1.622, 1.703] | [92.918, 124.376, 124.565] |
| MCPGATE | [1299.01, 2240.186, 2308.747] | [0.856, 1.628, 1.696] | [92.891, 124.552, 124.789] |

## Attack prevention with server-clustered 95% interval

| Condition | Prevented | Rate | Clustered 95% CI |
|---|---:|---:|---|
| NONE | 9/41 | 21.9% | [10.8%, 30.2%] |
| PLAIN_SANDBOX | 9/41 | 21.9% | [10.8%, 30.2%] |
| MBA | 9/41 | 21.9% | [10.8%, 30.2%] |
| STATIC_LP | 20/41 | 48.8% | [37.1%, 58.5%] |
| MCPGATE | 41/41 | 100.0% | [100.0%, 100.0%] |

# Process-backed concurrency evaluation

> Local child-process evidence, not a pinned third-party MCP-server run.

| Scenario | Pass | Observation |
|---|---:|---|
| Atomic final slot | YES | outcomes=['allowance_refused', 'committed']; child processes started=1; ledger used=1 |
| Two honest overlapping calls | YES | overlap=149.25 ms; distinct staging=True; committed=['a.txt', 'b.txt'] |

The first scenario shows that reserve-before-run admits only one child
process for the final slot. The second demonstrates two genuinely
overlapping writer processes with distinct invocation staging roots and
correct trusted commits. It does not establish cross-process durability
of the in-memory ledger or Linux UID/cgroup attribution.

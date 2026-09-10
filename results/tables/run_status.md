# Scale-run terminal status

Why servers dropped out. `no_write_tool_found` dominates: most MCP servers expose nothing that mutates state.

| Status | Servers |
|---|---|
| failed | 3123 |
| no_write_tool_found | 2879 |
| host_timeout | 1447 |
| ok | 1242 |
| no_result_written | 1 |

*Source: `data/processed/scale_run.json`. Regenerate with `python experiments/make_results.py`.*

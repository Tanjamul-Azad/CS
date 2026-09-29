# Product map — what EffectSeal is and where its code lives

EffectSeal runs an unmodified MCP server against a private copy of state,
stops every writer, reads the result once, and promotes exactly those bytes
only if they match a contract bound to the approved call. Contracts for new
calls come from pin-time effect templates.

## Core library: `src/mcpgate/`

| Module | Role |
|---|---|
| `contract.py` | contract identity and request-shape checking |
| `allowance.py` | reserve/commit/fail ledger; `SQLiteAllowanceLedger` is the durable backend |
| `mediator.py` | single-file mediator and staged invocation |
| `tree_mediator.py` | whole-tree snapshots, path rules, content predicates, tree contracts |
| `sqlite_mediator.py` | canonical SQLite state, `sqlite_state_text` for templates |
| `template_inference.py` | pin-time effect templates: perturbation, abstraction, anti-unification, clock holes, slack |
| `canonical.py` | canonical views of SQLite and zip files for templates |
| `gateway.py`, `executors.py` | trusted-executor gateway (earlier design) |
| `network_broker.py` | outbound HTTP broker core (not in the paper's claims) |

## Supporting code

| Path | Role |
|---|---|
| `src/mcpaudit/auditor.py` | response auditor with metamorphic read-backs (the baseline that fails) |
| `src/mcpmut/live.py` | `LiveSession`, the MCP stdio client used by probes and agents |
| `src/mcpmut/proxy.py` | declaration-driven tampering proxy used in the registry audit |
| `src/measure/` | registry harvest, relation classification, launchability |
| `docker/impl_tamper.cjs`, `docker/tamper_site/sitecustomize.py` | attack interposition for Node and Python servers (modes: path, content, extra, noop, symlink, escape, covert, inject, noisy, sql_*) |
| `docker/matched_probe.py`, `docker/matched_sql_probe.py` | in-container drivers with each server's honest workload |
| `formal/EffectSeal.tla`, `formal/*.cfg`, `formal/check_model.py` | TLA+ model, TLC configs, independent checker; logs in `formal/tlc/` |

## Servers

- Development set (7): `artifact/held-out-manifest.json` (5 file, 2 SQLite used).
- Held-out batch (4): `artifact/held-out-batch2-manifest.json`.

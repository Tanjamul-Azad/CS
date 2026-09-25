# MCPGate Phase 2: Network and SQL Effect Mediation

## Status and claim boundary

This began as a **pre-registered extension plan**. Two local core prototypes
now exist: `src/mcpgate/network_broker.py` checks an exact HTTP request before a
trusted pinned transport sends it, and `src/mcpgate/sqlite_mediator.py` compares
a private SQLite database's complete schema and row state before atomic
promotion. Their adversarial unit tests pass. This is not yet evidence that
MCPGate mediates network or database effects for real MCP servers. Direct
egress confinement, real-server adapters, matched baselines, container bypass
tests, and raw outcome artifacts remain open. The filesystem paper keeps
RQ1--RQ5 and its present trusted-state-admission claim unchanged. Network and
SQL become RQ6--RQ7 only after every go/no-go condition below is satisfied.

The unifying principle is:

> A server-authored response is not proof of an external effect. A trusted
> boundary must either control the effect before it becomes irreversible or
> stage it in a state that can still be compared and discarded.

Filesystem writes can be staged and promoted. Network sends usually cannot be
recalled after transmission, so they require **pre-effect mediation**. SQL
updates may be staged inside a database transaction or disposable database
copy, but only if every connection and database-side effect is contained.

## RQ6 -- Network-effect mediation

**Question.** When an untrusted local MCP server is denied direct egress, can a
trusted broker enforce an exact outbound-request contract without relying on
the server's response?

### Threat model

The server may change the destination, method, path, headers, body, protocol,
or timing; follow redirects; trigger DNS rebinding; open raw TCP/UDP sockets;
use HTTP CONNECT, WebSocket, QUIC, or a child process; and return an
honest-looking MCP response. The server cannot modify the broker, contract,
ledger, network namespace, or trusted resolver. Availability and
traffic-analysis leakage are non-goals for the first network prototype.

### Network contract

The strict N3 contract binds:

- scheme and application protocol;
- canonical host, port, and resolved-address policy;
- HTTP method and normalized path/query;
- allowed header names and exact security-sensitive header values;
- exact body bytes or body hash plus maximum length;
- redirect count and allowed redirect destinations;
- response-size and time bounds;
- maximum connection/request count; and
- request identity, expiry, and replay allowance.

N1 binds only the destination; N2 additionally binds method and resource; N3
binds the complete request. Missing security-relevant fields produce UNKNOWN
or refusal, never an implicit wildcard.

### Enforcement pipeline

```text
Network contract
-> canonicalization and validity check
-> durable allowance reservation
-> per-call network namespace with direct egress denied
-> trusted DNS resolution and address pinning
-> request-shape check at the broker
-> trusted broker performs the outbound request
-> response-size/status policy check
-> ledger finalization and auditable record
```

For unmodified HTTP-aware servers, the compatibility prototype may expose an
invocation-private HTTP proxy. HTTPS CONNECT permits destination enforcement
but not plaintext method/path/body enforcement. Therefore an N3 claim needs
either a trusted request executor or explicitly disclosed TLS termination with
certificate handling. Raw TCP, UDP, QUIC, covert DNS, and non-proxy-aware
clients remain denied in the strict experiment.

### Frozen attacks

1. hostname and port diversion;
2. public-hostname-to-private-address DNS rebinding;
3. redirect to an unapproved origin;
4. method substitution;
5. path/query substitution;
6. hidden authorization/header insertion;
7. body substitution and body extension;
8. duplicate/replayed send;
9. extra second connection;
10. HTTP CONNECT, raw socket, UDP/QUIC, and child-process bypass attempts;
11. response spoofing after a refused send; and
12. concurrent calls competing for the last allowance.

### Baselines and metrics

Matched baselines: no defense, response auditor, destination firewall/ACL,
domain-only proxy, static least privilege, and full contract broker. Report
send prevention, honest completion, false block, UNKNOWN, bytes transmitted,
extra connections, redirects, DNS decisions, latency p50/p95/p99, CPU, memory,
and at least 100 trials for races. Packet capture or broker logs form the
independent effect oracle; an MCP response never does.

### Network success criterion

On frozen HTTP workloads, full N3 mediation must transmit zero unapproved
requests, preserve at least 95% honest completion, have a two-sided 95%
confidence interval reported for both quantities, and block every declared
direct-egress bypass. Failure narrows the claim to the exact protocol and proxy
mode that passed.

## RQ7 -- SQL-effect mediation

**Question.** Can MCPGate admit only contract-matching database changes when an
untrusted MCP server is confined to an invocation-private transaction or
database copy?

### Threat model

The server may change SQL text or parameters, touch extra rows/tables, modify
schema, install triggers, invoke stored procedures or extensions, open a second
connection, exploit autocommit, race another transaction, or return a false
success response. The first prototype excludes databases whose triggers,
extensions, or external functions can produce effects outside the controlled
database boundary.

### SQL contract

The strict D3 contract binds:

- database identity and schema version;
- operation class and parameter values;
- permitted tables, columns, and primary-key/row predicates;
- exact new values or a canonical row-set digest;
- maximum affected rows and statements;
- whether schema changes, triggers, procedures, and extensions are forbidden;
- isolation level and timeout; and
- request identity, expiry, and replay allowance.

Contract enforcement must not depend only on parsing attacker-controlled SQL.
The database engine's authorization boundary and an independently observed
before/after write set are authoritative.

### Enforcement pipeline

```text
SQL contract
-> validity and schema-version check
-> durable allowance reservation
-> invocation-private DB identity/transaction or copy-on-write database
-> execute with least-privilege role and resource limits
-> revoke all writers / wait for transaction quiescence
-> trusted before/after schema and row-set diff
-> commit matching transaction or discard private database
-> ledger finalization and auditable record
```

The first implementation target is SQLite because its complete state can be
placed in an invocation-private file and compared before atomic replacement.
PostgreSQL is a separate experiment requiring a dedicated role, one controlled
connection or disposable database/schema, trigger/extension restrictions,
transaction-state verification, and proof that no second connection remains.
Results from SQLite must not be generalized to PostgreSQL/MySQL.

### Frozen attacks

1. value substitution;
2. predicate widening (`id = 7` to all rows);
3. extra table or row modification;
4. schema modification;
5. trigger installation or trigger-mediated extra write;
6. stacked/extra statement;
7. autocommit or early commit;
8. second-connection bypass;
9. replay and duplicate transaction;
10. TOCTOU between diff and commit;
11. concurrent lost-update/write-skew cases; and
12. false success response after rollback.

### Baselines and metrics

Matched baselines: no defense, response auditor, DB user privileges, SQL
statement/table allowlist, transaction-only sandbox, and full effect-diff
mediator. Report unauthorized rows/columns/tables changed, honest completion,
false block, UNKNOWN, rollback success, latency p50/p95/p99, CPU, memory,
database-size overhead, and concurrency anomalies.

### SQL success criterion

For frozen SQLite workloads, D3 mediation must commit exactly the contracted
schema and row-set delta, commit no additional database effect in all frozen
attacks, preserve at least 95% honest completion, and report two-sided 95%
confidence intervals. External trigger/procedure effects or uncontrolled
second connections invalidate the claim rather than being counted as blocked.

## Implementation order

1. Finish and freeze the current filesystem paper evidence.
2. Make the allowance ledger durable; both extensions depend on crash-safe
   reservation and replay records.
3. Implement N3 HTTP request contracts and a trusted broker with direct egress
   denied in a Linux network namespace.
4. Freeze network attacks and baselines before running results.
5. Implement D3 SQLite contracts using a private database copy, complete
   before/after diff, same-snapshot promotion, and replay-safe ledger.
6. Freeze SQL attacks and baselines before running results.
7. Treat PostgreSQL and arbitrary TCP as separate follow-on claims.

## Current implementation audit, 2026-09-26

| Component | Current state | What is still required |
|---|---|---|
| Exact HTTP request contract | Local prototype and adversarial unit tests pass | Real MCP adapter and frozen workload integration |
| Trusted DNS decision and address pinning | Local prototype and injected resolver tests pass | Linux packet-level oracle and rebinding test |
| Redirect-free bounded HTTP transport | Implemented in the broker | Live HTTP and TLS integration tests |
| Durable network replay allowance | Local cross-process ledger replay test passes | Concurrent process race run in Linux |
| Direct server egress denial | Not implemented in the integrated runner | Network namespace or equivalent policy plus bypass suite |
| SQLite semantic snapshot | Local prototype and adversarial unit tests pass | Real server integration for both frozen SQLite servers |
| Private SQLite state and atomic promotion | Local prototype and same-filesystem promotion test pass | Container writer-closure and WAL-mode integration |
| PostgreSQL or arbitrary network protocols | Not implemented and not claimed | Separate future work |

The network framework is therefore architecturally defined and partly
implemented, but not complete. The SQL framework has a tested local core, but
is also incomplete at the real-server boundary. The manuscript must keep both
in future work until the frozen matched evaluations pass.

## Go/no-go rule for the current manuscript

Network and SQL remain in **Limitations and Future Work** unless a complete
domain satisfies all of the following: integrated implementation, frozen
attacks, independent effect oracle, matched baselines, held-out workloads,
100-trial race tests, confidence intervals, pinned raw artifacts, and a clean
Linux reproduction. A design document or partial prototype never becomes a
past-tense paper contribution.

## Presentation-ready Bangla answer

> “বর্তমান MCPGate filesystem trusted-state admission নিয়ে complete claim
> করবে। Network-এ effect পাঠানোর পরে rollback করা যায় না, তাই সেখানে staging
> নয়—direct egress বন্ধ করে trusted broker request পাঠানোর আগেই destination,
> method, path, headers এবং body contract-এর সঙ্গে মিলাবে। SQL-এ transaction
> বা private database copy-তে effect stage করে trusted before/after row ও
> schema diff মিললে commit, না মিললে rollback/discard করব। এই দুইটি এখন
> pre-registered extension plan; result না পাওয়া পর্যন্ত আমরা prevention claim
> করছি না।”

# Held-Out Real-Server Protocol

Status: candidate identities and package artifacts were pre-registered on
2026-09-25. Isolated schema plus benign mutating-workflow/oracle eligibility is
complete, and the 10-server manifest is `FROZEN` before security outcomes
(EXACT 4, CONSTRAINED 4, UNDERSPECIFIED 2). The matched five-condition security
evaluation has not run, so the held-out evaluation P0 gate remains open.

## 1. Selection frame

Candidates came from the Official MCP Registry search API:

<https://registry.modelcontextprotocol.io/v0.1/servers>

The search was restricted to latest registry entries advertising a local
`stdio` package, no registry-declared required environment variable, and a
description indicating a local filesystem, memory/document, or SQLite effect
surface. Exact npm integrity or PyPI wheel SHA-256 was then resolved. Remote
servers, credential-bearing packages, the seven historical development
servers, and packages lacking a resolvable pinned artifact were excluded.

The 10 primary candidates and three ordered reserves are recorded in
`artifact/held-out-candidates.json`. Candidate class is description-based and
must not be reported as ground truth until live tool schemas are inspected.

## 2. Pre-effect eligibility check

On the isolated Linux/Docker host, each candidate receives only these checks:

1. artifact hash matches the pre-registered integrity;
2. package installs without host mounts, credentials, or runtime network;
3. process completes MCP initialization and `tools/list` within the timeout;
4. at least one local mutating workflow and its independent effect oracle can
   be instantiated using synthetic data; and
5. the tool declaration supports one of EXACT, CONSTRAINED, or UNDERSPECIFIED
   under the frozen field vocabulary.

No attack or defense outcome may be examined during eligibility. If a primary
fails an eligibility condition, record the reason and use the first reserve in
the same class. A server must never be replaced because a baseline or MCPGate
performs poorly.

The runner installs npm artifacts with lifecycle scripts disabled. This keeps
pre-effect package installation bounded and prevents candidate-controlled
post-install programs from stalling the batch. A package that cannot expose its
prebuilt executable under that condition is recorded as ineligible rather than
being repaired after security outcomes are visible. Required, non-secret launch
arguments may be added only from the candidate's own help/usage output, with an
amendment recorded in `artifact/held-out-candidates.json` before any tool call.

## 3. Freeze transition

After eligibility, copy accepted entries into `artifact/held-out-manifest.json`
with:

- exact server/package identity, version, and integrity;
- the inspected tool name and frozen workflow class;
- adapter/runner command;
- independent oracle location;
- whether custom adapter code was required; and
- an eligibility log hash.

Only then set manifest status to `FROZEN`. The final set must contain at least
10 independent implementations and at least two per claimed class. Freeze the
Git commit before any matched security outcome is read.

## 4. Matched conditions

Every accepted workload runs the same honest, wrong-destination,
extra-destination, content-substitution, hidden-field, replay, TOCTOU,
link/rename, background-writer, silent-no-op, and overlapping-call scenario
where the schema makes that scenario meaningful. The matched conditions are:

1. no defense;
2. response auditor/MBA;
3. task-specific static least privilege;
4. plain container/filesystem sandbox without contract diff; and
5. full MCPGate.

The independent oracle, synthetic input, timeout, repetition count, and
resource limits must be identical across conditions. Unsupported scenarios are
`NOT_APPLICABLE`, not successes or failures.

## 5. Outcomes and statistics

Record mutation attempted, protocol error, authorized effect, unauthorized
effect, completion, false block, UNKNOWN, latency, CPU, and peak memory as
independent fields. Report per-server rows plus server-clustered confidence
intervals. Do not pool nested tool calls as independent observations.

## 6. Integrity rule

The candidate file is planning evidence, not evaluation evidence. The paper
may describe this protocol in future tense until the frozen manifest, raw
results, image IDs, and eligibility hashes are checked in. Any deviation from
the selection or replacement rule must be disclosed before presenting held-out
outcomes.

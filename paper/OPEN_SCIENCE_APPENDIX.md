# Open Science Appendix (Working Draft)

This appendix is written for the USENIX Security 2027 submission requirement.
It must be updated after the release-environment run and before anonymous
upload. Every statement below distinguishes currently available material from
planned release material.

## A. Artifact availability

At submission, the authors plan to provide an anonymous repository containing:

- the MCPGate implementation and integrated filesystem mediator;
- unit, adversarial, ablation, concurrency, and baseline tests;
- compact raw JSON sufficient to regenerate each paper table and figure;
- exact Python and third-party MCP-server dependency locks;
- the Dockerfile, image identifier, invocation metadata, and build/run commands;
- annotation codebook, blank forms, anonymized labels, and scoring code; and
- scripts for quick evaluation and the complete evaluation.

The current working repository is not the anonymous artifact. It contains Git
history and paths that may identify the author and therefore must not be linked
from a double-blind submission.

## B. Claims supported by the artifact

The quick artifact supports:

1. the executable transcript-indistinguishability illustration;
2. effect-oracle separation;
3. controlled response-auditor/gateway baselines;
4. integrated mediator invariants and adversarial regressions;
5. controlled property ablations;
6. local child-process concurrency; and
7. reference and submission-integrity checks.

The full artifact is intended to support:

1. the 8,692 → 4,121 → 1,242 corpus funnel;
2. response-auditor operating points;
3. contract expressibility over the frozen server set;
4. the pinned third-party-server integrated mediator run;
5. held-out baseline and robustness evaluation; and
6. all final performance and confidence-interval figures.

## C. Quick evaluation

Expected runtime on the development machine is under two minutes after
dependencies are installed:

```bash
python scripts/run_quick_artifact.py
```

The command creates a timestamped result directory with:

- exact command lines and exit codes;
- stdout and stderr logs;
- wall-clock duration;
- Git commit and dirty-state indicator;
- Python/platform and direct-package versions; and
- a SHA-256 manifest.

The checked-in development run is not a release result because its Git state is
dirty and it was produced on Windows. The anonymous release must contain a
clean, pinned Linux run.

## D. Full evaluation

The full evaluation must run on an isolated Linux/Docker host. Unvetted MCP
packages must never run directly on a credential-bearing host. The integrated
real-server runner:

- builds a fresh Git-revision/version-tagged image;
- verifies the locked npm package version and registry SHA-512 integrity;
- disables runtime networking;
- uses a read-only container root and bounded tmpfs workspaces;
- drops all capabilities before adding only those required by the trusted
  adapter; and
- records the Git state, Docker version, image ID, host platform, exact package
  version/integrity, and complete command.

The release instructions must state expected hardware, disk use, network use,
and wall-clock time separately for quick and full modes.

## E. Data and provenance

For each reported table and figure, the release must provide:

- compact raw rows or a documented aggregate when redistribution is not
  possible;
- a schema that defines attempted, protocol-error, authorized-effect,
  unauthorized-effect, completion, and UNKNOWN fields independently;
- exact input hashes and byte lengths;
- the transformation command and software environment; and
- the regenerated table/figure hash.

Existing hashes of unavailable local traces are provenance aids, not a
substitute for data release. The paper will not claim fresh-clone
reproducibility until an evaluator can regenerate every result named in the
claim–evidence matrix.

## F. Annotation materials

The release will include the frozen 265-item Round-2 sample, labeling codebook,
two independently completed anonymized label files, scorer, agreement result,
adjudication policy, and classifier report. If redistribution of source text is
restricted, the artifact will include stable record identifiers, hashes, and
the maximum redistributable context, with the limitation stated explicitly.

## G. Licensing and maintenance

Before release, the authors must audit:

- the repository license;
- licenses for copied/adapted scripts and third-party server packages;
- whether registry metadata and server identifiers may be redistributed; and
- a durable archival location and DOI for the camera-ready artifact.

No archival DOI or long-term maintenance commitment is claimed yet.

## H. Current reproducibility gaps

As of 2026-09-25, the following remain open:

- the integrated Docker result must be repeated from a clean release commit;
- several historical raw M3–M5 traces are gitignored;
- the frozen 10-server workloads have not completed the matched five-condition
  evaluation; and
- Round-2 human annotation is blank.

These are submission blockers, not post-acceptance cleanup items.

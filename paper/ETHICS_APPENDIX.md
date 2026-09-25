# Ethics Appendix (Working Draft)

## A. Research purpose and risk

This work studies whether untrusted Model Context Protocol (MCP) server
implementations can produce effects that differ from a client's approved call,
and evaluates client-controlled containment/admission mechanisms. The work can
improve defenses, but the attack descriptions and tampering proxy also show how
to divert tool effects and conceal the diversion behind an honest-looking
response. We therefore minimize operational detail not required for
reproduction and run third-party code only in isolated environments.

## B. Third-party software execution

The corpus includes publicly discoverable MCP packages. Package inclusion is
not an allegation of malicious intent. Experiments apply controlled mutations
or wrappers to pinned versions and report what the experimental configuration
did; they do not label maintainers or projects as malicious.

Unvetted packages must run in disposable containers with:

- no host secrets or credentials;
- no host filesystem mount except an explicitly scoped scratch/result path;
- non-root server execution;
- resource and process limits;
- no runtime network for the final integrated probe unless a specific
  experiment requires and documents it; and
- complete logging of package identity and resolved version.

The historical registry-scale study intentionally excluded servers requiring
credentials. This reduces risk but creates a strong selection effect: results
must not be generalized to credentialed, high-value services.

## C. External effects and network safety

The mechanism's trusted-state admission guarantee does not imply that an
unconfined server caused no external effect. One historical path-diversion
trial wrote to `/tmp/exfil.dat` inside the disposable container. A separate
experiment demonstrated that a filesystem-only mediator cannot observe a local
socket exfiltration channel. These results are disclosed as limitations.

No experiment should contact real users, send real email, alter a production
repository, initiate a financial transaction, or transmit captured secrets.
Network-dependent experiments must use researcher-controlled local endpoints
or documented test services and synthetic data.

## D. Data collection and privacy

The dataset consists of public registry/package metadata, tool declarations,
synthetic arguments, execution status, and filesystem observations. The study
does not intentionally collect personal data. Logs may nevertheless contain
unexpected package output, absolute paths, usernames, hostnames, tokens, or
other secrets. Before release, a scripted and manual redaction audit must scan
raw logs and result bundles; files with unresolved sensitive content must be
excluded with their omission documented.

The artifact must not expose local usernames, institution paths, Git author
metadata, API keys, `.env` files, package-manager credentials, or reviewer
tracking links.

## E. Human annotation

Round-2 validation requires two independent annotators. Participation should be
voluntary, the task should not expose annotators to private data, and the paper
should disclose annotator relationship/compensation in aggregate. Raw labels
will be anonymized. Disagreement will be reported before adjudication, and no
label will be changed merely to cross a pre-registered kappa threshold.

If annotators are students under the authors' supervision, the authors should
avoid coercion and document how participation and compensation were separated
from grading or employment evaluation.

## F. Disclosure and project identifiers

The experiments currently describe behavioral limits across server classes and
do not establish a remotely exploitable vulnerability in a named maintainer's
production deployment. If the final pinned runs reveal a specific new
vulnerability or unsafe default, the authors will privately notify the
maintainer with reproduction details and a reasonable remediation period before
public release. The paper will distinguish vulnerable behavior from malicious
intent.

Server names and exact versions improve reproducibility but can create
reputational risk. The final manuscript should name a project only when the
behavior is necessary evidence, reproducible on a pinned public release, and
described neutrally. Aggregate results should be preferred where identity adds
no scientific value.

## G. Dual use and release scope

The release will include attack harnesses needed to reproduce path/content
diversion, replay, and the tested TOCTOU failure. It will not include real
credentials, target lists, persistence mechanisms, or tooling for deploying
attacks outside the isolated harness. The artifact documentation will place the
safety boundary before all full-evaluation commands.

## H. Research integrity

Automated tools assisted with code and manuscript preparation. Human authors
remain responsible for every claim, result, citation, and released artifact.
The repository enforces three safeguards:

- manuscript citations may use only primary-source-verified bibliography keys;
- the claim–evidence matrix marks READY, QUALIFIED, OPEN, and RETIRED claims;
  and
- the submission checker exits non-zero while open claims, P0 gates, or
  manuscript evidence markers remain.

No pending experiment may be described in the past tense, and no missing result
may be filled with a plausible number.

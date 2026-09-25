# Venue and Writing Standard

## Decision

The primary target is USENIX Security 2027, Cycle 2. The paper is a systems
security paper about confining untrusted MCP tool servers, binding approved
requests to independently observed effects, and evaluating the mechanism on
real implementations. This is a closer fit to USENIX Security than a general
AI venue because the central contribution is an enforcement boundary and its
security evaluation, not a new language model.

The official deadline and format were checked on 2026-09-26:

- mandatory registration: 2027-01-19, Anywhere on Earth;
- paper submission: 2027-01-26, Anywhere on Earth;
- artifact submission: 2027-01-29, Anywhere on Earth;
- body limit: 13 pages, excluding references and appendices;
- format: official USENIX two-column template, US letter, 10 point Times;
- review: anonymous;
- Open Science appendix: required; and
- Ethics appendix: strongly encouraged.

Official source:
<https://www.usenix.org/conference/usenixsecurity27/call-for-papers>

The current `paper/latex` tree already uses the USENIX style. It remains a
working source until every result gate in `paper/CLAIM_EVIDENCE_MATRIX.md` is
closed.

## Published papers used as structural models

These papers are used to study organization and evidence presentation. Their
text is not copied.

1. **Logic Gone Astray: A Security Analysis Framework for the Control Plane
   Protocols of 5G Basebands**, USENIX Security 2024, Distinguished Paper.
   It presents the problem and limits of prior approaches, states concrete
   goals and questions, gives a system overview before component details,
   defines the threat model, and reports scale and findings in the abstract.
   <https://www.usenix.org/conference/usenixsecurity24/presentation/tu>
2. **Data Coverage for Guided Fuzzing**, USENIX Security 2024, Distinguished
   Paper. It separates the core idea, implementation, and evaluation. The
   evaluation starts with explicit research questions, names the matched
   baseline and standard environment, reports repeated trials, and includes
   component analysis and overhead.
   <https://www.usenix.org/conference/usenixsecurity24/presentation/wang-mingzhe>
3. **Terrapin Attack: Breaking SSH Channel Integrity By Sequence Number
   Manipulation**, USENIX Security 2024, Distinguished Paper and Distinguished
   Artifact. It states assumptions and limitations early, moves from root
   cause to concrete attacks and implementation evidence, reports repeated
   trials where probability matters, measures deployment prevalence, and
   ends with practical mitigation.
   <https://www.usenix.org/conference/usenixsecurity24/presentation/b%C3%A4umer>

## Paper structure

The 13 page body will use this order:

1. Abstract
2. Introduction
3. Background and problem statement
4. Threat model and security goals
5. Measurement: why response auditing is insufficient
6. MCPGate design
7. Implementation
8. Evaluation methodology
9. Results
10. Limitations and discussion
11. Related work
12. Conclusion

The Open Science and Ethics sections remain appendices. Optional supporting
material cannot carry a fact required to understand or validate a main claim.

## Abstract contract

The abstract is written last. It must contain, in this order:

1. the concrete security problem;
2. why current response based checks and coarse confinement do not solve it;
3. the main design idea;
4. the evaluation corpus and compared conditions;
5. only measured headline results; and
6. the exact claim boundary and principal limitation.

Every number in the abstract must map to a raw artifact and a row in the
claim evidence matrix. Until the matched held out evaluation and independent
human annotation are complete, placeholders remain visibly marked and no
headline number is guessed.

## Writing rules

- Use short, direct sentences and ordinary technical English.
- Give one meaning to each term and use that term consistently.
- Introduce a symbol only when it removes more ambiguity than it creates.
- Do not use decorative dashes, slogan-like fragments, or inflated adjectives.
- Do not write generic claims such as "robust", "comprehensive", "novel", or
  "state of the art" without a precise comparison and evidence.
- Separate observed results, derived conclusions, assumptions, and future work.
- Use past tense only for work that has run and has a pinned artifact.
- Use present tense for design properties demonstrated by code or proof.
- Use future tense for planned network, SQL, or human study work.
- Name negative results. Do not hide UNKNOWN, false blocks, unsupported cases,
  failed servers, or attacks that are not applicable.
- Each paragraph starts with its point and ends with evidence or consequence.
- Each figure must answer one question that is difficult to answer from prose.
- Captions must be understandable without reading the surrounding paragraph.

## Evaluation presentation

The evaluation section begins with a matrix containing research question,
dataset or workload, compared conditions, metric, oracle, and statistical
unit. Each result subsection follows the same sequence:

1. research question;
2. experimental setup;
3. result with uncertainty;
4. interpretation;
5. limitation or alternative explanation.

Servers are the independent clusters. Nested tool calls are not counted as
independent samples. Deterministic cases report exact counts. Race and timing
cases report the frozen number of repetitions, median, p95, p99 where
applicable, and two sided 95 percent confidence intervals.

## Figure standard

All final figures must be vector graphics that LaTeX includes as PDF. Source
must remain editable. The final set is expected to include:

1. trust boundary and threat model;
2. response observation versus effect admission;
3. integrated mediation pipeline;
4. corpus selection and freeze flow;
5. five condition evaluation matrix;
6. detector operating points;
7. held out security and completion results;
8. latency distribution;
9. ablation results; and
10. claim and limitation map.

Figures 7 and 8 must not be generated until matched raw results exist.


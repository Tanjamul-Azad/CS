# Trust, but Cannot Verify

**Execution Integrity and Its Limits in Model Context Protocol Agents**

Group 13 — Md. Tanzamul Azad (0112230863), Jahidul Islam (0112230654)
United International University

---

## What this is

MCP lets a user approve a tool **once**, after which an autonomous agent may invoke it indefinitely without further review. Approval binds trust to the tool's *declaration* — name, description, schema. The security-relevant object is its *implementation*.

This project shows that gap is not merely unaddressed but, for an identifiable class of tools, **unaddressable client-side**; measures how much of the real MCP ecosystem falls in that class; and builds the defense that works for the rest.

**Central result (theory).** No client-side monitor can distinguish an honest server from one that performs a malicious effect while returning an honest response, whenever the tool's effect is not observable through an independent channel. This invalidates the entire response-validation family — including the defense this project originally proposed.

## Repository map

```
docs/          research program — start with 00-RESEARCH-PLAN.md
src/mcpmut/    MCP-MutBench: harness, mutation engine, defenses, oracle
src/measure/   registry harvester + V-class classifier
src/analysis/  statistics and figure generation
data/          corpus and benchmark definitions
experiments/   configs, results, logs
paper/         LaTeX source, figures, bibliography
```

## Documents

| Doc | Contents |
|---|---|
| [00-RESEARCH-PLAN.md](docs/00-RESEARCH-PLAN.md) | Master plan, thesis, contributions |
| [01-literature-review.md](docs/01-literature-review.md) | 24 works, organized by what each verifies |
| [02-gap-analysis.md](docs/02-gap-analysis.md) | The I×E grid and the empty quadrant |
| [03-novelty-contributions.md](docs/03-novelty-contributions.md) | Novelty audit, reviewer rebuttals, draft abstract |
| [04-threat-model.md](docs/04-threat-model.md) | Adversary tiers T0–T3 |
| [05-verifiability-taxonomy.md](docs/05-verifiability-taxonomy.md) | **Theory core** — Theorem 1, classes V0–V3 |
| [06-dataset-plan.md](docs/06-dataset-plan.md) | Building D1/D2 from nothing; labeling protocol |
| [07-experiment-plan.md](docs/07-experiment-plan.md) | RQs, matrix, statistics, power |
| [08-figures-plan.md](docs/08-figures-plan.md) | Every figure and the claim it carries |
| [09-venue-timeline.md](docs/09-venue-timeline.md) | Venue strategy, milestones |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env    # add your own keys; .env is gitignored
```

## Status

Design complete; implementation starting. See [00-RESEARCH-PLAN.md](docs/00-RESEARCH-PLAN.md) §7.

## Security note

Earlier exploratory notebooks in this project contained hardcoded API keys. Those keys are revoked and no secret is tracked in this repository. All credentials load from `.env`.

## License

Research code, released for reproducibility. See `LICENSE`.

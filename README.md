# The Price of a Lie

**Auditing Untrusted Tool Servers Without Their Cooperation**

Group 13 — Md. Tanzamul Azad (0112230863), Jahidul Islam (0112230654)
United International University

---

## What this is

MCP lets a user approve a tool **once**, after which an autonomous agent may invoke it indefinitely without further review. Approval binds trust to the tool's *declaration* — name, description, schema. The security-relevant object is its *implementation*, and nothing binds the two.

**Theorem 1.** A *passive* client — one that inspects responses — cannot detect a server that performs a malicious effect while returning the honest response. Detection rate equals false-positive rate. This invalidates the entire response-validation family, including the defense this project originally proposed.

**The escape.** The client is not passive. It is authorized to *call*. Metamorphic relations derived automatically from tool declarations force a diverting server to maintain a consistent shadow world — a simulated honest server running in parallel. That burden is measurable, and it is the security argument.

**Hard constraint:** zero cooperation. No signed receipts, no attestation, no independent channel, no help from the server or any downstream provider. Only tools the client was already approved to use. Anything else does not get deployed.

## The result, in one table

Every variant below steals money through an approved tool whose declaration never changed — hash pinning is blind to all of them:

| Adversary | Attacker LOC | Caught by |
|---|---|---|
| M5 forge response | 3 | R1 write-read |
| M7 + shadow ledger | 9 | R2 conservation |
| M8 + shadow balance | 17 | **nothing** |

Defenses do not stop the attacker. They **price** them. M8 wins and Theorem 1 says it always will — that is the honest ceiling. The contribution is the slope below it, plus the fact that documented real MCP compromises are M5-class one-line patches maintaining no shadow state at all.

```bash
python experiments/demo_mba.py       # no API key needed
```

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
| [05-verifiability-taxonomy.md](docs/05-verifiability-taxonomy.md) | **Theory core** — Theorems 1 & 2, classes A0–A3 |
| [06-dataset-plan.md](docs/06-dataset-plan.md) | Building D1/D2 from nothing; labeling protocol |
| [07-experiment-plan.md](docs/07-experiment-plan.md) | RQs, matrix, statistics, power |
| [08-figures-plan.md](docs/08-figures-plan.md) | Every figure and the claim it carries |
| [09-venue-timeline.md](docs/09-venue-timeline.md) | Venue strategy, milestones |
| [10-implementation-notes.md](docs/10-implementation-notes.md) | Code architecture |
| [11-runtime-validation-design.md](docs/11-runtime-validation-design.md) | **MBA — the zero-cooperation defense** |
| [12-intellectual-lineage.md](docs/12-intellectual-lineage.md) | The 11 fields we inherit from, and what breaks |

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

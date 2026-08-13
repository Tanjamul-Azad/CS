# D1 Findings — Ecosystem Measurement

**Status: INTERIM.** n = 1,153 tools / 67 servers, from 130 of 500 discovered repositories. Harvest still running. Numbers will shift; the *direction* of every effect below is already large enough that it is unlikely to reverse, but nothing here is final and none of it has passed κ validation yet.

Supersedes `docs/13`, which measured only the official reference repo and is now best understood as the *best-case* control arm.

---

## 1. The headline

**62.0% of MCP tools have relation degree 0** (95% CI 59.2–64.8, n=1,153).

No client-side audit detects their compromise at any cost. Not with a bigger budget, not with a smarter checker — Theorem 1 applies and there is no relation to check. For these tools the remedy is policy: restrict the call, or put a human in front of it.

| Class | n | % | 95% CI |
|---|---|---|---|
| **A0** unrelatable | 715 | **62.0%** | 59.2–64.8 |
| A1 self-relatable | 106 | 9.2% | 7.7–11.0 |
| A2 read-backable | 326 | 28.3% | 25.8–30.9 |
| A3 invariant-bound | 6 | **0.5%** | 0.2–1.1 |

---

## 2. The finding that reframes the paper: official ≠ ecosystem

| | Official reference (n=43) | Community (n=1,153) | Ratio |
|---|---|---|---|
| **A0 rate** | 9.3% | **62.0%** | **6.7×** |
| `readOnlyHint` declared | 74.4% | **2.6%** | 29× |
| `destructiveHint` declared | 51.2% | 1.9% | 27× |
| `idempotentHint` declared | 51.2% | 1.6% | 32× |
| `outputSchema` present | 30.2% | **0.0%** | — |
| `inputSchema` present | ~100% | 54.9% | — |

Every prior MCP security paper that evaluates on reference servers is evaluating on the most favourable 3% of the ecosystem. This is a concrete, quantified instance of a general methodological problem, and it is worth stating plainly: **the servers researchers test on are not the servers users run.**

### 2.1 MCP's behavioral annotations are effectively unused

`docs/13` framed these hints as "self-declared by the audited party, therefore unverifiable." That critique stands, but it turns out to be **almost moot in practice**: only 2.6% of tools in the wild declare `readOnlyHint` at all.

The story is therefore not *"the protocol trusts the attacker's self-report"* so much as *"the protocol's one behavioral channel is dead on arrival."* Both are findings. The second is the bigger one, and it inverts the framing from `docs/13` — which is exactly why that document is superseded rather than merely extended.

Consequence for our method: the classifier's reliance on self-declared hints is far smaller than feared. **Dual derivation moves only 1.6 points** (A0 62.0% → 63.7% when hints are ignored). Measured auditability is not resting on the attacker's word, because the attacker's word is almost never given. That is a much stronger position than we expected to be in.

### 2.2 No output schemas at all

`outputSchema` on **0.0%** of community tools (0/1,153).

This directly caps what can be derived. Without knowing what a read returns, a client cannot mechanically check that a write is reflected in it, so R1 falls back to matching name and description vocabulary — weaker and noisier. A large share of the 62% A0 rate is likely *caused* by this absence rather than by any deep property of the tools.

**That reframes the finding as actionable rather than merely grim:** it implies a concrete, cheap, unilateral protocol recommendation — *mandate or strongly encourage `outputSchema`* — which would move tools out of A0 at essentially no cost to server authors. It is rare for a measurement paper to hand the ecosystem a fix this specific.

---

## 3. Conservation is essentially absent

**4 R2 relations across the entire corpus. A3 = 0.5%.**

R2 is the strongest relation class: it constrains a *global* quantity and is the hardest thing for an attacker to fake, because doing so requires simulating the honest system's arithmetic (the 17-LOC rung of the ladder). In the wild it is nearly unavailable.

`docs/13` flagged A3=0 as possibly an instrument artifact. That explanation is now much weaker: the inline-schema bug is fixed, input-field resolution went 23% → 72% on the reference corpus, and R2 is no longer gated behind R1. Conservation still barely appears. The likeliest reading is now **real**: most MCP servers expose file, search, and API-wrapper tools with no conserved numeric quantity. Banking-style invariants are the exception, not the rule.

Still requires κ validation before being claimed.

---

## 4. Tool-count hypothesis: NOT confirmed

`docs/13` predicted A0 rate would fall monotonically as servers ship more tools, since relations are derived between siblings. It does not:

| tools/server | servers | tools | A0 rate |
|---|---|---|---|
| 1 | 12 | 12 | 83.3% |
| 2–3 | 6 | 16 | 87.5% |
| 4–7 | 19 | 101 | 65.3% |
| 8–15 | 9 | 106 | 45.3% |
| **16+** | 21 | 918 | **62.9%** |

It falls through 8–15, then **rises again** for large servers.

The mechanism is visible in the per-server table: large servers are often *bundles of unrelated tools* — `MCP-Open-Discovery` (65 tools, 61 A0), `prometeo-mcp` (27 tools, 26 A0) — rather than cohesive services. Adding tools only helps if they touch the same resource.

This suggests the right predictor is not tool count but something like **resource cohesion**: how many tools share a resource with at least one sibling. Worth constructing and testing properly, and worth reporting as a corrected hypothesis rather than quietly dropping — the naive version was ours and it was wrong.

---

## 5. Declaration idioms

| Idiom | n | % |
|---|---|---|
| Python FastMCP decorator | 531 | 46.1% |
| TS object literal | 214 | 18.6% |
| JSON manifest | 163 | 14.1% |
| TS `registerTool` | 101 | 8.8% |
| TS `server.tool` | 97 | 8.4% |
| Python `types.Tool` | 47 | 4.1% |

Python FastMCP dominates. Since that path is AST-based and reliable, extractor confidence is higher than a regex-heavy pipeline would suggest — but recall on the TS idioms (35.8% combined) is still unmeasured against real code and remains a live limitation.

---

## 6. What must close before any of this is claimed

| # | Item | Why it blocks |
|---|---|---|
| 1 | **Finish the harvest** (130/500 repos) | n and CIs are provisional |
| 2 | **κ validation**, 300 tools, 2 annotators | classifier accuracy unmeasured; A0 bias unknown |
| 3 | **Extractor recall on real code** per idiom | a systematic miss biases the headline |
| 4 | Resource-cohesion metric | replaces the falsified tool-count hypothesis |
| 5 | Sampling-frame bias audit | GitHub-only; npm/PyPI-only servers invisible |

Item 2 is the hard blocker. Until the classifier is scored against a human gold standard, 62.0% is an instrument reading, not a measurement.

---

## 7. Reproduce

```bash
python experiments/run_d1.py --target 500 --resume
python experiments/run_d1.py --report-only
```

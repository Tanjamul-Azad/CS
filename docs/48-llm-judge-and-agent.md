# 48 — Workstreams F and I: an LLM judge, and a real agent end to end

Plans: `artifact/llm-judge-plan.json`, `artifact/agent-e2e-plan.json`.
Model for both: OpenAI `gpt-4.1-mini-2025-04-14`, temperature 0. The API key
is read from the environment only; it never enters a container, a log, or the
repository.

## F — an LLM judge as a response-level monitor

The judge sees everything a response-level monitor can see: the approved
call, the server's response, and every read-back the project's response
auditor made to the same server. It never sees the trusted snapshot.
Transcripts: `artifact/results/llm_judge_transcripts.json` (five filesystem
servers; honest x3; each applicable attack under a naive and a consistent
adversary). Verdicts: `artifact/results/llm_judge.json`.

| Transcripts | Judge said UNSAFE | Wilson 95% |
|---|---:|---|
| honest (false positives) | 8 / 15 = 53% | 30–75% |
| landed attacks, naive adversary | 13 / 21 = 62% | 41–79% |
| landed attacks, consistent adversary | 12 / 21 = 57% | 37–76% |

The judge's detection rate cannot be told apart from its false-positive rate,
for either adversary: the three intervals overlap almost entirely. It flags
benign warnings in honest responses (for example ori-memory's "missing
description" notices) about as often as real diversions. This is the
observation boundary with a third-party-style detector instead of our own
auditor: more capable reading of the same evidence does not create a witness.
Estimated spend: USD 0.015.

Prediction stated in advance: consistent-tier detection indistinguishable from
the false-positive rate. Met. The naive tier did not come out clearly better
either, because the judge's high false-positive rate swamps any signal.

## I — a real agent end to end

An OpenAI function-calling agent on the host drives two real MCP filesystem
servers (Python and Node) that run in their frozen images with no network and
the staging directory as the only writable mount. Twelve file-writing tasks,
each run against an honest server and a compromised one (consistent tier;
content, path, or extra-object diversion by task). Each agent tool call is
auto-approved; after the session, the staged tree is judged as-is (no defense)
and through session-level EffectSeal admission, whose contract is the pin-time
template (workstream A) instantiated with the agent's own write calls.
Result: `artifact/results/agent_e2e.json`.

| 24 episodes per row | No defense | EffectSeal |
|---|---:|---:|
| honest task completed | 24 / 24 | **24 / 24** (0 false blocks) |
| compromised: harmful effect in trusted state | 24 / 24 | **0 / 24** |
| compromised: the agent reported any problem | 0 / 24 | — |

- The agent never noticed the compromise: the consistent server's responses
  were honest, so the agent reported success every time.
- EffectSeal refused every compromised session and admitted every honest one;
  median admission time 0.14 ms (excluding the container, which dominates).
- Caveats: both servers are exact (0-bit) template servers, the easy case;
  admission is session-level (all write calls of a task checked together after
  the session), not per call; a refused compromised session leaves the task
  undone (fail closed), which is correct but is a lost task.

Estimated spend: USD 0.041 (F and I together about USD 0.06 of the USD 5 limit).

## F (second baseline) — call-level authorization in the style of Progent

`experiments/run_calllevel_baseline.py`, result `artifact/results/calllevel_baseline.json`.
The strictest reasonable pre-execution policy per workflow: only the approved
tool, no argument outside the schema, every path argument directly under
`/sandbox` with the approved extension. Implemented from Progent's published
semantics, not with its code. Applied to the recorded requests of F's
transcripts and I's agent episodes (no new runs, no API calls).

| | Call-level policy | EffectSeal |
|---|---:|---:|
| honest transcripts blocked | 0 / 15 | 0 |
| landed attacks prevented (transcripts) | **0 / 42** | 22 / 22 on the same servers and scenarios (matched evaluation) |
| agent: honest tasks completed | 24 / 24 | 24 / 24 |
| agent: compromised harm reaching trusted state | **24 / 24** | **0 / 24** |

This is close to true by construction, and that is the point: a rug-pulled
server receives exactly the approved request and changes only the effect, so
any policy that decides on the request, however strict, admits it. Authorizing
calls and admitting effects are different properties.

## Scale-up runs (v2), registered before running

### F v2 — three judges, larger sample (`artifact/results/llm_judge_v2.json`)

176 transcripts (50 honest; 63 landed attacks per adversary tier), judged by
gpt-4.1-mini, gpt-4.1, and gpt-5-mini. Raw rates (flagged UNSAFE):

| Judge | Honest | Naive | Consistent |
|---|---:|---:|---:|
| gpt-4.1-mini | 22/50 | 35/63 | 24/63 |
| gpt-4.1 | 0/50 | 31/63 | 12/63 |
| gpt-5-mini | 12/50 | 38/63 | 27/63 |

Split by whether the attacked transcript was actually indistinguishable from an
honest one — decided without any judge, by comparing normalized responses and
read-backs with the same server's honest transcripts
(`experiments/analyze_judge_leaks.py`; the split is post hoc, its criterion uses
no verdict):

| Judge | Honest FPR | Consistent, indistinguishable | Consistent, leaked |
|---|---:|---:|---:|
| gpt-4.1 | 0/50 | **0/42** | 12/21 |
| gpt-5-mini | 12/50 (24%) | 9/42 (21%) | 18/21 |
| gpt-4.1-mini | 22/50 (44%) | 15/42 (36%) | 9/21 |

Where the adversary kept the transcript honest, every judge's detection rate
equals its own false-positive rate; a stronger judge helps only where the
evidence differs, and whether it differs is the attacker's choice. Our
interposition adversary leaked in 21/63 consistent transcripts (a Python
server's directory scan that the shim does not wrap, and a no-op that surfaced
an error); a better attacker would leak less. Spend USD 0.71.

### I v2 — harder servers and a second agent model (`artifact/results/agent_e2e_v2.json`)

Five servers (two exact filesystem servers plus compose-mcp, repomemory, and
ori-memory, whose templates have slack) x 12 tasks x honest/compromised x two
agent models (gpt-4.1-mini, gpt-4.1). 226 of 240 planned episodes ran: the host
`ori init` setup container timed out before ori-memory's gpt-4.1 task 5 and
ended the run (a setup failure, not an agent, server, or admission outcome).

| 113 episodes per row | No defense | EffectSeal |
|---|---:|---:|
| honest task completed | 109 | **108** (1 false block, repomemory) |
| compromised: harm reached trusted state | **113 / 113** | **0 / 113** |
| compromised: agent reported any problem | 8 / 113 | — |

Per server and model, harm with EffectSeal is 0 everywhere, including the three
servers whose templates have slack. Four honest ori-memory tasks failed without
any defense too (the agent's call did not produce the requested title). Spend
USD 1.31. Total API spend for workstreams F and I: about USD 2.1 of the USD 5
limit.

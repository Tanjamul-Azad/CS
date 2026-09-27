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

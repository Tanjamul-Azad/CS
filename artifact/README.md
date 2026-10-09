# EffectSeal artifact

This artifact accompanies the paper *Faithful Responses, Faithless Effects:
Verified-Effect Admission for Tool-Using LLM Agents on Untrusted MCP Servers*.
It contains the mediator and broker, template inference, both TLA+ models, every
evaluation harness, the frozen server manifests, the pre-registration plans, and
compact per-cell result files for every number in the paper.

`paper/CLAIM_EVIDENCE_MATRIX.md` maps each claim in the paper to the result file
that supports it.

## 1. Quick reproduction (Linux, no Docker inside, no API keys)

From the root of a fresh clone:

```bash
python -m pip install --require-hashes -r artifact/requirements-full-linux.txt
sh scripts/reproduce_clean_linux.sh
```

or, in a throwaway container:

```bash
docker run --rm -v "$PWD:/src-repo:ro" -v "$PWD/out:/out" python:3.12-slim sh -c \
  'apt-get update -qq && apt-get install -y -qq git >/dev/null &&
   git config --global --add safe.directory "*" &&
   git clone -q /src-repo /work && cd /work && OUT=/out sh scripts/reproduce_clean_linux.sh'
```

The script writes one log per step and `summary.txt`. It runs the test suite,
both TLA+ model checkers, the transcript-indistinguishability demonstration, the
mediator ablations, the 100-trial allowance races (local and network), the
network overhead measurement, the file-arm baseline mapping, and regenerates
every paper figure from the checked-in results. Every step should print `PASS`.
On our machine the whole run, including the dependency install, takes about
ten minutes.

## 2. Full reproduction (Docker)

Third-party servers are untrusted code. Run them only through the provided
harnesses, which start each server in a container with no network (local-state
servers) or with the broker as its only route (network servers), all Linux
capabilities dropped, a read-only image, and resource limits. Never mount host
credentials.

| Paper result | Command | Result file(s) |
|---|---|---|
| Registry share of local and remote servers | `python experiments/measure_local_remote.py` | `artifact/results/m1_local_remote_2026-10-08.json` |
| Release churn and maintainer concentration | `python experiments/measure_rugpull_exposure.py` | `artifact/results/m2_rugpull_exposure_2026-10-09.json` |
| Response auditor over the registry | `experiments/run_scale.py`, `experiments/analyze_operating_points.py` | `results/tables/operating_points.md` |
| LLM judges (three OpenAI models) | `python experiments/run_llm_judge.py judge --version v2` (needs `OPENAI_API_KEY`) | `artifact/results/llm_judge_v2.json` |
| LLM judge (local Llama 3.1 8B) | `python experiments/run_llm_judge_ollama.py --version v2` | `artifact/results/llm_judge_ollama_v2.json` |
| Judge-free leak split | `python experiments/analyze_judge_leaks.py` | `artifact/results/llm_judge_v2_leak_split.json`, `llm_judge_ollama_v2_leak_split.json` |
| Local state, five matched conditions | `python experiments/run_matched_filesystem.py`, `run_matched_sql.py` | `artifact/results/matched_filesystem.json`, `matched_sql.json` |
| Pin-time templates, development and held-out | `experiments/run_template_generalization.py`, `run_batch2_templates.py` | `artifact/results/template_generalization*.json`, `batch2_templates.json` |
| Second held-out batch (no eligible server) | `python experiments/run_batch3_pipeline.py workflow`, then `manifest` | `artifact/held-out-batch3-manifest.json` |
| Network selection by rule | `python experiments/network_select_servers.py` | `artifact/results/network_selection_20261008-225940/` |
| Network matched evaluation | `python experiments/network_matched_eval.py --selection <dir>` | `artifact/results/network_matched_20261008-234304/` |
| Postmark incident and real tools | `network_postmark_pilot.py`, `network_postmark_toolhive.py`, `network_postmark_agentbound.py`, `network_postmark_mcpscan.py` | `artifact/results/network_postmark_*` |
| Live check against the real Postmark API | `python experiments/network_postmark_live_replay.py` | `artifact/results/network_postmark_live_20261009-170400.json` |
| Official GitHub server | `python experiments/network_named_demo.py` | `artifact/results/network_named_20261009-000146/` |
| Agents, local state | `run_agent_e2e_v2.py` (OpenAI key); `run_agent_e2e_ollama.py` (local) | `artifact/results/agent_e2e_v2.json`, `agent_e2e_llama.json` |
| Agents, network | `network_rq5_agents.py` (OpenAI key, or `--base-url` for a local model) | `artifact/results/network_rq5_*` |
| Network overhead and races | `python experiments/measure_network_overhead.py` | `artifact/results/network_overhead_races.json` |
| File-arm baselines | `python experiments/make_file_baselines.py` | `artifact/results/file_baselines.json` |
| TLA+ models | `python formal/check_model.py`, `python formal/check_net_model.py` | `formal/tlc/*.log` |

Notes:

- Network experiments run against recording mocks of each API, so no vendor
  account or key is needed. The live Postmark check sends about thirty requests
  to the real Postmark API with its documented test token, which validates a
  request without delivering email; a guard refuses any other token or host.
- The postmark-mcp attack versions are built from the official MIT-licensed
  source with a one-feature change each. The malicious npm package is never
  downloaded.
- The ToolHive driver also needs `mcp==2.1.1` and the `thv` binary (version
  0.51.4); the AgentBound driver builds the AgentBound sandbox image from its
  published artifact (doi 10.5281/zenodo.19571298).
- Local-model runs use Ollama with the model defined in
  `artifact/baselines/ollama/Modelfile.llama3.1-32k` (Llama 3.1 8B, context
  32768, temperature 0): `ollama create llama3.1-32k -f <that file>`.
- The registry crawl traces contain third-party output and are not
  redistributed; the artifact ships the aggregate tables and the hashes of the
  raw traces.

## 3. Pre-registration

Every scored run has a plan committed before it: `artifact/*-plan.json` and
`paper/NETWORK_PREREG_V2.md`, with later changes recorded as dated amendments.
Development runs that preceded a change are kept under their own names, and no
result file of an earlier run is overwritten.

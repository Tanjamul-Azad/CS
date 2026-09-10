# Attempted vs happened vs detected

Ground truth for every detection rate in the project. The old `attack_landed` flag meant only that the proxy selected a target field. Here the old label would count 2 of these while 3 carry a real unauthorized effect -- and one reports a protocol error AND leaves a forbidden write behind, which is why excluding errored trials is also wrong. Only observation is ground truth.

| Behaviour | Mutation attempted | Protocol error | Authorized effect | Unauthorized effect | Unknown | Detector violation |
|---|---|---|---|---|---|---|
| honest | - | - | yes | - | - | - |
| divert_path | yes | - | - | yes | - | yes |
| substitute_content | yes | - | - | yes | - | - |
| silent_noop | - | - | - | - | yes | - |
| refuse | - | yes | - | - | yes | - |
| error_but_writes | yes | yes | - | yes | - | yes |

*Source: `data/processed/effect_oracle.json`. Regenerate with `python experiments/make_results.py`.*

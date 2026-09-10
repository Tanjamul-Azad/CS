# Real attacks the detector discarded

Found by auditing our own detector: attacks that landed, where the tampered trial fired and the honest trial did not - real catches - reported only as warnings and therefore scored zero. The third row is the attacker's exfiltration path visible in the reader's own output.

| Server | Write tool | Diverted field | Alert |
|---|---|---|---|
| dev.useaxis/axis | update_context | filename | [WARNING] update_context / R1: read_context reports the target of this write does not exist, yet the response claimed success (weak pairing: read_cont |
| io.github.KVANTRA-dev/NOUZ-MCP | write_file | path | [WARNING] write_file / R1: read_file reports the target of this write does not exist, yet the response claimed success (weak pairing: read_file shares |
| io.github.Semiotronika/NOUZ-MCP | write_file | path | [WARNING] write_file / R1: read_file reports the target of this write does not exist, yet the response claimed success (weak pairing: read_file shares |
| io.github.domdomegg/filesystem-mcp | create | path | [WARNING] create / R1: view reports the target of this write does not exist, yet the response claimed success (weak pairing: view shares only a resour |
| io.github.parnasheps-eng/dark-search-protocol | add_source | url | [WARNING] add_source / R1: wrote ["url=https://example.test/ahmahv (read-back shows url in ['/tmp/exfil.dat'], none match)"] but list_sources does not |

*Source: `data/processed/pilot_pre_r7_baseline.json`. Regenerate with `python experiments/make_results.py`.*

# M2 proper - the untrusted server performs its own effect

Closes the gap `boundary_probe` (the preliminary control) left open: here the SERVER itself writes into an isolated staging workspace it owns (0700), no executor in the path; a trusted mediator diffs the workspace against the contract and only then copies the approved file into a separate committed store the server has zero permission on. Prevention coverage 10/10, same as the preliminary probe -- but `blocked by` FLIPS: 8/10 by the contract check (staging diff), only 2/10 (rename_after_write, hardlink) by OS permission, and only because those permissions protect the COMMITTED store, not the server's own writable workspace. hidden_extra_field COMMITS here (confinement=CONFINED, completion=COMPLETED) -- a pure effect-diff cannot see a request argument that leaves no file-level trace, confirming docs/25 section 3.1's boundary-sees-effects-not-requests limitation on real filesystem state.

| Scenario | Undefended | M2-defended | Completion | Blocked by |
|---|---|---|---|---|
| honest | CONFINED | CONFINED | COMPLETED | not applicable |
| wrong_path | VIOLATED | CONFINED | NOT_COMPLETED | contract check (staging diff) |
| content_substitution | VIOLATED | CONFINED | NOT_COMPLETED | contract check (staging diff) |
| hidden_extra_field | CONFINED | CONFINED | COMPLETED | not applicable |
| same_dir_extra_file | VIOLATED | CONFINED | NOT_COMPLETED | contract check (staging diff) |
| symlink_escape | VIOLATED | CONFINED | NOT_COMPLETED | contract check (staging diff) |
| rename_after_write | VIOLATED | CONFINED | COMPLETED | OS permission (on the committed store) |
| hardlink | VIOLATED | CONFINED | COMPLETED | OS permission (on the committed store) |
| delete_after_write | UNKNOWN | CONFINED | COMPLETED | OS permission (on the committed store) |
| preopened_fd | VIOLATED | CONFINED | NOT_COMPLETED | contract check (staging diff) |
| child_process | VIOLATED | CONFINED | NOT_COMPLETED | contract check (staging diff) |
| background_write | VIOLATED | CONFINED | NOT_COMPLETED | contract check (staging diff) |
| error_after_effect | VIOLATED | CONFINED | NOT_COMPLETED | contract check (staging diff) |
| silent_noop | UNKNOWN | UNKNOWN | NOT_COMPLETED | not applicable |

*Source: `data/processed/boundary_probe_m2.json`. Regenerate with `python experiments/make_results.py`.*

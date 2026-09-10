# Preliminary control experiment - executor-mediated gateway

NOT milestone M2. M2 requires the confined SERVER to perform the effect while a generic boundary enforces the contract; here the gateway performs it through a per-tool executor and the server cannot write at all, so the authorization-to-boundary translation problem is untested. Paired against an undefended control, so prevention is measured over attacks that actually landed: 10/10, with hidden_extra_field and delete_after_write excluded because they never landed even undefended. `Blocked by` matters -- 8 by OS permission, 2 by the contract check. Confinement is not authorization.

| Scenario | Undefended | Defended | Completion | Blocked by |
|---|---|---|---|---|
| honest | CONFINED | CONFINED | COMPLETED | OS permission |
| wrong_path | VIOLATED | CONFINED | NOT_COMPLETED | contract check |
| content_substitution | VIOLATED | CONFINED | NOT_COMPLETED | contract check |
| hidden_extra_field | CONFINED | CONFINED | NOT_COMPLETED | contract check |
| same_dir_extra_file | VIOLATED | CONFINED | COMPLETED | OS permission |
| symlink_escape | VIOLATED | CONFINED | COMPLETED | OS permission |
| rename_after_write | VIOLATED | CONFINED | COMPLETED | OS permission |
| hardlink | VIOLATED | CONFINED | COMPLETED | OS permission |
| delete_after_write | UNKNOWN | CONFINED | COMPLETED | OS permission |
| preopened_fd | VIOLATED | CONFINED | COMPLETED | OS permission |
| child_process | VIOLATED | CONFINED | COMPLETED | OS permission |
| background_write | VIOLATED | CONFINED | COMPLETED | OS permission |
| error_after_effect | VIOLATED | CONFINED | COMPLETED | OS permission |
| silent_noop | UNKNOWN | UNKNOWN | NOT_COMPLETED | not applicable |

*Source: `data/processed/boundary_probe.json`. Regenerate with `python experiments/make_results.py`.*

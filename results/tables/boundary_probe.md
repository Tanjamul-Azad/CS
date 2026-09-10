# M2 - real boundary vs a real adversarial server

An untrusted server running as a separate OS process under a different user, attacking a protected directory it cannot write to. Verdicts come from an observer reading the filesystem, never from the server. Confinement and completion are separate: blocking cannot make a server do work, so a silent no-op is NOT_COMPLETED rather than prevention.

| Scenario | Protocol | Confinement | Completion | Boundary verdict |
|---|---|---|---|---|
| honest | ok | CONFINED | COMPLETED | ALLOWED and performed by gateway |
| wrong_path | ok | CONFINED | NOT_COMPLETED | REFUSED (effect would land elsewhere) |
| content_substitution | ok | CONFINED | NOT_COMPLETED | REFUSED (effect would land elsewhere) |
| hidden_extra_field | ok | CONFINED | NOT_COMPLETED | REFUSED (proposal adds an unapproved field) |
| same_dir_extra_file | ok | CONFINED | COMPLETED | ALLOWED and performed by gateway |
| symlink_escape | ok | CONFINED | COMPLETED | ALLOWED and performed by gateway |
| rename_after_write | ok | CONFINED | COMPLETED | ALLOWED and performed by gateway |
| hardlink | ok | CONFINED | COMPLETED | ALLOWED and performed by gateway |
| delete_after_write | ok | CONFINED | COMPLETED | ALLOWED and performed by gateway |
| preopened_fd | ok | CONFINED | COMPLETED | ALLOWED and performed by gateway |
| child_process | ok | CONFINED | COMPLETED | ALLOWED and performed by gateway |
| background_write | ok | CONFINED | COMPLETED | ALLOWED and performed by gateway |
| error_after_effect | error | CONFINED | COMPLETED | ALLOWED and performed by gateway |
| silent_noop | ok | UNKNOWN | NOT_COMPLETED | ALLOWED (execution skipped by scenario) |

*Source: `data/processed/boundary_probe.json`. Regenerate with `python experiments/make_results.py`.*

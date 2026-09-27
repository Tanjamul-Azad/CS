# 47 — Workstream G: pin-time templates on the second held-out batch

Frozen before the run: `artifact/held-out-batch2-candidates.json` (seeded
order), `artifact/held-out-batch2-manifest.json` (servers and exclusions),
`artifact/batch2-evaluation-plan.json` (protocol, success rule, and SHA-256 of
the inference library, checked by the runner). Result:
`artifact/results/batch2_templates.json`. These four servers were never used
in development.

## Which servers, and why only four

30 candidates were frozen; builds for candidates 18–30 failed when the host
system drive filled, and no new packages are installed on this machine, so
they were not evaluated. Of the first 17, eight answered tools/list in
isolation; one was deferred (needs a PDF fixture) and three could not complete
an honest workflow here (a remote vault credential; an offline embedding
model; state in a SQLite database under `$HOME`, the same exclusion as in the
first held-out set). **Four servers remain: too few for a strong claim, and
reported as such.**

## Results (pre-registered rule: pooled false blocks <= 5%, all landed attacks refused)

| Server | Honest held-out | False blocks | Slack (bits) | Landed attacks | EffectSeal-T | Content-blind |
|---|---:|---:|---:|---:|---:|---:|
| tablestakes | 12 | 0 | unbounded (degenerate) | 0 / 15 | — | — |
| tacitus | 12 | 0 | 374 | 12 / 15 | 12 | 6 |
| aigroup-mdtoword (DOCX) | 12 | **4** | 5,410 | 15 / 15 | 15 | 6 |
| cpersona (SQLite) | 12 | **2** | unbounded | 12 / 12 | 12 | 4 |
| **Total** | **48** | **6 (12.5%)** | | **39** | **39 (100%)** | **16 (41%)** |

- **Security criterion met:** every landed attack was refused (39/39); binding
  content matters (the content-blind ablation refused 16/39).
- **Utility criterion failed:** 6/48 honest calls were falsely blocked
  (12.5% > 5%).
- **Pin-time policies are not usable as designed:** every honest held-out
  template fails both the 128-bit budget and the structural policy, so either
  policy would refuse to pin all four servers.

## Why, server by server

- **tablestakes:** the perturbed `content` was no longer a markdown table; the
  server then wrote nothing *without returning an error*, so pin-time field
  discovery (which reacts to errors) did not hold the field fixed. Training runs
  sometimes wrote a file and sometimes not, and the template degenerated to "zero
  or one arbitrary .md file". No attack had anything to land on. Lesson: a
  silent no-op under perturbation is indistinguishable from a valid call at pin
  time; perturbation needs a validity check (did the honest run produce an effect?).
- **aigroup-mdtoword:** all four false blocks are the 3x-longer-text calls; the
  DOCX canonical view exposes XML whose structure changes with text length
  (paragraph and run splitting) that four training runs did not cover. Slack is
  large (5.4 kbits) because most of the document XML is hole.
- **cpersona:** SQLite writes sometimes leave `-wal`/`-shm` sidecar files and
  sometimes do not; both false blocks come from that nondeterminism, and the
  sidecars make slack unbounded. The canonical view reads the main file only.
- **tacitus:** clean on honest calls; slack is an audit log and a
  history file named by a content hash (192 bits).

## What this means for the paper

The development set (doc 46: 1/84 false blocks) was optimistic. On unseen
servers the template **mechanism stays sound** (no landed attack admitted) but
**utility and tightness degrade** for container formats, nondeterministic sidecar
files, and inputs whose validity the perturbation cannot preserve. The honest
framing is: pin-time templates are a conservative contract source with a
measured, per-tool slack; they are tight for plain file and row effects and
loose (or failing closed) for structured containers. The pin-time policy
question is open.

The library was not changed after seeing these results. Fixes suggested by
this run (effect-validity check during pin-time perturbation, sidecar-aware
SQLite view, more training variety for long text) would start a new
development cycle and need a fresh held-out batch.

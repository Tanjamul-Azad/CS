# Labeling Codebook — Auditability Classes A0–A3

**Purpose.** Produce a human gold standard against which the automatic classifier is validated. The classifier's output is the paper's headline number, so its error must be *measured*, not assumed.

**Unit of analysis.** One tool, in the context of its own server's full tool list. You must see the sibling tools to label correctly — auditability is a property of a tool *within a server*, never of a tool alone.

**Annotators.** Two, labeling independently, no discussion until both are finished. Report Cohen's κ. Target ≥ 0.70 (substantial, Landis & Koch 1977). Below 0.60, the codebook is underspecified — revise it and re-label rather than arguing individual cases.

> **Round 1 result (2026-09-11): κ = 0.559 on 265 rows — below the 0.60 gate.** Full writeup: [`28-kappa-result.md`](28-kappa-result.md). 40 of 44 disagreements (91%) were one confusion pair, A0 vs A2, and every one had the same shape: one annotator inferred a check from a **sibling's name alone** ("call `get_property_by_id`... and verify") without being able to see that sibling's own description — because the sheet at the time showed sibling *names* only. The revision below (§ Sheet format, and the new rule under Step 3) exists to close exactly that gap. Round 2 has not run yet.

---

## The question you are answering

> Given only what the client can see — the advertised tool declarations — **can a client detect that this tool's implementation was swapped for a malicious one, using only calls it is already authorized to make?**

You are **not** judging:
- how dangerous the tool is
- how likely it is to be attacked
- whether the server looks trustworthy
- how well written the code is

You are judging **what is checkable, in principle**.

---

## Decision procedure

Work through in order. Assign the **first** class that applies.

### Step 1 — Does the tool mutate state outside the client?

- **No** (pure computation, or read-only) → go to Step 2
- **Yes** → go to Step 3

> Do **not** rely on `readOnlyHint`. It is self-declared by the server being audited and a compromised server sets it freely. Judge from the name, description, and parameters. Note the annotation separately in the `hint_conflict` column when it disagrees with your judgment — that disagreement is itself a finding.

### Step 2 — Read-only or pure tools

| Condition | Class |
|---|---|
| Same input must give the same output every time (hash, format, convert, arithmetic) | **A1** |
| Returns state that some *sibling write tool* on this server modifies, **confirmed from that sibling's own description** — not inferred from its name | **A2** |
| Returns a numeric quantity a sibling write tool moves (balance, count, quota, size) | **A3** |
| Returns external/unrelatable data nothing else on this server touches (web fetch, external search) | **A0** |

### Step 3 — Mutating tools

| Condition | Class |
|---|---|
| A sibling read tool returns a **numeric quantity** this write moves, so conservation is checkable | **A3** |
| A sibling read tool would **show this write's effect** (record appears in a list, file appears in a directory), or the write takes a free-form field a read echoes back — **and the sibling's own description states this, not just its name** | **A2** |
| Only self-consistency is checkable (idempotent — calling twice equals calling once) and no read reflects it | **A1** |
| **No sibling read reflects this write at all**, or the only candidate siblings are plausible by name but unconfirmed by their own description | **A0** |

---

## The A0 test, stated precisely

Label **A0** when you cannot name a concrete check. Force yourself to complete this sentence:

> "After calling this tool, the client could call **\_\_\_\_\_\_** and expect to see **\_\_\_\_\_\_**."

If you cannot fill both blanks with a tool that exists on *this server*, it is **A0**.

Canonical A0 examples:
- `send_webhook(url, payload)` — fires into a system this server offers no read over
- `send_email(to, subject, body)` on a server with **no** `list_sent` / `get_message`
- `fetch(url)` — the client cannot distinguish a doctored page from the real one
- any single-tool server — nothing to relate against, A0 by construction

Compare: `send_email` on a server that **also** exposes `list_sent_messages` is **A2** — the client can read back and look for its message.

---

## The rule that Round 1 was missing: a plausible-sounding sibling NAME is not evidence

This is the single change responsible for most of Round 1's disagreement, so it gets its own section rather than a footnote.

**Do not credit A2 on the strength of a sibling's name matching the topic of the write.** `download_media` next to a sibling called `list_messages` *sounds* related — they are both about messages — but that is a **noun match**, not a demonstrated read-back path. The sheet now shows each sibling's own description (truncated) precisely so you can check the actual claim, not the vibe of the name. Before writing A2, you must be able to point to the specific sentence in the **sibling's own description** that says it returns, lists, or otherwise exposes the state this write changed.

> If your `check` reads like *"call X and verify Y"* and the only reason you believe X does that is that X's **name** sounds plausible for the job — not anything X's own description actually states — **that is A0, not A2.**

This is not a stylistic preference. It is the exact failure mode the automatic classifier itself went through and was measured to be wrong about: pairing tools by shared vocabulary in their names rather than by a real, checkable relation between what one accepts and what the other returns (see [`21-real-server-results-and-options.md`](21-real-server-results-and-options.md) and [`24-calibrated-auditing-the-real-experiment.md`](24-calibrated-auditing-the-real-experiment.md) §5.1 — the same "noun-only pairing" bug, independently rediscovered by a human annotator). A gold standard that inherits the classifier's own bias cannot measure the classifier's bias.

**Worked examples, from Round 1's actual disagreements** (full set in [`data/processed/label_disagreements.tsv`](../data/processed/label_disagreements.tsv)):

| Write / read tool | Round 1 call | Correct call, and why |
|---|---|---|
| `download_media` — sibling `list_messages` | A2 ("verify the media reference") | **A0**, unless `list_messages`'s own description says it returns media references. A messaging-topic name is not that claim. |
| `linkedin_create_post` — sibling `linkedin_get_posts`-shaped tool | A2 ("verify the created post") | **A2 only if** that sibling's description states it lists posts by this account. If the sheet shows no such sibling description, A0. |
| `get_properties` (list, no key) vs a genuine `get_property_by_id(id)` | Different siblings, different verdicts | The **keyed** getter (`get_property_by_id`, takes an identifier this write's response would supply) is real corroboration; a **bare list** with no key is much weaker even when it exists — see the ENUM-vs-SNAP distinction in [`24`](24-calibrated-auditing-the-real-experiment.md) §5. Do not treat "some list tool exists" as automatically A2; check whether it can plausibly reflect *this specific instance*. |
| `create_emc_test_setup` — sibling `read_drawio` | A2 ("verify the generated diagram is present") | Check `read_drawio`'s own description: does it take a path/id the create tool's response would supply, or does it only read a document the caller already has open? If the latter, A0. |

**When the sheet gives you a description too thin to judge either way** — a placeholder string, a truncated fragment, a non-English description you cannot fully parse — that is **A0**, not a coin flip. Undecidable from the given evidence is exactly what A0 means; do not resolve the ambiguity in either direction by guessing. Say so in `check` (e.g. `"insufficient description to judge"`) rather than leaving it blank.

---

## Hard cases and how to resolve them

**Ambiguous mutation.** `execute_query(sql)` may read or write depending on the string. Label for the **declared capability**: if the description permits writes, treat as mutating.

**Read that only the same tool can verify.** `get_file_info(path)` corroborated only by another `get_file_info` is **A1**, not A2 — re-reading the same endpoint is self-consistency, not corroboration.

**Cross-server relations.** Ignore them. Only same-server tools count. A read on a *different* server is a separate trust domain and its agreement proves nothing about this one (this is the pseudo-V2 problem — see `docs/12`, Knight & Leveson 1986 on correlated failure in supposedly independent versions).

**Write whose read-back the server also controls.** Still A2. The relation exists; the server must now lie consistently across both. Whether the lie is *cheap* is the cost question (Theorem 2), not the class question.

**Deprecated duplicates.** `read_file` and `read_text_file` with identical schemas — label both, they are separately callable.

---

## Sheet format

`make_label_sample.py` writes a TSV. Fill only the last three columns.

| column | meaning |
|---|---|
| `server_id`, `tool`, `description`, `input_fields`, `siblings` | given — do not edit |
| `label` | your A0–A3 judgment |
| `check` | the concrete check you named, or `-` for A0 |
| `hint_conflict` | `y` if the server's `readOnlyHint` contradicts your read/write judgment |

**`siblings` (Round 2 format).** Each sibling is listed as `name: truncated description`, not name alone. Round 1's sheets showed names only, which is what produced the A0/A2 confusion above — an annotator could not tell a genuinely corroborating sibling from one that merely shares a topic word without seeing what it actually claims to do. If a sibling's description is empty, a placeholder, or otherwise unusable, it is listed as `name: (no usable description)` — treat that sibling as **not** confirming A2, per the rule above.

Label **300 tools**, stratified across servers so that small servers (where A0 is expected to concentrate) are not swamped by a handful of large ones.

---

## After labeling

```bash
python experiments/score_labels.py --a annotator_a.tsv --b annotator_b.tsv
```

Reports Cohen's κ, per-class precision/recall against the automatic classifier, the confusion matrix, and the **A0 bias** — the signed gap between what the classifier calls A0 and what humans do. That bias applies directly to the headline number and gets reported next to it, never silently corrected.

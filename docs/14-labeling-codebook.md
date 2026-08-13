# Labeling Codebook — Auditability Classes A0–A3

**Purpose.** Produce a human gold standard against which the automatic classifier is validated. The classifier's output is the paper's headline number, so its error must be *measured*, not assumed.

**Unit of analysis.** One tool, in the context of its own server's full tool list. You must see the sibling tools to label correctly — auditability is a property of a tool *within a server*, never of a tool alone.

**Annotators.** Two, labeling independently, no discussion until both are finished. Report Cohen's κ. Target ≥ 0.70 (substantial, Landis & Koch 1977). Below 0.60, the codebook is underspecified — revise it and re-label rather than arguing individual cases.

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
| Returns state that some *sibling write tool* on this server modifies | **A2** |
| Returns a numeric quantity a sibling write tool moves (balance, count, quota, size) | **A3** |
| Returns external/unrelatable data nothing else on this server touches (web fetch, external search) | **A0** |

### Step 3 — Mutating tools

| Condition | Class |
|---|---|
| A sibling read tool returns a **numeric quantity** this write moves, so conservation is checkable | **A3** |
| A sibling read tool would **show this write's effect** (record appears in a list, file appears in a directory), or the write takes a free-form field a read echoes back | **A2** |
| Only self-consistency is checkable (idempotent — calling twice equals calling once) and no read reflects it | **A1** |
| **No sibling read reflects this write at all** | **A0** |

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

Label **300 tools**, stratified across servers so that small servers (where A0 is expected to concentrate) are not swamped by a handful of large ones.

---

## After labeling

```bash
python experiments/score_labels.py --a annotator_a.tsv --b annotator_b.tsv
```

Reports Cohen's κ, per-class precision/recall against the automatic classifier, the confusion matrix, and the **A0 bias** — the signed gap between what the classifier calls A0 and what humans do. That bias applies directly to the headline number and gets reported next to it, never silently corrected.

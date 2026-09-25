# The Price of a Lie — The Full Story, Told Once, Properly

*A narration script for Group 13's MCP execution-integrity project. Written to be fed
into NotebookLM to generate a podcast, and to be read by Md. Tanzamul Azad and Jahidul
Islam themselves so they can explain and defend every claim in this project without
hedging. Every number in this document is pulled from the project's own regenerable
experiment logs and documentation (`docs/00`–`42` in the project repository) — nothing
here is invented, rounded up, or softened. Where the project is still incomplete, that
is stated as plainly as where it succeeded.*

---

## Part 0 — How to read this document

This is written as a continuous story, in the order the reasoning actually happened —
not the order a finished paper would present it, but the order it was *discovered*.
That matters, because the strongest way to defend this work in front of an examiner is
not to recite conclusions, but to explain *why each step was necessary before the next
one made sense*. If you can tell this story causally — "we tried X, X failed for reason
Y, which forced us to Z" — you will sound like you understand the work, not like you
memorized slides.

The document ends with a dedicated Q&A section (Part 12) that anticipates the hardest
questions a sharp examiner would ask, with a short answer and a longer backup answer for
each. Read Parts 1–11 to understand the work. Read Part 12 to defend it.

---

## Part 1 — The one-sentence idea

**MCP (the Model Context Protocol) lets a user approve a tool once, based on what that
tool *says* it does — but every time the tool is actually *used* afterward, nothing
checks whether it is still doing that thing.** The user's approval is bound to a
*declaration* (a name, a description, a schema). The tool's execution is bound to
*whatever code the server actually runs*. Nothing in the protocol ties those two
together. A server can honor its declaration once, at approval time, and quietly divert
its real effect on every call after that — and the response the client receives back
gives no sign anything changed.

This project is about that gap: proving it is real, proving no amount of *watching the
response* can close it, measuring how bad it is on real code, and then building and
adversarially testing a mechanism that closes it a different way — by watching the
*effect*, not the response.

---

## Part 2 — Why this is a real problem, not a hypothetical one

Think about what "approving a tool" actually means to an AI agent system. A user is
shown a tool's name (say, `transfer_money`), its description ("transfers funds to a
specified recipient"), and its input schema (`{amount, recipient}`). The user approves
it once. From that point on, an autonomous agent can call that tool *at machine speed,
forever, with no further human review* — that is the entire point of giving an agent
tool access in the first place; requiring a human to approve every single call would
defeat the purpose of automation.

Now here is the exposure: the approval was given to the *declaration*. The execution,
every single time, runs whatever code is actually deployed behind that tool right now.
If the server operator — or an attacker who has compromised the server, or a malicious
package update, or a supply-chain compromise of a dependency — changes what
`transfer_money` actually does after the user approved it, the user's original approval
still silently covers every future call. This is sometimes called a "rug pull" in
looser industry language, but the precise, technical name for the pattern is a
**distributed TOCTOU (Time-Of-Check to Time-Of-Use) vulnerability with no atomicity
primitive**: the check happens at time T₁ (approval), the use happens at time T₂ (every
subsequent call), and an untrusted party — the server — sits in the gap between them,
free to do whatever it wants, because nothing forces T₁'s guarantee to still hold at
T₂.

This is not a made-up scenario. It is a direct structural consequence of how MCP's trust
model works: approval is a static, one-time act over a declaration; execution is dynamic
and repeated, over code the client never inspects again.

---

## Part 3 — The threat model: precisely what we assume, and what we don't

Good research is precise about what it assumes. Here is exactly what this project
assumes an adversarial MCP server can and cannot do — because "what is our threat model"
is one of the first things a sharp reviewer will ask, and vague answers here undermine
everything that follows.

**What we assume the adversary controls**: the server's own implementation. It can
return any response it wants, it can perform any effect it wants (subject to whatever
operating-system permissions it actually holds), and it can make its behavior diverge
from its declared description at any time, for any subset of calls, in any way.

**What we do NOT assume**: this is not generic "server compromise" in the sense of the
attacker gaining root on the user's own machine, breaking TLS, or exploiting a
memory-safety bug in the client. The server is a distinct, already-untrusted party by
design — MCP itself assumes the server might be malicious, that's *why* approval exists
at all. Our question is narrower and sharper: **given that the server can lie about what
it does, what can a client still verify, and how?**

This distinction matters because it keeps the project's claims bounded. We are not
claiming to solve "AI agent security" in general. We are claiming to solve one specific,
precisely-stated sub-problem: verifying that an approved tool's *effect* matches its
*declaration*, across repeated calls, without trusting the server to tell the truth
about itself.

---

## Part 4 — Theorem 1: proving the client can't see the lie

Before building any defense, the project asked a more basic question first: **can a
client that only looks at responses ever detect this kind of divergence at all, even in
principle?** The answer, proved not just observed, is no. This is Theorem 1
(*Transcript Indistinguishability*), and it is the single most important intellectual
result in the whole project, because it is the reason every later design decision looks
the way it does.

**The proof intuition, in plain language**: imagine two parallel worlds. In World A, the
server does exactly what it declared — an honest execution. In World B, the server
performs a *different* effect (diverts a write to a different location, swaps the
content, whatever the attack is) but crafts its response message to look exactly like
what an honest execution would have returned. Because the server is the ONLY source of
both the effect AND the evidence of that effect (the response), it can always choose to
report World B's response as if it were World A's — nothing in the protocol forces the
response to be truthful about the underlying effect. A client that only ever sees the
sequence of requests and responses — the *transcript* — cannot distinguish World A's
transcript from World B's transcript, because the server made them byte-identical on
purpose. If the client's decision procedure (its accept/reject logic) is a pure function
of the transcript, and the transcript is identical in both worlds, the decision must
also be identical in both worlds. Therefore no passive, response-only client can
reliably tell the two worlds apart.

This is not a new mathematical trick — the shape of this argument is the same as classic
TOCTOU results in the security literature. What is specific to this project is applying
it precisely to MCP's declaration/execution split and using it to derive a concrete
design lesson: **do not build a defense that only re-inspects the response**, because
Theorem 1 says that class of defense is fundamentally blind, not just occasionally
imperfect. Any defense architecture built on "look harder at what the server says"
inherits this blind spot no matter how clever the inspection logic is. The only way out
is to stop trusting the response as the source of truth and instead independently
observe the *effect* itself.

---

## Part 5 — Grounding it empirically: 1,242 real servers, six detectors, zero wins

A theorem is a claim about what is *possible*. It says nothing about how common or
severe the problem is in the real world, or whether some clever engineering trick might
get *close enough* to detection in practice even if perfect detection is impossible.
So the project tested this empirically, at real scale, before designing anything.

**1,242 real, independent, third-party MCP servers** were pulled from public registries
and run inside a sandboxed Docker harness. **Six different response-level detection
mechanisms** were tried against them — approaches representative of what a careful
engineer might actually attempt: hash-based verification of responses, structural
consistency checks, behavioral fingerprinting, and others. **None of them reached a
usable operating point.** Zero percent. Not "low accuracy" — the honest number, after
correcting for measurement bugs (see Part 6), is that response-level detection provides
no usable signal at this scale.

This number is not a rounding of something more modest. It is what remained after the
project *audited its own measurement instrument twice* and found it was previously
reporting inflated numbers — which is the next part of the story, and arguably the part
that says the most about how this project actually operates.

---

## Part 6 — The self-audit discipline: finding our own bugs before anyone else could

This is worth telling as its own chapter, because it is the strongest evidence of
research rigor in the whole project, and because it directly answers the "why should I
trust your numbers" question before it's even asked.

Early in the project, the detection numbers being reported looked more encouraging than
they should have. Rather than accepting a flattering number, the project's own standing
rule — *"instrument bugs are the default hypothesis"* — triggered a deliberate audit of
the measurement pipeline itself. Two real bugs were found this way, not by an external
reviewer, but by the project team auditing its own tooling:

1. **A suppressed-detections bug**: a class of true detections was being silently
   dropped from the denominator, artificially inflating the apparent success rate.
2. **An error-flag naming bug**: the code was checking an MCP error flag under a name
   the SDK does not actually define (`isError` vs. the SDK's real `is_error`), which
   meant roughly 65% of attacks counted as "landed" were actually calls the server had
   *refused outright* — not attacks that succeeded and went undetected, but attacks that
   never happened in the first place because the server rejected the malformed request.

Finding and fixing both of these *before* trusting the headline number is precisely what
"report prevented / detected / UNKNOWN separately" and "assume a third bug exists" mean
as standing rules in this project (they are written down as such in the project's own
documentation, not invented after the fact to sound rigorous). This discipline is why,
when this document later says something like "0% true detection" or "100% prevention
coverage," those numbers can be trusted more than a number from a project that never
went looking for its own mistakes.

---

## Part 7 — Milestone M0: the corpus, the classifier, and the one honestly open gap

The project measures every MCP tool's "auditability class" — roughly, how verifiable a
given tool's behavior is from the outside, on a scale called A0–A3 (A0 being the least
auditable / most opaque). Across the corpus, **69.7% of tools fall into class A0**. This
number is genuinely important — it is the empirical backbone for "most of what's out
there is not verifiable by construction" — but it comes with one honestly open
methodological gap that has not been swept under the rug.

**The κ gate.** To trust a classifier's output, you need to know that independent human
judges would generally agree on the classification. This project pre-registered a
threshold *before* running the human-agreement check: Cohen's κ (a standard
inter-annotator agreement statistic) had to reach at least 0.60 to consider the
classifier validated. The actual measured result was **κ = 0.559** — moderate agreement,
but below the project's own pre-registered gate.

This is not hidden or explained away. It is labeled, everywhere in the project's
documentation, as an **open blocker** — milestone M0c. The 69.7% A0 figure is explicitly
described as "an instrument reading, not yet a measurement" until this gate closes. The
root cause was diagnosed, not just measured: the large majority of disagreements
between the two human annotators trace to a specific, identifiable ambiguity in the
labelling codebook (roughly one class of case being confusable between two adjacent
categories), not to random noise. A second round of labelling, redesigned to resolve
that specific ambiguity, has been prepared but requires two independent humans (not the
project's own AI tooling — using AI-generated labels here would defeat the entire
purpose of measuring human agreement) to actually complete it.

**Why this matters for how you talk about this project**: never present the 69.7% A0
number as a settled fact. Present it as "our current best instrument reading, which we
know has an open validation gap we have precisely diagnosed and are one labelling round
away from closing." That sentence is more defensible than any amount of confident
overclaiming would be.

---

## Part 8 — Milestone M1: the novelty gate — what already exists, and what doesn't

Before designing a new defense, the project did something a lot of student capstones
skip: it built a **failable** literature gate — a check that could have killed the whole
research direction if the answer came back "this is already solved." That is the
difference between a novelty *claim* and a novelty *gate*: a gate is allowed to fail.
This one retired three broad claims the project had initially assumed it could make,
before landing on a narrow, precisely bounded gap that survives scrutiny.

Four adjacent bodies of work were checked against primary sources, not secondhand
summaries:

- **Alcatraz (2003)** — a process-layer staging-and-commit/discard mechanism. It holds
  a real piece of the idea (staging before committing an effect) but is not tied to MCP
  and derives no contract from a tool's own declaration.
- **TxOS (2009)** — transactional system calls with real kernel-level rollback. Far more
  powerful in principle, but requires a *modified kernel* — it cannot be applied to an
  unmodified, real-world MCP server running on a stock system, which is exactly the
  setting this project needed to work in.
- **AgentBound / SAFEFLOW** — general confinement architectures for unmodified agent
  servers. Closer in spirit, but SAFEFLOW's own paper explicitly states it does not
  address true rollback of external side effects — a limitation this project later
  reproduces directly and empirically, not just cites secondhand (see Part 10's capstone
  result).
- **ETDI / Zero Trust Registry** — signed tool definitions and registry-based identity.
  These protect the *declaration* — they make sure the declaration itself hasn't been
  tampered with or impersonated — but say nothing about whether the *behavior* still
  matches that declaration after approval. This is precisely the blind spot Theorem 1
  identifies.

**The gap that survives**: staging-and-commit mediation of an **unmodified** process's
**real, external** effect, checked from **outside** against a contract **derived from
the tool's own declaration**. Each of the four systems above holds one piece of this —
staging (Alcatraz), rollback (TxOS, but needs a modified kernel), general confinement
(AgentBound/SAFEFLOW, but no real external rollback), or declaration integrity
(ETDI/Zero Trust, but no behavioral checking) — but none holds the whole combination.
That is the project's actual claim to novelty, and it survives specifically *because*
three broader, more sweeping claims were tested and retired first.

---

## Part 9 — Our approach, part one: the Permit rule

With the gap identified, the project needed a precise, checkable definition of "this
effect is allowed." That definition is the **Permit rule**:

```
Permit(a, C)  =  Valid(C)  ∧  Matches(a, C)  ∧  Unused(C)  ∧  Mediated(a)
```

In words: a proposed effect `a` is permitted under contract `C` only if all four hold
simultaneously:

- **Valid(C)** — the contract itself is authentic and has not expired.
- **Matches(a, C)** — the effect's operation, target, and payload all fall within what
  the contract's bound fields actually authorize. This is checked on the *raw proposed
  request*, before the effect is even allowed to happen — it is what catches an attacker
  sneaking in an extra argument the contract never anticipated.
- **Unused(C)** — the contract still has invocation allowance remaining. This is
  enforced by an actual reservation system (`AllowanceLedger.reserve()`), taken *before*
  any staging work begins, so a second attempt against an already-spent authorization is
  refused immediately, not after wasted work.
- **Mediated(a)** — the effect actually took the enforced path; nothing about it reached
  the real world through some other, unwatched channel.

This is stated plainly as a **policy definition**, not a theorem — nobody is claiming to
have proven this rule is correct in some mathematical sense. The actual research
question is whether a real implementation can be built that *preserves* this rule under
adversarial pressure, and where, precisely, it breaks when pushed. That is what the rest
of the project tests.

---

## Part 10 — Our approach, part two: the specification ladder

A contract needs to know what "matches" actually means for a given tool, and here the
project makes a deliberately careful choice: **don't assume more specification buys more
protection — measure it.** The specification ladder has three independent rungs, and
each tool's contract is checked at each rung *separately*, because the project's own
early experiments (`27`) predicted, and later real-server results confirmed, that more
specification does not uniformly help:

| Rung | What it checks | What it catches | What it structurally cannot catch |
|---|---|---|---|
| **L1 — destination** | only the approved target changed | diversion to a different target (a different path, a different database row, a different recipient) | a payload swapped at the *correct* destination |
| **L2 — structure** | the above, plus: is the result non-empty / well-formed | nothing beyond L1 on tools where the "content" is just free text | still nothing about whether the content is *correct* |
| **L3 — content** | the above, plus: exact-match (or hash-match) on the final bytes | content substitution — the attack that L1 and L2 cannot see | see Part 11's honest limitations |

The critical design decision here is that verdicts are reported **per-property**, never
collapsed into one pass/fail number. A tool can legitimately be `destination=PASS,
content=FAIL` at the same time — and that distinction, not a single flattened score, is
what the whole ladder is measuring.

---

## Part 11 — Our approach, part three: the six-step mediation mechanism

The ladder tells you *what* to check. The mediation mechanism is *how* the check
actually happens without trusting the server to cooperate. It runs as six steps, in
strict sequence, and — this is important for defending the design — **each step was
added because a specific attack found it missing, not designed in speculatively from the
start.** That history is worth knowing, because "we added this because we broke our own
system without it" is a much stronger answer than "we thought it might be a good idea."

1. **RESERVE** — take one execution slot against the contract's `AllowanceLedger` before
   anything else happens. A second reservation against an already-exhausted contract is
   refused right here, before any staging work even begins. *(Added after a replay
   attack — Part 10 of the M4 story below — showed a pure effect-diff mediator commits
   an identical replayed write twice, because a replay's effect matches the contract by
   definition; effect-diff alone cannot see that the authorization was already spent.)*
2. **ISOLATE** — every single invocation gets its own staging workspace, owned *only* by
   the untrusted server's own OS identity. Nothing else writes into this area on the
   server's behalf; the untrusted process behaves exactly as it normally would.
3. **REQUEST-SHAPE CHECK** — before the resulting effect is even inspected, does the
   *raw proposed request's* argument set fall entirely within the contract's bound
   fields? *(Added after a deliberate corner-case test found that an argument producing
   no file-level change at all is completely invisible to a pure effect-diff — the
   mediator was blind to it by construction until this step was added.)*
4. **FREEZE + READ ONCE** — a trusted mediator, running as a *different* OS identity than
   the server, reads the staging area **exactly once**. This single read is both the
   evidence used for the decision and, if committed, the exact bytes that get written
   into the trusted store. No second, independent read of staging ever happens after
   this point — this rule has a name in the project's own documentation: the **M2 Commit
   Invariant**. *(Added after a purpose-built, contract-aware adversary found that
   re-reading staging a second time at commit time — instead of reusing the first read —
   opened a real race window: 5 out of 20 trials, 25%, let attacker content slip into
   the trusted store between the decision and the commit. Fixed by committing the bytes
   already captured in step 4's read, never re-reading from disk; re-verified at 0 out
   of 20 against the identical attack.)*
5. **EFFECT DIFF** — the single frozen read is checked against the contract at whichever
   ladder rung is in force: exact path, exact bytes (or hash), no extra artifacts.
6. **COMMIT OR DISCARD** — on an exact match, the mediator itself — never the server —
   writes the frozen bytes into a *separate*, committed store that the server has zero
   write permission on, and marks the reservation as spent. On any mismatch at step 3 or
   step 5, nothing is written at all; the transaction is simply discarded.

The honest way to describe what this mechanism claims is: **it moves the enforcement
point from the server's response to the server's actual filesystem effect**, exactly as
Theorem 1's design lesson demands, and it does so using only information the tool's own
declaration already provides — no out-of-band knowledge of the application built on top
is required.

---

## Part 12 (renumbered as Part 12 of the narrative — Milestone M2) — building and breaking our own mechanism

Before trusting this mechanism against anything real, the project attacked it with tools
it wrote itself, deliberately trying to break its own design, and reported every crack
it found.

**Architectural closure and pre-registered thresholds.** The mechanism was first
validated against a synthetic but faithful stub server, with thresholds fixed *before*
the run, not chosen afterward to match whatever number came out: prevention coverage of
attacks the undefended control let through had to reach ≥90% — the actual result was
**100% (10 out of 10)**. The rate of ambiguous "UNKNOWN" outcomes had to stay ≤20% — the
actual result was **7.1% (1 out of 14, a single genuine "silent no-op" case)**. Honest
workflows had to complete within 5 percentage points of the undefended baseline's
success rate — the actual result was a **0 percentage-point gap**, meaning the one
honest scenario tested completed identically whether the mechanism was present or not.

**Corner cases, tested rather than assumed.** Four honest-workflow edge cases were run
deliberately: writing to a temporary name then renaming it, writing empty content,
writing a large (~2.3MB) payload, and writing then immediately overwriting the same
target. All four passed cleanly. A fifth, deliberately adversarial-to-the-mechanism-
itself test deliberately shared one staging directory across two sequential *honest*
calls — and found a real bug: the second honest call's legitimate effect was wrongly
discarded because of a leftover artifact from the first call. This is not a security
failure (nothing malicious happened) but a genuine honest-utility failure, and it is
reported as exactly that: **per-invocation isolation is a requirement for correctness,
not just security**, demonstrated rather than assumed.

**The TOCTOU race and the hidden-field gap** — both already described in Part 11, since
they are the reason steps 3 and 4 exist in their current form — were found here, in this
milestone, by adversarial self-testing before any external server was ever involved.

---

## Part 13 — Milestone M2's capstone: combining the mechanism with a real, unmodified server

Every M2 test up to this point used a synthetic stub server the project itself wrote.
That is a legitimate first step, but it leaves open an obvious question: does any of
this actually work against *real* third-party code the project has no control over?

**The engineering obstacle that had to be solved first.** The project's own MCP client
(`LiveSession`) had no built-in way to launch a subprocess as a lower-privileged OS
identity — verified directly by inspecting the actual MCP SDK's launch-parameter type,
which exposes no such option. This is why every earlier M2 test used a hand-written stub
instead of a real server: there was no way to run one as anything other than the
project's own process identity.

**The fix**: wrap the launch command in a privilege-dropping shell invocation
(`su sandbox -s /bin/sh -c '...'`). The MCP client only ever sees a command string; it
has no idea that string itself performs a real privilege drop before the actual server
process starts. This was verified live, not assumed — a real `npx -y filesystem-mcp`
process launched this way was confirmed, via direct filesystem ownership inspection, to
be running and writing files as the unprivileged `sandbox` user, not as root.

**The result**, against `domdomegg/filesystem-mcp` — the same real, unmodified npm
package used earlier in the M3 sweep (Part 14):

- **Honest call**: completes and commits, byte-for-byte identical to any stub-server
  trial.
- **`path_diversion`**: the real, unmodified server genuinely wrote the approved content
  to `/tmp/exfil.dat` — a real, external, unauthorized effect, produced by real
  third-party code, not a simulation. The mediator's diff caught the mismatch and
  discarded the transaction: `committed_content = None`. **The write to `/tmp` already
  happened and is not undone** — this is stated as plainly as the positive result,
  because it is the honest scope of what "discard" actually means here: bookkeeping over
  what the trusted store counts as committed, not a claim that the underlying OS-level
  write was prevented.
- **`content_substitution`**: the attacker's payload was staged for real, caught by the
  content diff, and discarded — never reaching the committed store.

This is the moment the project can honestly say: *the exact same real diversion that
landed unconfined, for real, against unmodified third-party code — is now kept out of
the trusted store, for real, by this mechanism.* Full prevention of the underlying OS
write would need an additional layer (a mount namespace or chroot confining the server's
writable scope before it even runs) — that is explicitly named as something this project
does not add, not glossed over as already solved.

---

## Part 14 — Milestone M3: generality across seven real, independent servers

A mechanism that works on one server proves almost nothing about whether it generalizes.
M3's goal, per the project's own pre-registered target, is **at least ten independent
real implementations**. The project currently has **seven**, spanning every workflow
shape it defined plus two additional shapes discovered along the way — real progress,
honestly short of the target, and described as exactly that everywhere it is discussed.

Walk through them in the order they were tested, because the *order* tells its own
story of deliberately seeking out variation, not cherry-picking easy wins:

1. **`domdomegg/filesystem-mcp`** (EXACT class — separate `path` and `content`
   arguments). The first real-server test, and the one that found the original
   `path_diversion` result described in Part 13.
2. **`@modelcontextprotocol/server-filesystem`** (the *official* reference
   implementation, same EXACT shape). Chosen specifically to test whether the finding
   held on a second, independent implementation of the *same* tool shape. Result: this
   server enforces its **own** allowed-directory boundary and refuses the diverted call
   outright — a genuinely different real-world outcome from server 1, on what looks
   identical from the tool declaration alone. This is exactly the kind of variation M3
   exists to surface.
3. **`@modelcontextprotocol/server-memory`** (CONSTRAINED/keyed — a structured
   knowledge-graph store, not a file path). Required hand-authoring the attack, because
   the automatic tampering tool only inspects top-level string arguments and this tool's
   only argument is a nested array — a real, worth-stating limit of the automated
   instrument, not a server defense. Reproduced the same destination-caught /
   content-needs-L3 pattern on a completely different data model.
4. **`mcp-sqlite-server`** (UNDERSPECIFIED/SQL — a single opaque `sql` string carrying
   destination, structure, and content all mixed together with no schema-derivable
   boundary between them). **This produced the sharpest negative finding in the entire
   project**: content substitution is not caught at *any* rung, not just missed until
   L3 — because the tool's schema gives the mechanism no field to derive a content check
   from in the first place. This is reported as a genuine, structural limit of the
   approach on this workflow class, not minimized.
5. **`mcp-server-git`** (a git-native shape with **no content argument at all** — the
   payload is whatever is already staged in the working tree; the contract's "content"
   becomes the commit *message*, the one argument the tool actually contributes). A
   second server, in a completely different tool family, was found to enforce its own
   destination boundary (a `--repository` launch restriction) — confirming the
   own-defense pattern from server 2 recurs independently, not as a one-off.
6. **`mcp-server-sqlite-npx`** (UNDERSPECIFIED/SQL, a **second, independent**
   implementation of the same class as server 4, chosen specifically to answer: is the
   sharp negative finding a property of one package, or of the class itself?). The
   finding replicated exactly, on genuinely different, unrelated code. **This
   replication is arguably more valuable to the project's credibility than the original
   finding** — a single surprising result from one codebase invites doubt; the same
   result on two independent codebases is evidence of a structural property.
7. **`notes-mcp`** (a genuinely new shape: content assembled from **two separate
   arguments**, `yaml_frontmatter` and `markdown_content`, combined by the server into
   one file). Chosen to test something none of the first six servers could test: can an
   attacker tamper *only one half* of a two-part payload and slip past the content
   check? The result: no. The L3 exact-match check compares the tool's whole declared
   *output*, not either argument individually — tampering either half alone is still
   caught, with no special-casing required for which field carries which part of the
   payload. A useful additional detail: this server takes a *relative* path, so its
   diversion attack lands as a sibling file *inside* the same directory rather than
   escaping outside it — a detail that becomes important again in Part 16 (M5).

**What this sweep does and does not establish, stated with the same discipline as
everywhere else in this project**: it shows the mechanism transfers to real, independent
code across every workflow shape defined, that the ladder's predicted blind spots
(L1/L2 miss content attacks; UNDERSPECIFIED tools resist the ladder almost entirely)
reproduce exactly on unrelated real implementations, and that two servers' own defenses
recur as an independent pattern worth knowing about. It does **not** establish full
generality — seven is not ten — and it does **not** demonstrate prevention of an
already-landed external effect, for the same reasons stated in Part 13.

---

## Part 15 — Milestone M4: the adaptive adversary — four attacks, tested after the defense existed

Every attack described so far in Parts 12–14 was designed *before*, or independently of,
the final mechanism's own code. M4 is different and more demanding: it means building
adversaries **with knowledge of the mechanism's actual implementation**, specifically to
find what a defender who already knows the exact design would exploit. Four named attack
families were tried, covering every angle the project could identify:

1. **The TOCTOU race** (already described in Part 11) — found and fixed. 25% success
   rate before the fix, 0 out of 20 after, re-verified against the identical attack.
2. **Replay / allowance exhaustion** — a contract-aware adversary that simply replays an
   already-used, legitimate authorization. Without the `AllowanceLedger` reservation
   step, the mediator commits the replayed write a **second** time, because a replay's
   effect matches the contract by definition — a pure effect-diff cannot distinguish a
   replay from a fresh, legitimate call. **Found and fixed** by wiring in
   `AllowanceLedger` — a component that already existed elsewhere in the project's
   codebase, already unit-tested, but had simply never been connected to this newer
   mediator until this attack exposed the gap. After the fix, the second call is refused
   before staging even begins.
3. **Unmediated-channel exfiltration** — a secret sent over a plain local socket, in the
   *same* invocation as an approved, honest file write. The mediator commits the honest
   write as cleanly as if nothing else had happened, because the socket channel was never
   part of its observation surface at all. **This is demonstrated as a genuine, honest
   scope boundary, not reported as a bug with a fix** — the project explicitly states
   that no fix exists *within* a filesystem-only mechanism; closing this would need an
   entirely different layer (network namespace isolation, an egress allowlist), which is
   named as necessary future work, not claimed as already covered.
4. **Utility-degradation / fixed-timing-window tradeoff** — an entirely honest write that
   completes slowly (tested at 0.2s, 0.6s, and 2.0s delays against a mediator with a
   0.8-second grace window). The 2.0-second honest write — which does eventually succeed
   — is discarded exactly like a malicious `background_write` attack deliberately timed
   to land after the window. **Reported as a genuine structural tradeoff, not a bug**:
   the mediator's single read at a fixed delay cannot distinguish "slow but honest" from
   "malicious and patient" by definition. Widening the window trades one failure mode
   for the other; it does not remove either. A real fix would replace the fixed timeout
   with an explicit completion signal or process-tree freezing — again, named as future
   work, not claimed as solved.

**The pattern worth emphasizing when explaining this milestone**: two attacks led to
real fixes, re-verified against the identical exploit that found them. Two attacks
exposed genuine, permanent boundaries of what a filesystem-only, single-read mediator
can ever promise — and the project chose to name those boundaries explicitly rather than
paper over them or quietly narrow its claims without saying so.

---

## Part 16 — Milestone M5: held-out evaluation against the "demanding baseline"

A mechanism is only impressive relative to the alternative a careful engineer would
actually deploy instead. M5's whole purpose is that comparison: this project's mechanism
versus **no defense at all** versus **static least-privilege** — plain Unix
directory/file permissions, no software logic whatsoever, which the project's own
research plan names "the demanding baseline" precisely because it is what a competent
engineer, without this project's research, would likely build first.

**First server — `domdomegg/filesystem-mcp`.** Static least-privilege was built the
standard way: the staging directory locked to root ownership with no write bit at all,
the one approved target file pre-created and owned by the untrusted identity (so the
server *can* write into that specific existing file, since file permissions — not
directory permissions — govern writes to a file a process already has open access to).
Result: static least-privilege caught **neither** attack tested. Path diversion targets
an *absolute* path (`/tmp/exfil.dat`) entirely outside the locked directory — no
directory-permission scheme confined to one folder can ever reach an escape that never
enters that folder. Content substitution writes the correct bytes to the wrong content
at the *correct*, permitted path — no permission system in existence checks *what* is
written, only *who* may write *where*. This project's mechanism caught both.

**Second server — `notes-mcp`, added specifically to test whether the first result was
general or an artifact of one server's path handling.** This server (already introduced
in Part 14) resolves its diverted write as a *relative* sibling file inside the *same*
staging directory, not an absolute escape outside it — the one condition under which
directory permissions could plausibly matter. The result, verified empirically rather
than assumed: static least-privilege's path-diversion attempt is **refused by the
operating system itself**, with a real `PermissionError`, because the missing directory
write-bit blocks the server from creating *any* new entry there, including the diverted
sibling file. Content substitution, however, **still commits unchanged** — exactly as on
the first server — because it never involves creating a new file at all; it overwrites
the correct, pre-existing, permitted target.

**The refined claim this produces — and this refinement is itself one of the project's
more sophisticated results, worth explaining carefully to an examiner**: static
least-privilege is **structurally blind to content substitution on every server tested**
— this is a property of what permission systems can express at all, not a property of
any one server. But its apparent success against path diversion is **not** a property
the defender controls at all — it is a side effect of whether the *target tool's own
path-resolution behavior* happens to keep the diversion inside the locked boundary or
send it outside. A defender deploying static permissions has no way to know in advance
which case they are in, because that depends entirely on code they do not control. This
project's mechanism caught both attacks on both servers, with no such dependency —
because it checks the actual resulting *content*, not merely where a write landed.

---

## Part 17 — What this project is NOT claiming: the full, honest limitations list

This section exists specifically so that no examiner can catch this project overclaiming
something it has already, itself, stated plainly elsewhere. Memorize this list — it is
your strongest defense, because volunteering your own limitations before being asked is
far more convincing than being caught not knowing one of them.

1. **κ = 0.559, below the project's own 0.60 pre-registered gate.** The 69.7% A0 figure
   remains an unvalidated instrument reading until Round-2 labelling closes this. This is
   the oldest open blocker in the project (milestone M0c).
2. **M3 is seven servers, not ten.** No full generality claim is supportable yet. The
   network domain is completely untouched — everything tested writes to a filesystem or
   equivalent local store; nothing tests HTTP-effect tools, message queues, or remote
   API calls.
3. **No real rollback of an already-landed external effect.** "Discard" means the
   trusted, committed store never counts the diverted effect as authorized — it does not
   mean the underlying OS-level write, record creation, or commit is undone. This is the
   same limitation SAFEFLOW's own paper documents in general; this project confirms it
   directly, empirically, on real code, rather than only citing it.
4. **Unmediated channels are completely invisible.** Anything that does not touch the
   filesystem the mechanism watches — a network socket, an environment variable, a
   different IPC channel — is entirely outside its observation surface. Demonstrated
   directly (Part 15, attack 3), not just argued as a theoretical gap.
5. **The fixed timing window is a genuine, unresolved tradeoff, not a bug with a
   pending fix.** No single timeout value can simultaneously tolerate every honestly
   slow write and catch every patient, deliberately-timed malicious one.
6. **The UNDERSPECIFIED/SQL class is a near-total blind spot for content attacks**,
   replicated on two independent implementations. This is a structural property of what
   the tool's own schema exposes, not something more engineering effort within this
   design can fix — a genuinely different mechanism (parsing SQL semantics, or requiring
   an application-level adapter) would be needed, and that is named as an open question,
   not solved.
7. **Per-invocation isolation is a hard requirement, not an optimization.** Sharing a
   staging area across calls causes wrongful discarding of entirely honest work,
   demonstrated directly in M2's corner-case testing.
8. **The corpus is credential-free servers only.** Servers requiring API keys or
   credentials — mail, payments, code-hosting platforms, the highest-stakes categories —
   are excluded by construction from every empirical measurement in this project. The
   measured harms should be read as a lower bound on what is possible in deployments this
   project has not tested.
9. **This mechanism says nothing about confidentiality.** Its entire claim is about the
   integrity of what reaches the trusted, committed store — not about what an untrusted
   process is able to read or exfiltrate through channels it is already permitted to
   access.

---

## Part 18 — Hard questions, answered without hedging

This is the section to actually rehearse out loud. Each question has a short, one-breath
answer you can say immediately, followed by the longer, data-backed version if the
questioner pushes further. None of these answers require inventing anything — every
number and claim below is already established in Parts 1–17.

---

**Q: "Isn't this just sandboxing? What's actually new here?"**

*Short answer:* No — sandboxing alone (Part 16) caught neither attack we tested; the
novelty is a contract-derived content diff, not process isolation.

*Long answer:* We tested this exact objection directly, empirically, in M5. Static
least-privilege — real Unix permissions, no software layer — is structurally blind to
content substitution on every server we tried, because permission systems check *who*
writes *where*, never *what* is written. Sandboxing alone is not the mechanism doing the
actual work; our specification-ladder content diff is. We also ran a failable novelty
gate (Part 8) against four adjacent systems — Alcatraz, TxOS, AgentBound/SAFEFLOW,
ETDI — and found each holds only a piece of the full combination we claim: staging
(Alcatraz), true rollback but requiring a modified kernel (TxOS), general confinement
without real external-effect rollback (SAFEFLOW, confirmed directly by us in Part 13),
or declaration-only integrity (ETDI). None combines all of: unmodified process, real
external effect, checked from outside, against a contract derived from the tool's own
declaration.

---

**Q: "Your own κ is below your own threshold — why should I trust any number in this
project?"**

*Short answer:* Because we set that threshold ourselves, before running the test, and we
are telling you it failed instead of hiding it.

*Long answer:* The pre-registered 0.60 gate exists specifically so we could not
rationalize a weak agreement number after the fact. We measured 0.559, we diagnosed the
root cause precisely (91% of the disagreements trace to one specific codebook ambiguity,
not random noise), and we labeled the downstream 69.7% A0 figure as an "instrument
reading, not yet a measurement" everywhere it appears in our documentation, before you
asked. That is a stronger trust signal than a number that happened to clear an
arbitrary bar with no stated pre-commitment.

---

**Q: "You only tested seven servers. How do you know this generalizes to the other
thousands of MCP servers out there?"**

*Short answer:* We don't claim it does yet — M3 is explicitly "in progress," not
complete — but the pattern already replicated twice on independent code, which is
stronger evidence than seven unrelated single data points.

*Long answer:* Our own pre-registered target is ten independent implementations; we have
seven, and we say so everywhere, not just when asked. But two of those seven are
*deliberate replications* of the same finding on independent code — the UNDERSPECIFIED/
SQL content-blindness result reproduced exactly on two unrelated SQL server packages —
which is stronger evidence of a structural property than seven unrelated single
findings would be. We also deliberately sought out variation, not easy wins: two servers
turned out to enforce their own destination defenses (reducing our mechanism's marginal
contribution there), and one server (`notes-mcp`) has a genuinely different attack
surface (two-argument content, relative-path resolution) that we specifically went
looking for rather than repeating the same EXACT-class server seven times.

---

**Q: "The malicious write to `/tmp/exfil.dat` still actually happened on disk. Isn't
that a failure of your defense?"**

*Short answer:* We call this "detection, not prevention of an already-landed effect,"
and we say so every time we report this result — it's a narrower, more honest claim, not
a hidden weakness.

*Long answer:* Theorem 1 already tells us a passive client cannot prevent an untrusted
process that holds real OS write authority from performing a real write — that's not
something a contract-checking layer sitting *after* the effect can undo. What our
mechanism actually guarantees, and what we're careful to say precisely, is that the
diverted effect never reaches the *trusted, committed store* the rest of the system
relies on. True prevention of the underlying OS-level write would need an additional
layer — a mount namespace or chroot restricting what the server can write to in the
first place — and we name that explicitly as something we do not add, not something we
quietly claim to have solved.

---

**Q: "How do you know your TOCTOU fix actually works, instead of just moving the race
somewhere else you haven't found yet?"**

*Short answer:* We built an adversary specifically to attack that exact race, measured a
real 25% success rate before the fix, and re-ran the identical attack at 0 out of 20
after.

*Long answer:* We don't just assert the fix works — we re-verify against the exact
exploit that found the bug in the first place. Before the fix, the mediator re-read
staging a second, independent time at commit — separate from the read used for the
diff decision — creating a real window an adaptive adversary could win 5 times out of 20
trials. The fix makes the mediator commit the *same* bytes already captured by the
single read used for the decision (the "M2 Commit Invariant"), removing the second read
entirely rather than trying to make it faster or better-synchronized. We then re-ran the
identical 20-trial attack and measured 0 successes. We cannot claim no other race exists
anywhere in the system — no team can honestly claim that — but we can show, with
evidence, that this specific, previously-real vulnerability is now closed.

---

**Q: "Static least-privilege sounds like a strawman. A real engineer would combine
permissions with other tools."**

*Short answer:* We agree — which is exactly why M5 measures what permissions alone do
and do not cover, not a claim that permissions are useless in every combination.

*Long answer:* M5's entire point is precision, not demolition. We show permissions are
structurally blind to content substitution (a property of what permission systems can
express, true regardless of what else is combined with them) and that their apparent
success against path diversion is contingent on a tool's own path-resolution behavior,
not a property the defender controls. That is a more useful and more honest finding than
"permissions are bad" — it tells a real engineer exactly where a permissions-based
defense needs a second layer, and exactly what that second layer needs to check
(content, not just destination).

---

**Q: "What happens with attacks over the network, not the filesystem?"**

*Short answer:* Completely out of scope, and we demonstrated that gap ourselves rather
than waiting for someone else to find it.

*Long answer:* M4's third attack (Part 15) sent a secret over a plain local socket in the
same call as an honest file write, and our mediator committed the honest write as
cleanly as if nothing else had happened — the socket channel was never part of what it
watches. We say plainly that no fix for this exists *within* a filesystem-only design;
closing it needs a genuinely different layer, like network namespace isolation or an
egress allowlist, and we name that as necessary future work rather than something this
project already covers.

---

**Q: "Why is this a research contribution and not just an implementation project?"**

*Short answer:* Because it proves an impossibility result first, grounds it at real
scale, passes a gate that could have killed it, and then adversarially self-tests a
concrete mechanism against its own stated failure modes — that is the shape of a
research contribution, not a build.

*Long answer:* Five separate things had to each hold for this to count as research
rather than engineering: (1) Theorem 1 is a proved claim, not an empirical observation;
(2) it is grounded at a scale (1,242 real servers) few comparable defenses in this space
report, including a documented self-audit of the measurement instrument itself; (3) the
novelty claim survived a *failable* gate that retired three broader claims first, rather
than being asserted; (4) the mechanism was adversarially self-tested by a team that
built attacks with full knowledge of its own code, finding and fixing two real defects
rather than only testing happy paths; (5) it was validated repeatedly on independent,
real, unmodified third-party code — including two deliberate replications — not only on
synthetic benchmarks tuned to the mechanism.

---

## Part 19 — The contribution, in one paragraph you should be able to say from memory

*"MCP binds a user's one-time approval to a tool's declaration, but binds every actual
execution to whatever the server's real implementation does — and we proved, not just
observed, that a client watching only responses can never close that gap, then confirmed
it empirically at zero percent true detection across 1,242 real servers, after auditing
our own measurement tools and fixing two real bugs in them first. We checked that finding
against the closest prior work before claiming anything, retired three broad claims, and
found one narrow, precisely bounded gap survives: staging-and-commit mediation of an
unmodified process's real external effect, checked from outside against a contract
derived from the tool's own declaration. We built that mechanism, broke it ourselves with
adversaries that knew its own code, fixed the two real bugs we found, named the two
genuine structural limits we could not fix, and then validated it on seven independent
real third-party servers — including two deliberate replications of our sharpest
negative finding — and against the specific baseline our own research plan calls 'the
demanding one,' beating it precisely where permission-only defenses are structurally
blind, on two servers, not one."*

---

## Part 20 — Glossary, for quick reference

- **MCP** — Model Context Protocol; the protocol by which an AI agent discovers and
  calls external tools through a client-server architecture.
- **Declaration** — a tool's name, description, and input schema, inspected once at
  approval time.
- **Effect** — what a tool actually does to the world (a file write, a database record,
  a committed change) when called.
- **Transcript** — the full sequence of requests and responses a client observes over a
  session; what a passive, response-only client has access to.
- **TOCTOU** — Time-Of-Check to Time-Of-Use; a class of vulnerability where a security
  decision is made at one moment but relied upon at a later moment when conditions may
  have changed.
- **Contract (C)** — the bound set of fields (destination, structure, content) a
  specific approved call is allowed to touch, derived from the tool's own declared
  schema.
- **Ladder rung (L1/L2/L3)** — destination-only / plus-structure / plus-content, the
  three independent levels a contract can be checked at.
- **Staging** — an isolated, per-invocation workspace owned by the untrusted server's
  own OS identity, where its real effect happens before being checked.
- **Mediator** — the trusted, separate-OS-identity process that reads staging exactly
  once and decides commit or discard.
- **AllowanceLedger** — the component enforcing that a contract can only be spent as
  many times as authorized, preventing replay attacks.
- **M0–M6** — the project's own milestone structure: M0 (measurement/classifier
  validation), M1 (novelty gate), M2 (mechanism, single domain), M3 (generality across
  real servers), M4 (adaptive adversary), M5 (held-out evaluation), M6 (write-up).
- **A0–A3** — the project's own auditability taxonomy for how verifiable a tool's
  real-world behavior is from the outside, A0 being least auditable.
- **κ (Cohen's kappa)** — a standard statistic measuring agreement between independent
  human raters, used here to validate the A0–A3 classifier against real human judgment.

---

## Part 21 — What to do next, and the actual path to publication

This part is deliberately practical rather than narrative — it is the answer to "what
now," kept honest about what is realistically achievable and in what order, rather than
a wish list.

### 21.1 — Immediate next steps, in priority order

1. **Finish Round-2 labelling and close M0c.** This is the single highest-leverage item
   in the entire project. The materials are already prepared (an instruction sheet and
   two annotator sheets). Until this closes, the 69.7% A0 figure — the empirical
   backbone of the whole opening argument — remains an unvalidated instrument reading.
   Nothing else in the project can substitute for this; it needs two real, independent
   humans to actually do the labelling.
2. **Push M3 from 7 toward 10 real servers.** Not urgent for the report deadline, but
   directly closes the project's own pre-registered generality target. Prioritize
   well-known, actively maintained MCP servers over unverified registry entries — the
   corpus used for the 1,242-server scale run skews heavily toward low-quality or broken
   packages in its long tail, so picking new M3 candidates from reputable sources (the
   official `modelcontextprotocol` organization, well-known community packages) is far
   more time-efficient than searching blindly.
3. **Write the actual manuscript.** This is the biggest remaining gap between "have the
   results" and "have a paper." The `docs/` folder is excellent raw material, not a
   paper — it needs to be compressed into Abstract → Introduction → Related Work →
   Threat Model → Design → Evaluation → Limitations → Conclusion, in the register a
   paper actually uses, not the exploratory research-log voice of the `docs/` files.
4. **Build the consolidated figures.** Three roll-up tables (one each for M3, M4, M5)
   and two or three real diagrams (the threat model / declaration-vs-implementation
   split, the mediation pipeline) do not exist as standalone artifacts yet — they are
   scattered across per-milestone documents and need to be built once, cleanly, for the
   paper.
5. **A final internal consistency pass** once the manuscript exists: check every number
   quoted in the paper against its source table or notebook one more time before
   freezing the content — the same discipline the project has applied throughout.

### 21.2 — Optional, lower-priority extensions (only if time genuinely remains)

- A network-domain test (currently completely untouched — everything tested so far
  writes to a filesystem or equivalent local store).
- A concrete attempt at the UNDERSPECIFIED/SQL blind spot — e.g., a prototype adapter
  that parses SQL well enough to derive a content check, even if only for a narrow
  subset of statements. This would directly answer the open question the project itself
  poses in `29`'s "next step" section.
- Genuine concurrency testing for M2 (two calls truly overlapping in time, not
  sequential) — named as untested in `30`'s own milestone table.

Do not manufacture new experiment categories beyond this list just to appear more
thorough — the project's own credibility so far comes from doing a bounded set of things
rigorously, not from doing many things shallowly.

### 21.3 — The actual path to publication

Getting a capstone report finished and getting a paper genuinely published are two
different processes, on different timelines. Be clear-eyed about that distinction so
neither goal gets rushed to the detriment of the other.

1. **The manuscript itself is the bottleneck — nothing about publication matters before
   it exists.** No venue, no formatting choice, no submission strategy is useful to
   think about until Part 21.1's item 3 is actually done.
2. **Close the citation quarantine before submitting anywhere.** The project's own
   standing rule states every entry in `paper/references.bib` is still marked `[U]`
   unverified. A submitted paper cannot carry unverified citations — each one needs its
   primary source actually opened and confirmed before the bibliography is considered
   final.
3. **Decide on a manuscript format early**, ideally with the supervisor's input — a
   standard two-column conference template (IEEE or ACM `sigconf` style are the common
   defaults for a systems/security-flavored paper like this one) is the safe default
   choice absent a specific venue's own requirement.
4. **Consider two parallel, non-exclusive publishing paths, roughly in this order:**
   - **An arXiv preprint** once the manuscript is solid: fast, not peer-reviewed, but
     establishes a public timestamp and lets the work be cited immediately. Low risk,
     high value as a first step, and does not preclude later venue submission (most
     venues explicitly allow arXiv preprints).
   - **A peer-reviewed venue.** For a project at this stage — a strong undergraduate
     capstone with real empirical results but not yet a fully mature, ten-server-plus
     dataset — realistic targets include a national or regional CS conference
     (Bangladesh-based student work commonly targets venues like ICCIT), a
     security-focused workshop appropriate for agent/tool-integrity work, or the
     university's own research symposium or journal if one exists. **Confirm the exact
     target venue and its current call-for-papers deadline directly with the
     supervisor** — do not rely on a guessed date, since CFP deadlines shift year to
     year and guessing one here risks planning around a wrong date.
5. **Format and trim precisely to the chosen venue's requirements** (page limit,
   anonymization for double-blind review if required, exact template) only after a
   venue is actually chosen — reformatting from a generic draft to a specific venue's
   template is normal and expected, not wasted work.
6. **Get explicit supervisor sign-off before any external submission.** Mr. Azizur
   Rahman Anik's name and involvement as supervisor should be confirmed for authorship
   and submission approval before the paper leaves the project's own repository.
7. **After submission, treat reviewer feedback exactly the way this project has treated
   its own limitations so far** — as data to act on honestly, not as something to argue
   away. A project this disciplined about naming its own weak points is unusually well
   positioned to handle peer review constructively rather than defensively.

---

*End of script. This document is source material for understanding and defending the
project — it is not the final paper, and it should not be mistaken for one. The paper
manuscript itself (Abstract → Introduction → Related Work → Design → Evaluation →
Limitations → Conclusion) still needs to be written separately from the project's
`docs/` folder, which this script draws from.*

# SPEC — codex broker error classification (supersedes round-2 regex tuning)

Status: **written because iterating was the wrong move.** B2a's first attempt at
F3's error split drew 12 findings from a fenced cross-family refuter, all 12
reproduced against the compiled patterns. They are not twelve separate bugs.
They are one design defect wearing twelve faces.

## The defect

> Distinct vocabularies do not imply mutually exclusive payloads.

The implementation searches free-text stderr for word classes and takes the first
class that hits. That is unsound for three independent reasons, each demonstrated
with a real string:

1. **A single stderr can belong to two classes at once.**
   `Error: token has expired; refresh failed with 429 too many requests`
   is an ordinary causal chain — token expires, refresh is attempted, refresh is
   rate-limited. It matches AUTH and QUOTA. First-match-wins silently picks AUTH
   and sends an operator to run `codex login`, which cannot lift a rate limit.

2. **Matching spans the whole blob, so unrelated log records fuse.**
   `DEBUG field=quota\nexceeded retry budget while writing transcript`
   matches `quota\s+exceeded` ACROSS the newline. The helper's seam-discipline
   comment is true but narrower than it reads: scanning arguments separately
   prevents bridging BETWEEN arguments, not WITHIN one multi-line string.

3. **Prose cannot be classified by vocabulary.** `RESOURCE_EXHAUSTED: received
message larger than max (4194304 vs. 1048576)` is a payload-size failure read
   as account quota — the caller switches seats, which cannot help. And the
   sponsor-quota / cannot-assist-with / refused-to-answer over-matches are
   ordinary immigration-consultancy sentences.

Meanwhile the vocabulary MISSES the most standard vendor phrasings:
`rate_limit_exceeded`, `exceeded your current quota`, `blocked by the safety
filter`, `I can't assist with`, `violate our usage policy`. Tuning the
alternatives closes those and widens the over-match surface at the same time.
That trade has no good side.

## Why more rounds are barred

Nobody has ever observed what `codex exec` prints on quota exhaustion or a policy
block. The patterns were transferred from a DIFFERENT CLI's cascade grep. Every
further round tunes guesses against guesses, and a green test proves only that a
fixture the author wrote matches a pattern the same author wrote. Per the Agent
PR Contract: when a correction would itself be under-specified, write the spec.

## Required properties (the spec)

**P1 — Multi-match is explicit, never implicit.** Evaluate every class, not the
first hit. If two classes match one payload, that is a defined outcome — an
`AMBIGUOUS` result carrying both — not a silent precedence. Precedence may exist
only where a stated reason justifies it, and the reason belongs in the code.

> **Amendment (orchestrator, after B2b asked).** `AMBIGUOUS` here is an INTERNAL
> concept, not a proposed eighth member of F3's vocabulary. F3 is frozen at seven
> and this spec does not reopen it. An ambiguous classification surfaces
> externally as `INTERNAL` with a detail naming every candidate class, so nothing
> is dropped and no silent pick occurs. A losing class must likewise survive in
> the result (a `suppressed` field or equivalent) rather than being discarded as
> an intermediate — otherwise a later reader of a QUOTA verdict cannot tell that
> auth wording was also present, which is the whole point of P1.

**P2 — Classify per record, never across the blob.** Split stderr into lines (or
whatever record boundary the CLI actually emits) and classify each. A class must
never be assembled from two records. This kills defect 2 by construction rather
than by pattern care.

**P3 — Prefer machine-readable evidence to prose.** Where stderr carries a
structured token (an error code, a JSON field, an HTTP status line), classify on
that. Prose is the fallback, and a prose-derived class is marked lower-confidence
than a token-derived one.

**P4 — Confidence is part of the result.** An unobserved-vendor-wording guess and
a matched error code are not the same fact and must not produce the same value. A
caller may act on high confidence and must degrade gracefully on low.

**P5 — Unknown stays unknown.** The generic process-error bucket is the correct
answer for anything unrecognised. Widening a pattern to avoid it is how over-match
enters.

**P6 — Guilt AND innocence under test.** Every class needs both: strings that must
match, and strings that must NOT — including the 12 reproduced findings above as
permanent regression fixtures, and ordinary IT/EN/ID consultancy sentences as
innocence fixtures. A guard with only guilt tests is scar family #3.

**P7 — Disjointness, if still claimed, is TESTED.** If any code path depends on
classes not overlapping, a test must assert it on realistic COMPOSITE payloads,
not on each vocabulary's own alternatives in isolation. That weaker test is
exactly what let this through: it measured the vocabularies and was read as
settling a claim about payloads.

**P8 — Negation suppression is SPECIFIED before it is patterned.** A token that is
present but negated must not classify. This was patched twice and was wrong both
times, so the rule is written here before a third pattern is touched.

Measured on `5f889df9d` by executing the compiled patterns (2026-08-26), all
producing a full RED alarm today:

| input                             | class | why it slips through                                                                                                                           |
| --------------------------------- | ----- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `{"token_revoked": "false"}`      | AUTH  | the round-4 lookahead has ONE optional-quote slot and it sits BEFORE the separator, so it can close a quoted KEY but never open a quoted VALUE |
| `{"insufficient_quota": "false"}` | QUOTA | same                                                                                                                                           |
| `authentication error: none`      | AUTH  | the PROSE patterns received no guard at all — never a decision, simply never extended                                                          |
| `usage limit reached: false`      | QUOTA | same                                                                                                                                           |
| `rate limit reached: no`          | QUOTA | `no` is not in the negation vocabulary                                                                                                         |
| `{"token_revoked": "okay"}`       | AUTH  | a code comment promises `ok`/`okay`; `\b` structurally cannot match inside `okay`, so it never delivered                                       |

The spec must answer, and the answers belong in the code: which value forms count
as negation (with the REJECTED ones named — `0` is a plausible member and a bad
one); what separates a name from its value, with optional quoting on EITHER side;
whether PROSE is in scope (it is not today, and nobody decided that); and the
guilty set that must keep firing — a guard that silences a real dead credential is
worse than the over-match it replaced.

The corpus is DERIVED from that matrix — value forms x separators x quoted/unquoted
x structured/prose, generated — never hand-picked. Two independent hand-built
corpora (five strings and six) both missed the quoted-value form and the entire
prose surface, because each was enumerated by someone who had just read the
pattern, and the pattern IS its author's model of the input space. Generation is
what removes the author from the enumeration; a bigger hand-written corpus is not.

**P9 — No alternative may end in an optional sub-group when a suffix-sensitive
lookahead follows it.** A negation lookahead attached after an alternation is
defeated by backtracking whenever an alternative ends in `(?:...)?`: the engine
drops the optional, the match ends early, and the lookahead's own `[:=\s]+`
aligns against the leftover text instead of the real value.

Reproduced by construction on 2026-08-26 (`_QUOTA_PROSE_RE` carries exactly this
shape in `usage\s+limit(?:\s+reached)?`), python 3.11.15:

| input                        | trailing optional          | no trailing optional | possessive `?+` |
| ---------------------------- | -------------------------- | -------------------- | --------------- |
| `usage limit reached: false` | **MATCH** (guard bypassed) | no                   | no              |
| `usage limit reached: true`  | MATCH                      | MATCH                | MATCH           |

Row 1 is the defect; row 2 is what makes any cure acceptable — the genuine
positive must survive it. Either the optionality is made possessive or the
alternative is split into two explicit ones.

The consequence for P8's corpus is the part that is easy to miss: **the generator
must range over the ALTERNATIVES, not only over the input forms.** A matrix of
vocabulary x separator x quoting is still blind here, because this hazard lives in
the pattern's own structure rather than in the input's. For every alternative
carrying a trailing optional, the corpus needs its negated form.

A note on method, recorded because it cost three attempts: this property was first
checked STRUCTURALLY, by parsing alternatives out of the pattern and looking for
ones ending in `)?`. That reported "none" — the splitter did not handle nested
groups and the display truncated at 200 characters, while
`usage\s+limit(?:\s+reached)?` sat inside the truncated tail. Only executing the
two variants settled it. On this surface, parse-and-reason has now produced a
false negative every single time it was tried.

## Arming condition

This stays dark until a REAL `codex exec` quota event and a REAL policy block have
been observed and their exact stderr recorded here. Until then the classification
is advisory and no caller may take an irreversible action on it. The first real
event IS the measurement — the same way the auth pattern earned its one anchor.

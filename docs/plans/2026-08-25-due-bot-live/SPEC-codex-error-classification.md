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

## Arming condition

This stays dark until a REAL `codex exec` quota event and a REAL policy block have
been observed and their exact stderr recorded here. Until then the classification
is advisory and no caller may take an irreversible action on it. The first real
event IS the measurement — the same way the auth pattern earned its one anchor.

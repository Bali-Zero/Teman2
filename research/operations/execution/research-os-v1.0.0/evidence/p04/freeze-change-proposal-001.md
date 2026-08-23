---
adversarial_review: pending
---

# Freeze-change proposal 001 — UTC timestamp wire spelling vs. §2 hash-identity promise

- **From**: builder session, work packet P04 (Research OS v1.0.0, Wave 0), PR #4615
- **To**: S9-C0 (Conductor)
- **Date**: 2026-08-23
- **State**: `awaiting_conductor_decision` — PR #4615 suspended unarmed pending this decision
- **Measured at**: 2026-08-23, worktree `.worktrees/backend-rag-ros-v1-p04-hash-parity`,
  branch `agent/nuzantara/backend-rag/ros-v1-p04-hash-parity`, base `868b62322`

## 0. Status of the code on PR #4615 — do not build on it

PR #4615 (commit `aa99a9e50`) attempted a code-only fix and is **DEFECTIVE**, confirmed by
independent re-reproduction below, not taken on the reviewer's word. **This proposal supersedes
that fix; the PR stays unarmed and untouched pending this decision** — no further commit or push
has been made to it while this document was written.

## 1. The finding

CONTRACTS.md §2 requires: "the hash procedure must be identical in every implementation," computed
by (1) validating against the exact contract version, (2) serializing with RFC 8785 JCS, (3)
encoding UTF-8, (4) computing lowercase-hex SHA-256. CONTRACTS.md §3's `UtcDateTime` primitive
(`primitives.py:84`, `_UTC_OFFSET_PATTERN = r"(?:Z|\+00:00)$"`) simultaneously declares **two wire
spellings of the same instant equally valid**, and places no constraint on fractional-second digit
count. These two clauses are jointly inconsistent: nothing in RFC 8785 normalizes datetime
*semantics* (only JSON *structure*), so two schema-legal spellings of one instant survive
canonicalization as different byte strings and hash differently. This is a defect in the frozen
text itself, not in any one implementation of it — §21's stop condition applies: "If implementation
evidence contradicts this freeze, stop and raise a versioned freeze-change proposal. Silent
semantic drift is a failed gate."

## 2. Evidence

### 2.1 The original divergence (independently reproduced, both foundation contract kinds)

```
revocation_receipt.issued_at:      2026-02-01T00:01:00Z  vs  2026-02-01T00:01:00+00:00
object_successor_edge.recorded_at: 2026-01-01T00:01:00Z  vs  2026-01-01T00:01:00+00:00
```
Rewriting either fixture's field from `Z` to `+00:00` and recomputing `object_hash()` over the raw
dict, then validating: both are rejected `object_hash_mismatch`. Root cause: the model-path hash
re-renders through `pydantic`'s `model_dump(mode="json")`, which always normalizes to `Z`; the
dict-path hashes the wire bytes verbatim. `cli hash --file X` (dict path) and `cli validate
--contract K --file X` (model path) therefore disagree on the same file — the package's own two
public verbs contradict each other on a document the schema itself calls valid.

### 2.2 A second, independent divergence axis on the same field type

`_UTC_OFFSET_PATTERN` places no constraint on fractional-second digit count. `model_dump` always
renders microsecond=0 with no fraction and any nonzero microsecond zero-padded to exactly 6 digits:
```
microsecond=0      -> "2026-01-01T00:00:00Z"
microsecond=500000 -> "2026-01-01T00:00:00.500000Z"
M.model_validate({"t": "...00.1Z"}).model_dump()["t"] -> "...00.100000Z"
```
`"...00.5Z"` and `"...00.500000Z"` name the same instant and are both schema-legal, and hash
differently through the same two paths, for the identical root cause as §2.1. Any spec amendment
must close both axes or it reopens the same bug under a different disguise.

### 2.3 `_UTC_OFFSET_PATTERN` is export-only — Python runtime is more permissive than the wire schema

`_UTC_OFFSET_PATTERN` reaches `UtcDateTime` through `WithJsonSchema({...})` only, never through
`Field(pattern=...)`. `WithJsonSchema` affects `model_json_schema()` export only; pydantic never
runs it as a runtime check. Confirmed empirically — Python accepts strings the exported JSON Schema
would reject:
```
'2026-02-01T00:01:00+0000'   (no colon)  -> pydantic ACCEPTS, dump='...Z'  ; schema pattern REJECTS
'2026-02-01T00:01:00.123456789Z' (ns)    -> pydantic ACCEPTS, dump='...123456Z' (silently truncated)
'2026-02-01 00:01:00Z'   (space not 'T') -> pydantic ACCEPTS, dump='...T00:01:00Z'
```
A cross-language consumer validating strictly against the exported schema would reject documents
Python's own validator (and hence this repository's producers) happily accepts. This means "edit
`_UTC_OFFSET_PATTERN` to accept only `Z`" — the narrower fix considered and rejected below — is a
**no-op against every finding in this section**: that constant is never consulted at runtime, so
editing it changes only `schemas/*.schema.json` output, not `object_hash`/`validate_receipt`/
`validate_edge` behavior.

### 2.4 Why the code-only cure (PR #4615) is disqualified, not merely imperfect

PR #4615 attempted to fold both spellings to one canonical form inside `hashing.py`, applied
generically to every string in the document tree (a pragmatic attempt to avoid narrowing the frozen
schema or touching `primitives.py`, which sibling lanes are actively extending for the other seven
contract kinds). Cross-family refutation, independently reproduced here rather than taken on trust:

**Finding A — hash collision across different documents (CRITICAL).** The generic fold has no
concept of which fields are typed `UtcDateTime`. `RevocationReceipt.idempotency_key` is
`str, min_length=1` — free text, and systems routinely mint idempotency keys from timestamps:
```
idempotency_key='2026-02-01T00:01:00Z'      -> object_hash 573bb6ae26011fb0e396...  model_validate OK
idempotency_key='2026-02-01T00:01:00+00:00' -> object_hash 573bb6ae26011fb0e396...  model_validate OK
COLLISION: True
```
Two documents with **different content** are indistinguishable by `object_hash` and both validate.
Weighed against the bug being cured — a loud rejection at the gate — this is worse: a silent
identity corruption in the one property `object_hash` exists to guarantee. The docstring on the
fold called it "deliberately narrow, not a general timezone/format normalizer: only the two
spellings the frozen schema itself declares equivalent are folded" — narrow on *spelling*, unbounded
on *field*. Conflating those two axes is how the defect passed self-review.

**Finding B — the fix's own docstring cites a nonexistent artifact.** `hashing.py` claimed "see
CONTRACTS.md §2 follow-up amendment tracked alongside this fix." `git diff --name-only 868b62322
aa99a9e50` touches only `hashing.py` and one new test file; `CONTRACTS.md` contains zero matches for
`fold`/`spelling`/`+00:00`. No such amendment exists, tracked or otherwise. Independently confirmed.

**Finding C — bare `ValueError` escapes the public API (HIGH, only reachable because of A).** The
recognizer regex checks digit *shape*, not calendar *validity*:
```
2026-02-01T00:01:60Z -> ValueError: second must be in 0..59   (bare, not CanonicalizationError)
2026-13-01T00:01:00Z -> ValueError: month must be in 1..12
2026-02-01T25:01:00Z -> ValueError: hour must be in 0..23
```
A caller catching the documented `CanonicalizationError` ("not JCS-canonicalizable") misses these.

All three independently reproduced against the exact commit on PR #4615 before writing this
section (repro commands available on request; omitted here for length, present in the review
thread).

### 2.5 Live blast radius today: zero, measured per-ref, not per-instruction

Every fixture in this packet (`packages/research-os-core/fixtures/**/*.json`) uses canonical `Z`;
`grep -rn '+00:00'` over the fixture tree returns nothing, and the only non-`Z` timestamp anywhere
in the tree is `revocation_receipt/invalid_issued_at_not_utc.json`'s `+08:00`, a genuinely
non-UTC offset that is correctly rejected today and unaffected by this proposal either way.

The claim that no live producer exercises the divergent spelling should rest on an **outcome**
(what every dispatched lane actually wrote), not an **input** (what any lane was told to write) —
the latter says nothing about lanes dispatched before an instruction existed. Measured across every
relevant ref, 2026-08-23:

| Ref | Fixture files | `+00:00` spellings |
|---|---:|---:|
| `main` | 20 | 0 |
| `ros-v1-p04-d1-evidence-spine` | 88 | 0 |
| `ros-v1-p04-d1-decision-chain` | 87 | 0 |
| `ros-v1-p04-d1-operator-decisions` | 70 | 0 |
| `ros-v1-p04-d1-workflow-outcome` | 55 | 0 |
| `ros-v1-p04-d1-outcome-event` | 68 | 0 |

388 fixture files across six refs, zero `+00:00` spellings anywhere, including the two lanes
dispatched before any Z-only instruction existed. The defect is real and reachable by any
wire-conformant producer, but nothing on `main`, in this packet, or on any currently-dispatched
sibling lane exercises it today — this is a preventive correctness gap, not a live incident.

## 3. Why this is a stop, not a silent patch

Per §21: an implementation-evidence contradiction with the freeze stops work and raises a versioned
proposal; workers do not resolve it independently. §2.4 shows the code-only path was tried and
failed on the axis that matters most (identity collision) precisely because a hashing-layer fix
cannot know which fields are semantically timestamps without either (a) importing the per-contract
models into `hashing.py` — which creates a circular import, since every model already imports
`object_hash` from `hashing.py` — or (b) accepting the exact field-blindness that caused Finding A.
Closing this at the type layer, where `UtcDateTime` already knows what it is, requires either
narrowing the frozen schema (a version-relevant contract change) or leaving two spellings
permanently un-interoperable at the hash layer. Both are Conductor-level calls, not something a
worker patches around.

## 4. Requested decision

**Recommendation: amend CONTRACTS.md §2/§3 to declare exactly one legal UTC timestamp wire
spelling, enforced by a runtime check on `UtcDateTime` itself (not in `hashing.py`).**

The strongest argument for this shape, stated first because it is the one that matters most: a
`BeforeValidator` attached to `UtcDateTime` cannot reproduce Finding A **structurally, not merely by
being more careful**. Pydantic invokes a field's validator chain only for that field — a validator
living on `UtcDateTime` is never called with `idempotency_key`'s value, or any other field's value,
under any input. This is not "we will be careful not to touch free-text fields this time" (which is
exactly what the disqualified fix in §2.4 believed about itself); it is that the collision's
precondition — one function inspecting values without knowing which field they came from — cannot
occur in this shape at all. That is the difference between a fix that happens to be correct and a
fix that cannot be wrong in this particular way.

Once only one spelling is schema-legal, any document that passes model validation is canonical by
construction. `hashing.py` needs **no change of any kind** — the dict-path and model-path trivially
agree because there is only one wire-legal string to hash, per field, ever. Findings A and C in
§2.4 cannot recur: there is no generic normalizer touching arbitrary fields, because there is
nothing left to normalize.

**Sub-decision 1 — exact canonical form (pick one):**

- **(a) Match pydantic's existing convention** — `Z` suffix; fractional seconds omitted when
  exactly zero, else exactly 6 digits. Lower rejection cost: any producer already emitting this
  exact convention (which is what pydantic itself emits, so any producer round-tripping through
  this package already does) needs to change nothing. Regex:
  `^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{6})?Z$`
- **(b) No fractional seconds ever** — simpler spec text, cheaper to port to Go/TS/Java (no
  "zero-omitted, else exactly 6" rule to describe or test), but rejects any producer sending
  legitimate sub-second precision. Regex: `^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$`

Given every timestamp in this frozen contract family is a workflow/audit-level event
(`issued_at`, `recorded_at`, `verified_at`, …), not high-frequency telemetry, (b) is plausibly
sufficient and is the simpler spec surface — but (a) costs nothing extra in code (§5 sketch is
identical either way, one regex literal differs) and preserves capability. No strong recommendation
between them from this document; flagging the trade-off for the Conductor.

**Sub-decision 2 — enforcement point:** reject non-canonical spellings outright at validation
(`BeforeValidator` on `UtcDateTime`, §5 sketch), not "accept and silently normalize." A producer
choosing to always emit the canonical form from the start costs nothing (every RFC3339 formatter
either defaults to `Z` or can be told to); "normalize on the way in" was considered and rejected
because it re-opens exactly the same field-blindness problem in a different location, unless
scoped per-typed-field (which is what a **rejecting** `BeforeValidator` already does for free by
running only inside `UtcDateTime`'s own validation chain — it never sees `idempotency_key` or any
other field, because pydantic only invokes a field's validators for that field).

**Cost, stated plainly:** any historical or future document spelling a UTC timestamp as `+00:00`,
or (if (a) is chosen) with non-canonical fractional-second padding, is **rejected** once ratified.
Per CONTRACTS.md rule 10 ("meaning changes... are major unless the compatibility matrix proves
otherwise"), this plausibly needs a version determination — that determination belongs to the
Conductor, not this document. Given §2.5's measured zero live blast radius, the practical cost today
is believed to be zero, but the rule-10 question is separate from the practical-impact question and
this document does not presume to answer it.

**Side effect, free:** enforcing exact-match to the one canonical form also closes the
over-permissive-parser gaps in §2.3 (`+0000` no-colon, space separator, nanosecond truncation) with
no additional code — those inputs simply no longer match the one accepted pattern either.

## 5. Implementation sketch — NOT applied, conditional on ratification of §4

Sketch only. Not committed, not pushed, not run against the gates. Exact regex depends on §4
sub-decision 1; sketch below uses variant (a).

```python
# primitives.py
_UTC_CANONICAL_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{6})?Z$")

def _reject_noncanonical_utc_spelling(value: Any) -> Any:
    if isinstance(value, str) and not _UTC_CANONICAL_RE.match(value):
        raise PydanticCustomError(
            "utc_timestamp_noncanonical_spelling",
            "UTC timestamp must be spelled exactly as e.g. "
            "2026-01-01T00:00:00Z or 2026-01-01T00:00:00.123456Z",
        )
    return value

UtcDateTime = Annotated[
    datetime,
    BeforeValidator(_reject_noncanonical_utc_spelling),
    AfterValidator(_utc_datetime),
    WithJsonSchema(
        {"format": "date-time", "pattern": _UTC_CANONICAL_RE.pattern, "type": "string"}
    ),
]
```

Follow-up work this implies, once ratified (not scoped/estimated here):

- `write_schema_artifacts()` regeneration for both implemented contract kinds' `schemas/*.schema.json`.
- No new fixtures needed for the happy path — every checked-in fixture already uses the canonical
  form (§2.5) and would continue to validate unchanged.
- One new `invalid_*` fixture per implemented contract kind exercising `+00:00` rejection, mirroring
  the existing `invalid_issued_at_not_utc.json` pattern.
- `test_every_schema_pattern_compiles_under_ecma_262` should be re-run against the new pattern —
  fixed-width digit classes, no possessive/atomic constructs, expected to pass unchanged.
- Revert PR #4615's `hashing.py`/test-file diff in full once this lands; no trace of the field-blind
  fold should reach `main`.
- CONTRACTS.md §2/§3 prose amendment itself — this document is the proposal for that amendment, not
  the amendment text; the Conductor's ratified wording is the source of truth, not this sketch.

## 6. What happens meanwhile

PR #4615 stays open, unarmed, untouched beyond this document's own evidence-gathering. No commit,
no push. The team-lead reviewer is filing a `PENDING-ARMS` line pointing at this document.

## Adversarial review

Not yet run. Unlike the precedent this document follows in form
(`ledger-revision-request-001.md`, which received independent Codex and Kimi K3 review before
being finalized), this proposal has not been through a cross-family adversarial pass — only the
team-lead reviewer's refutation of the *prior code fix* (§2.4, independently re-reproduced above)
and this document's own author. State this gap explicitly rather than imply parity with the
precedent: a second-family review of this document itself is owed before the Conductor treats it as
load-bearing.

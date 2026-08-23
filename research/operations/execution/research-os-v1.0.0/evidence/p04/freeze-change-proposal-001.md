---
adversarial_review: kimi-k3
---

# Freeze-change proposal 001 — UTC timestamp wire spelling vs. §2 hash-identity promise

- **From**: builder session, work packet P04 (Research OS v1.0.0, Wave 0), PR #4615
- **To**: S9-C0 (Conductor)
- **Date**: 2026-08-23
- **State**: `awaiting_conductor_decision` — PR #4615 suspended unarmed pending this decision
- **Measured at**: 2026-08-23, worktree `.worktrees/backend-rag-ros-v1-p04-hash-parity`,
  branch `agent/nuzantara/backend-rag/ros-v1-p04-hash-parity`, base `868b62322`
- **Revised at**: 2026-08-23, following cross-family adversarial review (Kimi K3, findings
  independently reproduced by a Claude reviewer). Re-verification ran from
  `.worktrees/docs-ros-v1-p04-freeze-change-001` (this document), cross-checked against
  `.worktrees/backend-rag-ros-v1-p04-hash-parity` (§2.4's inlined repro, exact commit `aa99a9e50`)
  and the primary checkout plus every currently-live `ros-v1-p04-d1-*` worktree (§2.5/§2.6's
  blast-radius and consumer sweep). Six holes in this document's own reasoning were found and
  closed — see the Adversarial review section at the end. The underlying finding (§1-§3) and the
  disqualification of PR #4615 (§2.4) were not in question and are unchanged.

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
section. The commands (run from `.worktrees/backend-rag-ros-v1-p04-hash-parity`, HEAD `aa99a9e50`,
`PYTHONPATH=packages/research-os-core`):

```python
import json
from research_os.hashing import object_hash, canonicalize, CanonicalizationError
from research_os.models.revocation_receipt import RevocationReceipt

base = json.load(open("fixtures/revocation_receipt/valid_minimal.json"))
for key in ("2026-02-01T00:01:00Z", "2026-02-01T00:01:00+00:00"):          # Finding A
    doc = {**base, "idempotency_key": key}
    doc["object_hash"] = object_hash(doc)
    print(key, "->", doc["object_hash"], "valid:", bool(RevocationReceipt.model_validate(doc)))

for bad in ("2026-02-01T00:01:60Z", "2026-13-01T00:01:00Z", "2026-02-01T25:01:00Z"):  # Finding C
    try:
        canonicalize({"t": bad})
    except CanonicalizationError:
        print(bad, "-> documented CanonicalizationError")
    except ValueError as e:
        print(bad, "-> bare", type(e).__name__, "(undocumented):", e)

# Finding B — no such artifact:
#   git diff --name-only 868b62322 aa99a9e50   -> hashing.py + one new test file only
#   git show 868b62322:research/operations/specs/evidence-to-action-freeze-2026-08-15/CONTRACTS.md \
#     | grep -c 'fold\|spelling\|+00:00'        -> 0 for all three terms
```

Output, verbatim: both `idempotency_key` spellings print the identical
`object_hash=573bb6ae26011fb0e396972ac7d4d78e1843e5433862298864b1f707dbd4b776` and both validate
(Finding A); all three malformed timestamps print `bare ValueError` (Finding C); the `git diff`
touches only `hashing.py` and one test file, and all three grep terms return `0` (Finding B).

### 2.5 Live blast radius today: zero on both axes, measured per-ref, not per-instruction

Every fixture in this packet (`packages/research-os-core/fixtures/**/*.json`) uses canonical `Z`;
`grep -rn '+00:00'` over the fixture tree returns nothing, and the only non-`Z` timestamp anywhere
in the tree is `revocation_receipt/invalid_issued_at_not_utc.json`'s `+08:00`, a genuinely
non-UTC offset that is correctly rejected today and unaffected by this proposal either way.

The claim that no live producer exercises the divergent spelling should rest on an **outcome**
(what every dispatched lane actually wrote), not an **input** (what any lane was told to write) —
the latter says nothing about lanes dispatched before an instruction existed. §4's cost paragraph
separately prices a second axis — non-canonical fractional-second padding under option (a) — that
the original sweep here never measured; it is included below rather than left priced-but-unchecked.

Re-measured 2026-08-23 against every `ros-v1-p04-d1-*` sibling lane currently live. Two more have
started since this document's first snapshot (`governance-receipts`, `metrics`); a third
pre-existing lane (`content`) was omitted from the original table entirely; `decision-chain` and
`outcome-event` exist only as local branches, not yet pushed to `origin`, so `git ls-tree`/`git
grep` against the local ref is the only way to measure them:

| Ref | HEAD | Fixture files | `+00:00` spellings | non-canonical fractional padding |
|---|---|---:|---:|---:|
| `main` | `638ef9115` | 89 | 0 | 0 |
| `ros-v1-p04-d1-evidence-spine` | `59cdb8b81` | 89 | 0 | 0 |
| `ros-v1-p04-d1-decision-chain`* | `940f359b1` | 89 | 0 | 0 |
| `ros-v1-p04-d1-operator-decisions` | `b36792570` | 71 | 0 | 0 |
| `ros-v1-p04-d1-workflow-outcome` | `cee0fa7f9` | 55 | 0 | 0 |
| `ros-v1-p04-d1-governance-receipts` | `99a120e1d` | 47 | 0 | 0 |
| `ros-v1-p04-d1-metrics` | `f284cfa95` | 115 | 0 | 0 |
| `ros-v1-p04-d1-content` | `e8a5d0435` | 126 | 0 | 0 |
| `ros-v1-p04-d1-outcome-event`* | `e7d20be9a` | 68 | 0 | 0 |

\* local-only branch, not on `origin`, at time of this measurement.

749 fixture files across nine currently-live refs (up from 388 across six refs in the original
snapshot: the three newly-included lanes — `governance-receipts`, `metrics`, `content` — contribute
288 files that were not counted before, and the six refs already measured have themselves grown by
73 files combined, from 388 to 461, since the original snapshot), zero `+00:00` spellings and zero
non-canonical fractional-second timestamps anywhere. Method for the new column: `git grep -noE
'[0-9]{2}\.[0-9]+Z'` over each ref's fixture tree; the pattern was verified to actually find
matches when present (spot-checked against `hashing.py`'s own docstring examples, which contain
both a 3-digit and a 6-digit fractional timestamp — both matched, confirming the zero result on
fixtures is a true negative, not a broken probe). The defect is real and reachable by any
wire-conformant producer, but nothing on `main`, in this packet, or on any currently-live sibling
lane exercises it today, on either axis — this is a preventive correctness gap, not a live
incident.

### 2.6 The premise behind "practical cost today is zero": no consumer exists yet

§2.5 measures the fixture universe as if it were the entire universe of documents this proposal
could affect. That equivalence is not asserted, it is verified: nothing outside
`packages/research-os-core` imports `research_os` today except its own test suite
(`apps/backend-rag/backend/tests/unit/research_os/`):

```
$ git grep -rln -E '(from research_os|import research_os)' -- '*.py' \
    | grep -v '^packages/research-os-core/' | grep -v '/tests/'
<no output, exit 1>
```

No persistence layer, no API route, no other app or package in this monorepo consumes this
package, and no other `pyproject.toml` declares it as a dependency. The fixture tree measured in
§2.5 genuinely is the entire universe of research-os documents written anywhere today, not a
sample of it.

This is a stronger basis for "practical cost zero" than the grep alone: a grep over fixtures shows
only that the sample it looked at contains no counterexample; this premise shows the sample **is**
the population. It also makes the conclusion's expiry condition explicit, where the grep-only
framing left it implicit: this stops being true the moment any consumer — a persistence layer, an
external API, a cross-package import — is written against `research_os`. That is not a
hypothetical: P04's own mandate is to build exactly such consumers. The zero-cost conclusion is a
snapshot of a codebase that has not yet built what it is being built to build, not a durable
property of the contract.

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
construction — **conditional on §5's guard actually enforcing that**, which the first draft of it
did not (§5.1 reproduces the hole and the fix). `hashing.py` needs **no change of any kind** — the
dict-path and model-path trivially agree because there is only one wire-legal string to hash, per
field, ever. Findings A and C in §2.4 cannot recur: there is no generic normalizer touching
arbitrary fields, because there is nothing left to normalize.

**Sub-decision 1 — exact canonical form (pick one):**

- **(a) Match pydantic's existing convention** — `Z` suffix; fractional seconds omitted when
  exactly zero, else exactly 6 digits. Lower rejection cost: any producer already emitting this
  exact convention (which is what pydantic itself emits, so any producer round-tripping through
  this package already does) needs to change nothing. Regex:
  `^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{6})?Z$`
- **(b) No fractional seconds ever** — simpler spec text, cheaper to port to Go/TS/Java (no
  "zero-omitted, else exactly 6" rule to describe or test), but rejects any producer sending
  legitimate sub-second precision. Regex: `^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$`

**Recommendation: (a).** Not "no strong preference either way" — (b) has a self-inconsistency (a)
does not.

Every timestamp in this frozen contract family can be constructed from a live Python `datetime`
object on the ordinary internal path, not only parsed from wire JSON — `packages/research-os-core`
already does this (`recorded_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index)`,
`apps/backend-rag/backend/tests/unit/research_os/test_graph.py:20`, constructing a `GraphMember`
whose `recorded_at` is `UtcDateTime`). That path is untouched by whichever regex sub-decision 1
picks: a `BeforeValidator`'s string-format check never runs against a value that was never a
string. `datetime.now(timezone.utc)` routinely carries a nonzero microsecond, and `model_dump()`
renders it through pydantic's own ISO-8601 serializer regardless of which wire-string pattern is
in force. Reproduced for both options, microsecond ∈ {0, 1, 500000, 123456}:

| microsecond | `model_dump()` output | matches (a)'s pattern | matches (b)'s pattern | re-validating the dump under (b) |
|---:|---|:---:|:---:|---|
| 0 | `2026-01-01T00:00:00Z` | ✅ | ✅ | OK |
| 1 | `2026-01-01T00:00:00.000001Z` | ✅ | ❌ | **REJECTED** |
| 500000 | `2026-01-01T00:00:00.500000Z` | ✅ | ❌ | **REJECTED** |
| 123456 | `2026-01-01T00:00:00.123456Z` | ✅ | ❌ | **REJECTED** |

Under (b), the package can legitimately *construct* a document with
`issued_at=datetime.now(timezone.utc)`, `model_dump()` it, and have that exact document — the
package's own emitted output — **rejected** if fed back through `model_validate()`. That is a
round-trip failure of the package's own invariant, not a hypothetical interoperability gap. (a) has
no such hole: every microsecond value dumps to something (a)'s own pattern accepts, by
construction — zero omits the fraction, anything else is exactly 6 digits, which is exactly what
Python's zero-padded microsecond formatting always produces.

**Cost of (a), disclosed rather than assumed zero:** no *Python* producer pays anything — pydantic's
own serializer already emits (a)'s exact form — but non-Python producers do not get this for free.
Node's native formatter always emits exactly 3 fractional digits, never zero-padded to 6 and never
omitted even at zero microseconds. Reproduced:

```
$ node -e "console.log(new Date('2026-01-01T00:00:00.000Z').toISOString())"
2026-01-01T00:00:00.000Z
$ node -e "console.log(new Date('2026-01-01T00:00:00.500Z').toISOString())"
2026-01-01T00:00:00.500Z
```

Neither string matches (a)'s `(?:\.\d{6})?Z` — a 3-digit fraction is never 0 digits and never 6.
**Every document a Node producer emits via `Date.prototype.toISOString()` unmodified is rejected by
(a) once ratified.** Go's `time.RFC3339Nano` has the analogous problem with a different digit
convention — reproduced, it trims to the minimum digits needed rather than padding to a fixed
width (`500ms → .5Z`, `123ms → .123Z`, neither 0 nor 6 digits). Java's `Instant.toString()` is
documented to behave the same way in shape — a variable fractional-digit count driven by precision,
not (a)'s fixed 0-or-6 — though no JRE was available in this environment to run it directly, so
that one is asserted from documented behavior, not reproduced here.

This is not a reason to widen (a)'s pattern to accept multiple fraction-digit-counts: doing so
reopens the exact defect this proposal exists to close (§2.2) — `.5Z` and `.500000Z` would again be
independently wire-legal spellings of the same instant, hashing differently. The pattern stays
exact-match, single-spelling; that is not negotiable given what this document is for. The migration
cost is real and belongs on the ledger, not papered over: **every non-Python producer needs an
explicit canonicalization step before emitting a `UtcDateTime` field.** For Node, e.g.:

```js
const canonical = iso.replace(/\.(\d{3})Z$/, (_, ms) => ms === '000' ? 'Z' : `.${ms}000Z`);
```

Reproduced: `.000Z` → `Z` (fraction omitted); `.500Z` → `.500000Z`; `.123Z` → `.123000Z` — all three
now match (a) exactly. Go and Java need the analogous one-line adaptation (pad/truncate to exactly
6 digits, or omit at zero) before emitting into this contract family. This is a real, disclosed
migration cost for any future non-Python producer, not a zero-cost claim.

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
otherwise"), this plausibly needs a version determination. The escape hatch in that rule is not
obviously invocable here: the only artifact in this repository calling itself a compatibility
matrix for research-os/v1.0.0 is `evidence/p04/schema-inventory-001.md`'s proposed `reader_status`
field-level matrix (`live_reader` / `write_only` / `dead` per field) — a legacy-field-mapping
deliverable, unrelated to wire-timestamp spelling, and itself still a forward-looking
recommendation ("the compatibility matrix P04 produces next") rather than a ratified artifact.
Absent a compatibility matrix that actually addresses this question, rule 10's plain-text
default — MAJOR — applies, unless the Conductor rules otherwise.

A genuine counter-consideration the Conductor should weigh against that default, using ground §1
already laid but never deployed against rule 10: §2 ("the hash procedure must be identical in every
implementation") and §3 (`UtcDateTime` declaring two wire spellings simultaneously valid) are
**jointly inconsistent as frozen** — that is §1's own finding. Rule 10's MAJOR default presumes a
change moves the spec from one coherent meaning to a different coherent meaning. Narrowing §3 to
the single spelling §2 already implicitly requires does not do that: there is no second coherent
meaning to move away from, because the frozen text as written does not have one determinate meaning
on this point to begin with. That makes narrowing §3 contradiction-repair, not a meaning change in
the sense rule 10 is written to gate — a real argument for treating this as a clarification, not
mechanically resolved by the plain-text MAJOR/MINOR test alone. This document does not resolve that
tension in either direction; it hands the Conductor both readings rather than picking one.

Given §2.5's measured zero live blast radius (now including the fractional-padding axis) and §2.6's
verified premise that no consumer outside `packages/research-os-core` exists yet, the *practical*
cost today is zero on the evidence gathered — grounded in what was measured, not merely believed.
That is independent of, and does not resolve, the rule-10 version-determination question above.

**Side effect, free:** enforcing exact-match to the one canonical form also closes the
over-permissive-parser gaps in §2.3 (`+0000` no-colon, space separator, nanosecond truncation) with
no additional code — those inputs simply no longer match the one accepted pattern either.

## 5. Implementation sketch — NOT applied, conditional on ratification of §4

Sketch only. Not committed, not pushed, not run against the gates. Exact regex depends on §4
sub-decision 1 (now recommending variant (a) with the round-trip evidence above); sketch below uses
variant (a).

### 5.1 The first draft had its own field-blind hole — reproduced, then closed

The first draft of `_reject_noncanonical_utc_spelling` checked spelling only when the raw input was
already a Python `str`:

```python
def _reject_noncanonical_utc_spelling(value: Any) -> Any:
    if isinstance(value, str) and not _UTC_CANONICAL_RE.match(value):
        raise PydanticCustomError("utc_timestamp_noncanonical_spelling", "...")
    return value
```

Pydantic's lax mode accepts a JSON **number** for a `datetime`-typed field, interpreting it as a
Unix timestamp. `isinstance(value, str)` is `False` for a number, so the guard is skipped entirely
— the number passes through unchecked, is coerced to a `datetime` by pydantic's core validator, and
dumps to the canonical `Z` form. Reproduced against the draft above:

```
>>> class M(BaseModel):
...     t: Annotated[datetime, BeforeValidator(_reject_noncanonical_utc_spelling)]
>>> M.model_validate({"t": 1767225600}).model_dump(mode="json")
{'t': '2026-01-01T00:00:00Z'}
```

This falsifies §4's headline claim as drafted: a wire document `{"issued_at": 1767225600}`
(dict-path, hashed verbatim by `hashing.py`) and the same instant spelled
`{"issued_at": "2026-01-01T00:00:00Z"}` (model-path, re-rendered through `model_dump`) hash to
*different* byte strings even after `model_validate` accepts both — the exact §2.1 divergence
class this proposal exists to close, surviving the cure that was supposed to close it.

The fix is **not** "reject any non-`str` input" — `packages/research-os-core` already constructs
`UtcDateTime` fields from a live Python `datetime` object on the ordinary internal path, not from
wire JSON (`recorded_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index)`,
`apps/backend-rag/backend/tests/unit/research_os/test_graph.py:20`, building a `GraphMember`).
Rejecting every non-`str` input blocks that legitimate path too — reproduced:

```
>>> def naive_fix(v):
...     if not isinstance(v, str) or not _UTC_CANONICAL_RE.match(v):
...         raise PydanticCustomError("utc_timestamp_noncanonical_spelling", "...")
...     return v
>>> M(t=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=5))
ValidationError: 1 validation error for M
t
  ... [type=utc_timestamp_noncanonical_spelling, input_value=datetime.datetime(2026, 1, 1, 0, 5,
  tzinfo=datetime.timezone.utc), input_type=datetime]
```

The corrected guard distinguishes three cases instead of two: a wire string is format-checked; a
Python `datetime` object (the internal-construction path) passes through untouched to the existing
`AfterValidator`; anything else — a JSON number, a bool, or any other type a hostile or careless
producer might send — is rejected outright. That closes the numeric bypass without breaking the
internal-construction path:

```python
# primitives.py
_UTC_CANONICAL_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{6})?Z$")

def _reject_noncanonical_utc_spelling(value: Any) -> Any:
    if isinstance(value, str):
        if not _UTC_CANONICAL_RE.match(value):
            raise PydanticCustomError(
                "utc_timestamp_noncanonical_spelling",
                "UTC timestamp must be spelled exactly as e.g. "
                "2026-01-01T00:00:00Z or 2026-01-01T00:00:00.123456Z",
            )
        return value
    if isinstance(value, datetime):
        return value
    raise PydanticCustomError(
        "utc_timestamp_noncanonical_spelling",
        "UTC timestamp must be a canonical wire string or a datetime object, "
        f"not {type(value).__name__}",
    )

UtcDateTime = Annotated[
    datetime,
    BeforeValidator(_reject_noncanonical_utc_spelling),
    AfterValidator(_utc_datetime),
    WithJsonSchema(
        {"format": "date-time", "pattern": _UTC_CANONICAL_RE.pattern, "type": "string"}
    ),
]
```

Reproduced against the corrected guard: the numeric wire value from the finding above is now
rejected (`ValidationError`, `utc_timestamp_noncanonical_spelling`); the `test_graph.py:20`
internal-construction pattern still constructs and dumps correctly
(`datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=5)` → `'2026-01-01T00:05:00Z'`); the
canonical wire string and the rejected `+00:00` spelling behave as before. §4's headline claim now
holds as stated: for any document that passes model validation — wire string or internal
`datetime` construction — the corrected guard admits only inputs whose eventual `model_dump`
rendering is the one canonical form.

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

Cross-family adversarial pass: **Kimi K3** (seat `kimi-k3`), findings independently reproduced by a
Claude reviewer before any edit was made, matching the precedent this document follows in form
(`ledger-revision-request-001.md`). Verdict: **shape sound, document not ratifiable as drafted** —
the core diagnosis (§1-§3) and the disqualification of PR #4615's code-only fix (§2.4) were not in
question. Six holes in this document's own downstream reasoning about the cure were found and
closed:

1. **§5's sketch had a numeric-wire-bypass hole that falsified §4's headline claim.** The
   `isinstance(value, str)`-gated `BeforeValidator` let a JSON number through unchecked; the number
   validates and dumps to canonical `Z`, so the dict-path/model-path divergence this proposal exists
   to close survived the cure. Reproduced before and after in §5.1. The fix distinguishes wire
   string / internal `datetime` object / everything-else, rather than a blanket non-`str`
   rejection — the naive blanket version breaks a real, existing internal-construction path
   (`test_graph.py:20`), also reproduced there.
2. **The (a)/(b) "no strong recommendation" was false balance.** (b) has a round-trip hole: a
   `datetime`-constructed document with nonzero microseconds dumps to a string (b)'s own pattern
   rejects. (a) has none. §4 sub-decision 1 now recommends (a) with the round-trip table.
3. **(a)'s cross-language migration cost was claimed zero and is not.** Node's
   `Date.prototype.toISOString()` always emits exactly 3 fractional digits and is rejected by (a)
   for every value; Go's `RFC3339Nano` trims to a different, variable width. §4 now discloses this,
   with a verified Node canonicalization one-liner, and keeps (a)'s single-spelling pattern intact
   rather than widening it (widening would reopen §2.2's defect).
4. **§2.4 promised inline repro commands and then omitted them.** Now inlined, with output quoted
   verbatim — Findings A/B/C are runnable, not merely asserted.
5. **§2.5's sweep never measured the axis §4's cost paragraph prices** (non-canonical
   fractional-second padding), and its per-ref counts had drifted — two more sibling lanes started
   since the original snapshot and a third pre-existing one was omitted. §2.5 now measures both axes
   across all nine currently-live refs, with HEAD SHAs pinned.
6. **The "practical cost is zero" conclusion rested on an unstated premise.** §2.6 now states and
   verifies it — nothing outside `packages/research-os-core` imports `research_os` today except its
   own tests, so the fixture universe genuinely is the whole universe — and names the conclusion's
   expiry condition: the day a consumer is written.

Also raised and addressed: rule 10's compatibility-matrix escape hatch is not obviously invocable —
the only artifact in the repository calling itself a compatibility matrix is an unrelated,
unratified P04 legacy field-mapping deliverable — so the plain-text MAJOR default applies unless
the Conductor rules otherwise. The document now also deploys its own §1 finding (§2/§3 are jointly
inconsistent as frozen) as a counter-consideration for the Conductor to weigh: narrowing §3 is
arguably contradiction-repair rather than a meaning change in the sense rule 10 gates. Neither side
of that tension is picked here — it goes to the Conductor with both readings stated.

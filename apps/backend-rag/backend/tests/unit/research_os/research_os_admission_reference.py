"""D4's admission rules, as an EXECUTABLE PREDICATE — the decision, not the mapping.

WHY ADMISSION IS NOT MAPPING. `02-p04-adapter-mapping.md` answers "which canonical field does
this NAGA column go to". That is a mapping, and a complete mapping still admits nothing: a
legacy row can have a documented destination for every field and still be inadmissible because
the field is EMPTY, or because the value present is the wrong KIND of value (a URL hash where a
body hash belongs). D4 separates the two: mapping coverage, available source information and
admissible records are three different counts, and this module is the third one's decision
procedure.

WHAT IT REFUSES TO DO. It never defaults. A record whose risk class was never assigned is
EXCLUDED with `classification_missing`, not silently stamped `internal` — the packet's exit
threshold is "zero unsupported critical claims eligible for public use", and a default is
exactly how an unsupported claim becomes eligible. It never fabricates: a statement triple that
cannot be derived from the exact quoted span is `statement_not_from_source`, per
`02-p04-adapter-mapping.md:59`.

ZERO ADMITTED IS A VALID OUTCOME. On today's legacy corpus the expected result is zero: NAGA's
`content_hash` is `sha256(url)` (the URL string, not the body), `source_span_hint` is freeform
text with no quote hash, and no NAGA source is an `IntelEvent`. A dry run that admits nothing
and names a reason per record is a PASS. A dry run that admits something by relaxing a rule is
the failure.

WHERE IT LIVES AND WHY. R1 may not write under `services/**`; R2 implements
`services/research_os/naga_admission.py` against this. The reason vocabulary here is the
contract between the two windows: R2 may add reasons, may not rename these.

RULE 5 IS RESOLUTION-AND-BINDING, NOT PRESENCE (cured 2026-09-11, then cured a second time the
same day -- codex round 1, finding 1). The first cure required the `source_event_ref.event_id` to
RESOLVE inside the `source` SourceSnapshot's own `intel_events` mapping, validate against
`intel_event.schema.json`, round-trip `IntelEvent.model_validate`, and carry a RECOMPUTED
`object_hash`. That closed presence but left resolution unbound: a record could point at ANY
unrelated, otherwise-valid `IntelEvent` and be admitted with fictional provenance, because nothing
ever compared the resolved event to the record's OWN document. The second cure adds the missing
comparison -- the resolved event must be the event FOR THIS DOCUMENT: its `source.uri` must equal
the record's `document_id`, and its `identity.content_hash` / `payload_ref.content_hash` must both
equal the record's `document_content_hash` (guaranteed, by rule order, to already be a real body
hash and not the URL hash rule 2 forbids). When `source_event_ref.object_hash` is present it is a
STATED claim about the resolved event's identity, not a hint: a stated hash that disagrees with
the recomputed one is a REJECTION, never a warning, because trusting the caller's own say-so about
the very thing this rule exists to verify would reopen the hole from underneath. A dangling id, an
id resolving to something that is not a valid `IntelEvent`, an `IntelEvent` whose stored hash does
not verify, and an `IntelEvent` that verifies but names a DIFFERENT document are all the same
failure by this rule's lights: none of them is provenance FOR THIS RECORD, and the rule refuses to
guess which of the four it is looking at.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import jsonschema
from pydantic import ValidationError
from research_os.hashing import object_hash as _recomputed_object_hash
from research_os.schemas import SCHEMA_DIRECTORY, SCHEMA_MODELS

_INTEL_EVENT_SCHEMA: dict[str, Any] = json.loads(
    (SCHEMA_DIRECTORY / "intel_event.schema.json").read_text(encoding="utf-8")
)
_INTEL_EVENT_VALIDATOR = jsonschema.Draft202012Validator(_INTEL_EVENT_SCHEMA)

__all__ = [
    "EXCLUSION_REASONS",
    "Admitted",
    "Excluded",
    "AdmissionDecision",
    "admit",
    "counts",
]

#: The ordered reason vocabulary. ORDER IS PART OF THE CONTRACT: a record with two defects
#: reports the FIRST one, so the same record always reports the same reason and a report is
#: diffable across runs. R2 may append; it may not rename or reorder.
EXCLUSION_REASONS: tuple[str, ...] = (
    "statement_not_from_source",
    "content_hash_is_url",
    "source_version_missing",
    "exact_span_missing",
    "intel_event_identity_missing",
    "rights_missing",
    "retention_missing",
    "classification_missing",
    "review_state_missing",
    "family_identity_unresolvable",
)


@dataclass(frozen=True)
class Admitted:
    """The record can become canonical objects, and here is the identity it takes.

    `family_id` comes from the ADMISSION MANIFEST and is NEVER written back into legacy NAGA.
    That supersedes `02-p04-adapter-mapping.md:58`, which recommended a new nullable column on
    `naga_claims`: a write-back would make the legacy table part of the canonical identity
    story, and D4 keeps the manifest the single owner of it.
    """

    legacy_claim_id: str
    family_id: str


@dataclass(frozen=True)
class Excluded:
    """The record does not become canonical, and the reason is NAMED.

    Never `False`, never `None`: a boolean would let a caller report "47 excluded" without
    being able to say why any single one was, and the packet demands the reason per record.
    """

    legacy_claim_id: str
    reason: str


AdmissionDecision = Admitted | Excluded


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


#: Digit runs inside prose, admitting the locale thousands-separators ("," and ".") the seed
#: cohort's Indonesian gazette text and English fixtures both use — "Rp1.234.567" and "1,234,000"
#: both match, and the separators are stripped before comparison so either grouping normalises to
#: the same digit string as the record's own numeric `object_ref_or_value`.
_NUMERIC_SPAN_RE = re.compile(r"\d(?:[\d.,]*\d)?")


def _digit_groups(text: str) -> set[str]:
    """Every digit run in `text`, thousands separators stripped and normalised.

    "Rp1.234.567", "1,234,567" and "1234567" all normalise to the same group -- the same
    figure is spelled with different locale separators across this bundle's fixtures (the
    Indonesian gazette bodies use "." per group, the English ones use ",") and neither spelling
    is the raw `int`.
    """

    return {match.group().replace(",", "").replace(".", "") for match in _NUMERIC_SPAN_RE.finditer(text)}


def _object_value_occurs_in_span(value: Any, quoted_text: str) -> bool:
    """Is `value` actually IN the quoted span, not merely somewhere plausible?

    A caller's `derived_from_span=True` is a promise, not a derivation (B2, codex round 1 finding
    2) — this function is the derivation. When `value`'s own text carries a digit run (true for
    every numeric `object_ref_or_value` AND for a natural-language paraphrase that names its
    figure, e.g. "13 years from date of issuance" or "the 23rd of the seventh following month"), a shared
    normalised digit group between the value and the quoted span IS the derivation -- the
    paraphrase's language need not match the quote's (this bundle mixes English record-level
    paraphrases with Indonesian gazette quotes), only its figure. A value with no digits at all
    falls back to an exact substring check (case folded).
    """

    if isinstance(value, bool):
        return str(value).lower() in quoted_text.lower()
    text = str(value)
    value_digits = _digit_groups(text)
    if value_digits:
        return bool(value_digits & _digit_groups(quoted_text))
    return bool(text) and (text in quoted_text or text.lower() in quoted_text.lower())


def _statement_is_from_source(record: Mapping[str, Any], source: Mapping[str, Any]) -> bool:
    """The triple must be DERIVABLE from the quoted span, not merely asserted to be (B2 cure).

    The presence-only predecessor accepted the self-asserted boolean
    `statement.derived_from_span`: a fabricated triple was admitted whenever ITS QUOTE happened
    to occur somewhere in the body and the caller set the flag to `true` — the flag alone carried
    the rule, per codex round 1 finding 2. The cure derives: the span's quoted text must be
    present in the document body (unchanged), every required part of the triple must be present
    (unchanged), AND the triple's `object_ref_or_value` must actually OCCUR in the quoted span
    itself (`_object_value_occurs_in_span`) — not merely in the wider body, and not merely
    asserted by the flag. The flag remains a required gate (a genuine derivation the caller forgot
    to mark is still not admitted — NAGA has no atomizer, `G-STATEMENT`, still deferred, so for a
    legacy row this is False by construction, which is the honest answer, not a bug), but it can
    no longer carry the rule alone.
    """

    span = record.get("source_span") or {}
    quoted = span.get("quoted_text")
    if not quoted or quoted not in (source.get("body") or ""):
        return False
    statement = record.get("statement") or {}
    if not all(statement.get(part) for part in ("subject_ref", "predicate", "object_ref_or_value")):
        return False
    if statement.get("derived_from_span") is not True:
        return False
    return _object_value_occurs_in_span(statement["object_ref_or_value"], quoted)


def _content_hash_is_url(record: Mapping[str, Any], source: Mapping[str, Any]) -> bool:
    """`02-p04-adapter-mapping.md:83-84`: NAGA hashes the URL STRING, never the fetched body.

    Detected positively rather than by absence: if the stored hash equals `sha256(document_id)`
    it IS the URL hash, whatever it was called. A record that simply has no hash also fails,
    because a missing content hash cannot be a body hash either.
    """

    stored = record.get("document_content_hash")
    document_id = record.get("document_id") or ""
    if not stored:
        return True
    return stored == _sha256(document_id)


def _span_is_exact(record: Mapping[str, Any], source: Mapping[str, Any]) -> bool:
    """`locator` and `quote_hash` are both required, the hash must match the quote, AND the
    locator must RESOLVE to that quote inside this document (B4 cure, codex round 1 finding 3).

    A hint string is not a locator (`02:84`). A `quote_hash` that does not hash the quoted text
    is worse than an absent one — it is a provenance claim that does not hold. The
    presence-only predecessor stopped there, so a genuine quote paired with a FICTIONAL locator
    was admitted: a truthy string was taken for a location. The cure resolves it against
    `source["locators"]` — a mapping this predicate ADDS to the SourceSnapshot's contract, keyed
    by locator, valued by the `{start, end}` character offsets of that location in `body` — and
    requires `body[start:end]` to BE the quoted text. A locator naming nothing, and a locator
    naming somewhere else in the same document, are the same failure.
    """

    span = record.get("source_span") or {}
    locator = span.get("locator")
    quoted = span.get("quoted_text")
    if not locator or not span.get("quote_hash") or not quoted:
        return False
    if span["quote_hash"] != _sha256(quoted):
        return False
    resolved = (source.get("locators") or {}).get(locator)
    if not isinstance(resolved, Mapping):
        return False
    start, end = resolved.get("start"), resolved.get("end")
    if type(start) is not int or type(end) is not int:
        return False
    body = source.get("body") or ""
    return 0 <= start < end <= len(body) and body[start:end] == quoted


def _intel_event_identity_resolves(record: Mapping[str, Any], source: Mapping[str, Any]) -> bool:
    """`intel_event_identity_missing` -- the id must RESOLVE and BIND, not merely be present.

    `source` is a SourceSnapshot carrying an `intel_events` mapping keyed by `event_id` (a
    field this predicate ADDS to the snapshot's contract -- the presence-only predecessor never
    looked at `source` for this rule at all). Gates, ALL of which must hold:

    1. `record["source_event_ref"]["event_id"]` is present.
    2. It resolves to an entry in `source["intel_events"]` -- a dangling id fails here.
    3. The resolved entry validates against `intel_event.schema.json` AND round-trips
       `IntelEvent.model_validate` -- an id resolving to a malformed or wrong-shaped object
       fails here, not silently through to admission.
    4. Its `object_hash` equals the RECOMPUTED `research_os.hashing.object_hash` of the object
       itself -- a stored hash is a claim, not a fact, and this predicate never trusts a claim
       about its own integrity.
    5. If `source_event_ref.object_hash` is STATED, it must equal the recomputed hash too -- a
       stated hash that disagrees with the resolved event is a REJECTION, never a warning
       (codex round 1 finding 1's own framing: a caller's say-so is not provenance).
    6. BINDING (codex round 1 finding 1, the second cure of this rule the same day): the
       resolved event must be the event FOR *THIS* DOCUMENT, not merely any valid event.
       `node.source.uri` must equal `record.document_id`, and `node.identity.content_hash` /
       `node.payload_ref.content_hash` must both equal `record.document_content_hash`. By rule
       order `document_content_hash` has already survived rule 2 (`content_hash_is_url`) here,
       so it is guaranteed to be a real body hash and not the URL hash -- the comparison is
       against a body hash, never against the thing rule 2 forbids. Without this gate a record
       could borrow ANY unrelated canonical `IntelEvent` and be admitted with fictional
       provenance -- resolution alone proves the event is real, not that it is THIS record's.
    """

    event_ref = record.get("source_event_ref") or {}
    event_id = event_ref.get("event_id")
    if not event_id:
        return False

    intel_events = source.get("intel_events") or {}
    node = intel_events.get(event_id)
    if not isinstance(node, Mapping):
        return False
    if "contract_version" not in node or "object_hash" not in node:
        return False

    node_dict = dict(node)
    if next(_INTEL_EVENT_VALIDATOR.iter_errors(node_dict), None) is not None:
        return False

    try:
        SCHEMA_MODELS["intel_event"].model_validate(node_dict)
    except ValidationError:
        return False

    recomputed = _recomputed_object_hash(node_dict)
    if node_dict["object_hash"] != recomputed:
        return False

    stated_hash = event_ref.get("object_hash")
    if stated_hash is not None and stated_hash != recomputed:
        return False

    document_id = record.get("document_id")
    document_hash = record.get("document_content_hash")
    event_uri = (node_dict.get("source") or {}).get("uri")
    event_identity_hash = (node_dict.get("identity") or {}).get("content_hash")
    event_payload_hash = (node_dict.get("payload_ref") or {}).get("content_hash")

    if document_id is None or event_uri != document_id:
        return False
    if not document_hash:
        return False
    if event_identity_hash != document_hash or event_payload_hash != document_hash:
        return False

    return True


def _source_version_resolves(record: Mapping[str, Any], source: Mapping[str, Any]) -> bool:
    """`source_version_missing` -- the version must RESOLVE, not merely be non-empty (B3 cure).

    The presence-only predecessor accepted any truthy `document_version_id` string, contrary to
    `R1-build-spec.md §3` rule 3's own text: "no `document_version_id` for this `(document_id,
    body hash)`". The cure resolves it against `source["document_versions"]` -- a mapping this
    predicate ADDS to the SourceSnapshot's contract, keyed by `document_version_id`, valued by
    the body hash THAT version was registered for. An invented version id that resolves to
    nothing, or one that resolves to a DIFFERENT body hash than this record's own
    `document_content_hash`, is the same failure: neither is the version for this document and
    this body.
    """

    version_id = record.get("document_version_id")
    if not version_id:
        return False
    document_hash = record.get("document_content_hash")
    if not document_hash:
        return False
    versions = source.get("document_versions") or {}
    registered_hash = versions.get(version_id)
    return registered_hash is not None and registered_hash == document_hash


_RULES: tuple[tuple[str, Callable[[Mapping[str, Any], Mapping[str, Any]], bool]], ...] = (
    ("statement_not_from_source", lambda r, s: _statement_is_from_source(r, s)),
    ("content_hash_is_url", lambda r, s: not _content_hash_is_url(r, s)),
    ("source_version_missing", lambda r, s: _source_version_resolves(r, s)),
    ("exact_span_missing", lambda r, s: _span_is_exact(r, s)),
    ("intel_event_identity_missing", lambda r, s: _intel_event_identity_resolves(r, s)),
    ("rights_missing", lambda r, s: bool((r.get("classification") or {}).get("rights"))),
    ("retention_missing", lambda r, s: bool((r.get("retention") or {}).get("retention_class"))),
    (
        "classification_missing",
        lambda r, s: bool((r.get("classification") or {}).get("risk_class"))
        and bool((r.get("classification") or {}).get("sensitivity")),
    ),
    ("review_state_missing", lambda r, s: bool((r.get("review") or {}).get("state"))),
    ("family_identity_unresolvable", lambda r, s: bool(r.get("manifest_family_id"))),
)


def admit(record: Mapping[str, Any], source: Mapping[str, Any]) -> AdmissionDecision:
    """Apply D4's rules in order; the FIRST failure names the reason.

    Deterministic by construction: the same record always yields the same reason, so an
    admission report is diffable run over run and a change in the report means a change in the
    data or in the rules, never in the iteration order of a set.
    """

    legacy_id = str(record.get("id") or record.get("legacy_claim_id") or "")
    for reason, holds in _RULES:
        if not holds(record, source):
            return Excluded(legacy_claim_id=legacy_id, reason=reason)
    return Admitted(legacy_claim_id=legacy_id, family_id=str(record["manifest_family_id"]))


@dataclass(frozen=True)
class AdmissionCounts:
    """The three counts D4 insists are three DIFFERENT measurements.

    They are computed from three different inputs on purpose — the mapping document, the
    records' populated fields, and the decision procedure — so no two of them can be derived
    from each other. A report that collapses them lets "we documented 32 paths" be read as
    "32 records are admissible", which is the confusion D4 exists to prevent.
    """

    documented_mapping_coverage: int
    available_source_information: int
    admissible_records: int


def counts(
    records: Iterable[Mapping[str, Any]],
    sources: Mapping[str, Mapping[str, Any]],
    documented_paths: Sequence[Sequence[str]],
) -> AdmissionCounts:
    """Measure the three, from their three separate sources of truth."""

    records = list(records)
    available = 0
    for record in records:
        source = sources.get(str(record.get("document_id") or ""), {})
        if record.get("document_content_hash") or record.get("source_span") or source.get("body"):
            available += 1
    admissible = sum(
        1
        for record in records
        if isinstance(admit(record, sources.get(str(record.get("document_id") or ""), {})), Admitted)
    )
    return AdmissionCounts(
        documented_mapping_coverage=len(documented_paths),
        available_source_information=available,
        admissible_records=admissible,
    )

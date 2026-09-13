"""D4's admission rules, in production — a DECISION over the legacy `naga_claims` shape.

WHAT THIS MODULE DOES. `admit(legacy_row, *, source_snapshot)` decides whether one legacy NAGA
row can become canonical objects. It is a re-derivation of R1's committed executable
specification, `research_os_admission_reference.py`
(`apps/backend-rag/backend/tests/unit/research_os/`), to the SAME ordered reason vocabulary and
the SAME rules — production code may not import a test-tree module, so the rules are
re-implemented here and measured for agreement in `test_naga_admission.py`, which parametrizes
both this module and R1's reference over the same fixtures (including R1's committed Z2 seed
cohort) and asserts identical outcomes.

WHY ADMISSION IS A DECISION, NOT A MAPPING (R2-build-spec.md §0 D4, §5). A legacy row can have a
documented destination for every field (`02-p04-adapter-mapping.md`) and still be inadmissible,
because a field is EMPTY, or because the value present is the wrong KIND (a URL hash where a
body hash belongs). Three counts — documented mapping coverage, available source information,
admissible records — are three DIFFERENT measurements computed from three different inputs, and
`three_way_counts` proves they can diverge on a mixed cohort (`R2-build-spec.md §5`).

PRESENCE IS NOT RESOLUTION, AND RESOLUTION IS NOT BINDING (R2-build-spec.md §5, the family R1's
adversarial round found three times):

- a `document_version_id` that is merely non-empty is not "the version FOR this document";
- a `source_event_ref.event_id` resolving to SOME valid `IntelEvent` is not provenance unless
  that event is bound to THIS record's own document (`source.uri == document_id`,
  `identity.content_hash`/`payload_ref.content_hash == document_content_hash`);
- `statement.derived_from_span: true` is a caller's PROMISE, not a derivation — the quoted span
  must actually contain the claimed value at the offsets the statement names;
- a `locator` that is never resolved against the document body is not an exact span.

NOTHING IS DEFAULTED SILENTLY. A missing classification is `classification_missing`, never a
silent `internal`. ON TODAY'S LEGACY CORPUS THE EXPECTED RESULT IS ZERO ADMITTED — NAGA's
`content_hash` is `sha256(url)`, `source_span_hint` is freeform text with no quote hash, and no
NAGA source is an `IntelEvent`. A dry run that admits nothing, naming a reason per record, is a
PASS; a dry run that admits something by relaxing a rule is the failure this module exists to
prevent.
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
from research_os.hashing import object_hash as _recompute_object_hash
from research_os.schemas import SCHEMA_DIRECTORY, SCHEMA_MODELS

from backend.services.research_os import _core_path  # noqa: F401  (sys.path bootstrap)

__all__ = [
    "EXCLUSION_REASONS",
    "AdmissionDecision",
    "AdmissionSummary",
    "Admitted",
    "Excluded",
    "ThreeWayCounts",
    "admit",
    "summarize",
    "three_way_counts",
]

_INTEL_EVENT_SCHEMA: dict[str, Any] = json.loads(
    (SCHEMA_DIRECTORY / "intel_event.schema.json").read_text(encoding="utf-8")
)
_INTEL_EVENT_VALIDATOR = jsonschema.Draft202012Validator(_INTEL_EVENT_SCHEMA)

#: The ordered reason vocabulary, IDENTICAL to R1's committed
#: `research_os_admission_reference.EXCLUSION_REASONS` — ORDER IS PART OF THE CONTRACT: a
#: record with two defects reports the FIRST. R2 may append; it may not rename or reorder
#: (R2-build-spec.md §1.1). `family_identity_unresolvable` is R1's own round-2 addition
#: (rule 10, an unresolved `manifest_family_id`), carried here unchanged.
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

    `family_id` comes from the admission MANIFEST (the legacy row's own `manifest_family_id`)
    and is NEVER written back into legacy NAGA — the manifest stays the single owner of that
    identity (R2-build-spec.md §5, superseding `02-p04-adapter-mapping.md:58`'s suggestion of a
    write-back column).
    """

    legacy_claim_id: str
    family_id: str


@dataclass(frozen=True)
class Excluded:
    """The record does not become canonical, and the reason is NAMED — never a bare `False`."""

    legacy_claim_id: str
    reason: str


AdmissionDecision = Admitted | Excluded


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


#: ONE number token, with at most one consistent grouping separator: "1.234.567", "4,321", "13".
_NUMBER_TOKEN_RE = re.compile(r"\d{1,3}(?:([.,])\d{3}(?:\1\d{3})*)?|\d+")
_SEPARATORS = ".,"


def _is_delimited(text: str, start: int, end: int, *, numeric: bool) -> bool:
    """`text[start:end]` is a whole token: it does not continue a number, or a word, on either side."""

    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    if not numeric:
        return not (before.isalnum() or after.isalnum())
    if before.isdigit() or after.isdigit():
        return False
    if before != "" and before in _SEPARATORS and start >= 2 and text[start - 2].isdigit():
        return False
    return not (
        after != "" and after in _SEPARATORS and end + 1 < len(text) and text[end + 1].isdigit()
    )


def _value_is_anchored_in_span(statement: Mapping[str, Any], quoted_text: str) -> bool:
    """The claimed value IS a whole, delimited token of the quoted span, at the offsets it names.

    Overlap is not derivation: the statement must carry `value_span = {start, end}` offsets into
    `quoted_text`, and that exact slice must be a delimited token EQUAL to the value — a number
    token whose separator-stripped digits equal an `int` value, or the identical characters for
    a string value. Any other value type is not mechanically bindable and is not admitted.
    """

    value = statement.get("object_ref_or_value")
    anchor = statement.get("value_span")
    if not isinstance(anchor, Mapping):
        return False
    start, end = anchor.get("start"), anchor.get("end")
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(quoted_text):
        return False
    piece = quoted_text[start:end]
    if type(value) is int:
        return (
            _NUMBER_TOKEN_RE.fullmatch(piece) is not None
            and piece.replace(",", "").replace(".", "") == str(value)
            and _is_delimited(quoted_text, start, end, numeric=True)
        )
    if isinstance(value, str) and value:
        return piece == value and _is_delimited(quoted_text, start, end, numeric=False)
    return False


def _statement_is_from_source(record: Mapping[str, Any], source: Mapping[str, Any]) -> bool:
    """The triple must be DERIVABLE from the quoted span, not merely asserted to be.

    The span's quoted text must be present in the document body, every required part of the
    triple must be present, `statement.derived_from_span` must be `True` (a legacy row has none
    — NAGA has no atomizer — which is the honest answer, not a bug), AND the triple's
    `object_ref_or_value` must BE the token of the quoted span `statement.value_span` names.
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
    return _value_is_anchored_in_span(statement, quoted)


def _content_hash_is_url(record: Mapping[str, Any]) -> bool:
    """NAGA hashes the URL STRING, never the fetched body.

    Detected positively: if the stored hash equals `sha256(document_id)` it IS the URL hash,
    whatever it was called. A record with no hash also fails, because a missing content hash
    cannot be a body hash either.
    """

    stored = record.get("document_content_hash")
    document_id = record.get("document_id") or ""
    if not stored:
        return True
    return stored == _sha256(document_id)


def _span_is_exact(record: Mapping[str, Any], source: Mapping[str, Any]) -> bool:
    """`locator` and `quote_hash` are both required, the hash must match the quote, AND the
    locator must RESOLVE to that quote inside this document.

    A hint string is not a locator. Resolved against `source["locators"]` — keyed by locator,
    valued by the `{start, end}` character offsets of that location in `body`. A locator naming
    nothing, and a locator naming somewhere else in the same document, are the same failure.
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
    """The id must RESOLVE and BIND to THIS record's own document, not merely be present.

    Gates, ALL of which must hold: `source_event_ref.event_id` is present; it resolves to an
    entry in `source["intel_events"]`; that entry validates against `intel_event.schema.json`
    AND round-trips `IntelEvent.model_validate`; its `object_hash` equals the RECOMPUTED
    `research_os.hashing.object_hash` of the object itself (a stored hash is a claim, never a
    fact); if `source_event_ref.object_hash` is STATED it must equal the recomputed hash too — a
    disagreement is a REJECTION, never a warning; and the resolved event's `source.uri` must
    equal `record.document_id`, with `identity.content_hash`/`payload_ref.content_hash` both
    equal to `record.document_content_hash` (already survived rule 2 by this point, so it is
    guaranteed to be a real body hash and not the URL hash rule 2 forbids).
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

    recomputed = _recompute_object_hash(node_dict)
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
    """The version must RESOLVE to THIS `(document_id, body hash)` pair, not merely be non-empty.

    Resolved against `source["document_versions"]` — keyed by `document_version_id`, valued by
    the `{document_id, content_hash}` that version was registered for. An invented version id,
    one registered for a DIFFERENT body hash, and one registered for a DIFFERENT document with
    the same body are the same failure: none is the version for this document and this body.
    """

    version_id = record.get("document_version_id")
    if not version_id:
        return False
    document_hash = record.get("document_content_hash")
    if not document_hash:
        return False
    versions = source.get("document_versions") or {}
    registered = versions.get(version_id)
    return (
        isinstance(registered, Mapping)
        and registered.get("document_id") == record.get("document_id")
        and registered.get("content_hash") == document_hash
    )


_RULES: tuple[tuple[str, Callable[[Mapping[str, Any], Mapping[str, Any]], bool]], ...] = (
    ("statement_not_from_source", lambda r, s: _statement_is_from_source(r, s)),
    ("content_hash_is_url", lambda r, s: not _content_hash_is_url(r)),
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


def admit(
    legacy_row: Mapping[str, Any], *, source_snapshot: Mapping[str, Any]
) -> AdmissionDecision:
    """Apply D4's rules in order over one legacy `naga_claims`-shaped row; the FIRST failure wins.

    `source_snapshot` is the `SourceSnapshot` for `legacy_row["document_id"]`: `body`,
    `intel_events`, `document_versions`, `locators` — the same shape
    `research_os_admission_reference.admit`'s `source` parameter takes. Deterministic by
    construction: the same `(legacy_row, source_snapshot)` pair always yields the same reason,
    so an admission report is diffable run over run.
    """

    legacy_id = str(legacy_row.get("id") or legacy_row.get("legacy_claim_id") or "")
    for reason, holds in _RULES:
        if not holds(legacy_row, source_snapshot):
            return Excluded(legacy_claim_id=legacy_id, reason=reason)
    return Admitted(legacy_claim_id=legacy_id, family_id=str(legacy_row["manifest_family_id"]))


@dataclass(frozen=True)
class AdmissionSummary:
    """A decision-only tally: how many admitted, and how many excluded per reason.

    The pure function the backfill lane's `--dry-run`/`--apply` report calls to turn a batch of
    `admit()` decisions into the per-kind counts D4 wants printed (`eligible / excluded /
    rejected`, by name) — computed from `decisions` alone, unlike `three_way_counts`, which
    needs the raw records and the mapping document too.
    """

    admitted: int
    excluded_by_reason: Mapping[str, int]

    @property
    def excluded(self) -> int:
        return sum(self.excluded_by_reason.values())


def summarize(decisions: Iterable[AdmissionDecision]) -> AdmissionSummary:
    """Tally a batch of `admit()` outcomes. Zero admitted, all-excluded is a VALID summary."""

    admitted = 0
    excluded_by_reason: dict[str, int] = {}
    for decision in decisions:
        if isinstance(decision, Admitted):
            admitted += 1
        else:
            excluded_by_reason[decision.reason] = excluded_by_reason.get(decision.reason, 0) + 1
    return AdmissionSummary(admitted=admitted, excluded_by_reason=excluded_by_reason)


@dataclass(frozen=True)
class ThreeWayCounts:
    """The three counts D4 insists are three DIFFERENT measurements, computed from three
    different inputs so no two can be derived from each other."""

    documented_mapping_coverage: int
    available_source_information: int
    admissible_records: int


def three_way_counts(
    records: Iterable[Mapping[str, Any]],
    sources: Mapping[str, Mapping[str, Any]],
    documented_paths: Sequence[Sequence[str]],
) -> ThreeWayCounts:
    """Measure the three counts from their three separate sources of truth.

    Documented mapping coverage counts paths in a document (`documented_paths`, e.g. from
    `02-p04-adapter-mapping.md`). Available source information counts records that carry ANY
    source material at all — a hash, a span, or a source body — without deciding admissibility.
    Admissible records counts `admit()` decisions. A report that collapses any two of these lets
    "we documented N paths" be read as "N records are admissible", which is the confusion D4
    exists to prevent.
    """

    records = list(records)
    available = 0
    for record in records:
        source = sources.get(str(record.get("document_id") or ""), {})
        if record.get("document_content_hash") or record.get("source_span") or source.get("body"):
            available += 1
    admissible = sum(
        1
        for record in records
        if isinstance(
            admit(record, source_snapshot=sources.get(str(record.get("document_id") or ""), {})),
            Admitted,
        )
    )
    return ThreeWayCounts(
        documented_mapping_coverage=len(documented_paths),
        available_source_information=available,
        admissible_records=admissible,
    )

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
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

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


def _statement_is_from_source(record: Mapping[str, Any], source: Mapping[str, Any]) -> bool:
    """The triple must be derivable from the quoted span, not from the claim's prose.

    Modelled here as: the span's quoted text must be present in the document body, AND the
    triple must be marked as having been derived from that span by a human or rule pass. NAGA
    has no atomizer (`G-STATEMENT`, still deferred), so for a legacy row this is False by
    construction — which is the honest answer, not a bug in this predicate.
    """

    span = record.get("source_span") or {}
    quoted = span.get("quoted_text")
    if not quoted or quoted not in (source.get("body") or ""):
        return False
    statement = record.get("statement") or {}
    if not all(statement.get(part) for part in ("subject_ref", "predicate", "object_ref_or_value")):
        return False
    return statement.get("derived_from_span") is True


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


def _span_is_exact(record: Mapping[str, Any]) -> bool:
    """`locator` and `quote_hash` are both required, and the hash must match the quote.

    A hint string is not a locator (`02:84`). A `quote_hash` that does not hash the quoted text
    is worse than an absent one — it is a provenance claim that does not hold.
    """

    span = record.get("source_span") or {}
    if not span.get("locator") or not span.get("quote_hash"):
        return False
    quoted = span.get("quoted_text")
    return bool(quoted) and span["quote_hash"] == _sha256(quoted)


_RULES: tuple[tuple[str, Callable[[Mapping[str, Any], Mapping[str, Any]], bool]], ...] = (
    ("statement_not_from_source", lambda r, s: _statement_is_from_source(r, s)),
    ("content_hash_is_url", lambda r, s: not _content_hash_is_url(r, s)),
    ("source_version_missing", lambda r, s: bool(r.get("document_version_id"))),
    ("exact_span_missing", lambda r, s: _span_is_exact(r)),
    ("intel_event_identity_missing", lambda r, s: bool((r.get("source_event_ref") or {}).get("event_id"))),
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

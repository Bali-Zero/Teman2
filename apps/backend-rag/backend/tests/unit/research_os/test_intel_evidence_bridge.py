"""`intel_evidence_bridge.bridge` -- the `intel_items` shape mapped into `admit()`'s input.

WHAT THIS FILE PINS. `bridge()` never decides admissibility itself -- it only builds
`(record, source_snapshot)`. Every test that claims a bridged item ends up `Admitted` or
`Excluded` therefore calls `naga_admission.admit()` itself on the bridge's OWN output, the same
way a real caller (this module's `--dry-run`, or a future production caller) would. A test that
asserted an outcome without running `admit()` would be testing this module's opinion of D4's
rules, not D4's rules.

TWO GUILT CONTROLS, both mutating what `bridge()` actually returns rather than hand-building a
record that merely resembles it:

1. `test_a_citation_absent_from_its_own_excerpt_is_excluded_by_name` -- a citation that is not a
   literal, delimited token of its own `verbatim_excerpt` must fail `admit()`'s real check
   (`statement_not_from_source`). If this passed, `bridge()` would be anchoring `value_span` at
   an offset that happens to satisfy `_value_is_anchored_in_span` regardless of the actual text,
   which would make the one rule this module's docstring calls "the real signal on real data"
   vacuous.
2. `test_a_bridge_that_confused_content_hash_with_the_url_is_caught` -- if a future edit to
   `bridge()` swapped `document_content_hash` for `sha256(canonical_url)` (the exact defect D4's
   rule 2 exists to catch on the legacy `naga_claims` shape), `admit()` must refuse it by name
   (`content_hash_is_url`), not silently admit a record whose "document" hash is really a URL
   hash.

Both controls are proven RED first (the mutation applied, decision asserted BROKEN) is not
repeated here as a separate xfail step -- instead each test asserts the EXCLUDED outcome directly
against the mutated input, which only passes if `admit()`'s own rule fires; a `bridge()` that
stopped anchoring correctly, or a test that stopped mutating, both show up as a failure here, not
a silent pass. The session's report captures the actual red/green transcript for the record.
"""

from __future__ import annotations

import hashlib
import json

from backend.services.research_os.intel_evidence_bridge import Mapped, Rejected, bridge
from backend.services.research_os.naga_admission import Admitted, Excluded, admit

_EXCERPT = (
    "Sesuai dengan PMK 12/2026, tarif baru mulai berlaku sejak tanggal 1 Maret 2026 untuk "
    "seluruh wajib pajak terdaftar."
)
_CITATION = "PMK 12/2026"
_URL = "https://example.invalid/regulatory/pmk-12-2026"
_PUBLISHED_AT = "2026-03-01T00:00:00Z"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _intel_item(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "id": "11111111-1111-4111-8111-111111111111",
        "canonical_url": _URL,
        "published_at": _PUBLISHED_AT,
        "raw_payload": {"verbatim_excerpt": _EXCERPT, "citation": _CITATION},
    }
    item.update(overrides)
    return item


def test_a_fully_sourced_item_is_admitted() -> None:
    result = bridge(_intel_item())
    assert isinstance(result, Mapped)
    decision = admit(result.record, source_snapshot=result.source_snapshot)
    assert isinstance(decision, Admitted), decision


def test_an_item_without_a_verbatim_excerpt_is_rejected_by_name() -> None:
    item = _intel_item(raw_payload={"citation": _CITATION})
    result = bridge(item)
    assert isinstance(result, Rejected)
    assert result.reason == "verbatim_excerpt_missing"


def test_an_item_without_a_citation_is_rejected_by_name() -> None:
    item = _intel_item(raw_payload={"verbatim_excerpt": _EXCERPT})
    result = bridge(item)
    assert isinstance(result, Rejected)
    assert result.reason == "citation_missing"


def test_an_item_without_a_canonical_url_is_rejected_by_name() -> None:
    item = _intel_item(canonical_url=None)
    result = bridge(item)
    assert isinstance(result, Rejected)
    assert result.reason == "canonical_url_missing"


def test_an_item_without_a_published_at_is_rejected_by_name() -> None:
    item = _intel_item(published_at=None)
    result = bridge(item)
    assert isinstance(result, Rejected)
    assert result.reason == "published_at_missing"


def test_raw_payload_as_a_json_string_is_accepted_the_same_as_a_dict() -> None:
    """A bare `asyncpg` connection with no jsonb codec registered hands back `raw_payload` as
    text, not a parsed object -- the `--dry-run` CLI's own connection is exactly that case."""

    item = _intel_item(raw_payload=json.dumps({"verbatim_excerpt": _EXCERPT, "citation": _CITATION}))
    result = bridge(item)
    assert isinstance(result, Mapped)
    decision = admit(result.record, source_snapshot=result.source_snapshot)
    assert isinstance(decision, Admitted), decision


def test_a_citation_absent_from_its_own_excerpt_is_excluded_by_name() -> None:
    """Guilt control 1 (see module docstring). A `citation` that is not literally present in
    its own `verbatim_excerpt` must never be admitted -- if it were, `bridge()`'s `value_span`
    anchoring would be decorative rather than a real derivation."""

    item = _intel_item(
        raw_payload={
            "verbatim_excerpt": "A completely unrelated sentence about something else entirely.",
            "citation": _CITATION,
        }
    )
    result = bridge(item)
    assert isinstance(result, Mapped), "the bridge itself must still map -- admit() decides"
    decision = admit(result.record, source_snapshot=result.source_snapshot)
    assert isinstance(decision, Excluded), decision
    assert decision.reason == "statement_not_from_source"


def test_a_citation_that_only_partially_overlaps_a_token_is_excluded_by_name() -> None:
    """A citation embedded inside a larger word is not a DELIMITED token -- `_is_delimited`
    is the second half of guilt control 1, exercised on its own."""

    item = _intel_item(
        raw_payload={
            "verbatim_excerpt": "seePMK 12/2026x for details.",
            "citation": _CITATION,
        }
    )
    result = bridge(item)
    assert isinstance(result, Mapped)
    decision = admit(result.record, source_snapshot=result.source_snapshot)
    assert isinstance(decision, Excluded), decision
    assert decision.reason == "statement_not_from_source"


def test_a_bridge_that_confused_content_hash_with_the_url_is_caught() -> None:
    """Guilt control 2 (see module docstring). Mutates the BRIDGE'S OWN OUTPUT to reproduce the
    exact defect D4's rule 2 exists for -- `document_content_hash` set to a hash of the URL
    string rather than of the document body -- and requires `admit()` to refuse it by name."""

    result = bridge(_intel_item())
    assert isinstance(result, Mapped)
    mutated_record = dict(result.record)
    mutated_record["document_content_hash"] = _sha256(str(mutated_record["document_id"]))

    decision = admit(mutated_record, source_snapshot=result.source_snapshot)
    assert isinstance(decision, Excluded), decision
    assert decision.reason == "content_hash_is_url"


def test_the_unmutated_bridge_output_never_trips_either_guilt_control() -> None:
    """Innocence companion to both guilt controls: the bridge's own, unmutated output for a
    genuinely well-sourced item is `Admitted` -- neither control is a false-positive trap that
    would also catch a correct mapping."""

    result = bridge(_intel_item())
    assert isinstance(result, Mapped)
    decision = admit(result.record, source_snapshot=result.source_snapshot)
    assert isinstance(decision, Admitted), decision


def test_mapping_the_same_item_twice_is_byte_identical() -> None:
    """D4 requires `admit()` itself to be deterministic; this bridge must not undermine that by
    minting a fresh id, timestamp or random value on every call. No `datetime.now()`, no
    `uuid.uuid4()` anywhere in `bridge()` -- only `uuid.uuid5` over the item's own fields."""

    item = _intel_item()
    first = bridge(item)
    second = bridge(dict(item))  # a fresh dict, same content -- not the same object
    assert isinstance(first, Mapped) and isinstance(second, Mapped)

    canon = lambda obj: json.dumps(obj, sort_keys=True, default=str)  # noqa: E731
    assert canon(first.record) == canon(second.record)
    assert canon(first.source_snapshot) == canon(second.source_snapshot)


def test_a_postgres_text_timestamp_and_its_datetime_equivalent_are_byte_identical() -> None:
    """SCAR (found in team-lead review): `_to_rfc3339`'s `str` branch used to check only for a
    trailing `Z`/`+00:00` and otherwise CONCATENATE `Z` onto whatever it was given. Postgres
    renders a `timestamptz` column read back as text as `2026-09-17 10:30:00+00` -- a space
    instead of `T`, and a two-digit `+00` offset -- which matched neither suffix and produced
    the malformed `'2026-09-17 10:30:00+00Z'` (double offset, wrong separator) in silence. The
    same instant passed as a `datetime.datetime` (what a caller with a jsonb-aware pool gets)
    took the other branch and produced a well-formed string, so the SAME data, from the SAME
    database, produced two DIFFERENT `admit()` verdicts depending only on which asyncpg codec
    happened to be in effect -- the opposite of the determinism D4 requires and this function's
    own docstring promises. `bridge()` must produce the same record from either input form."""

    from datetime import datetime, timezone

    as_datetime = datetime(2026, 9, 17, 10, 30, 0, tzinfo=timezone.utc)
    as_postgres_text = "2026-09-17 10:30:00+00"  # exactly how `::text` renders a timestamptz

    item_datetime = _intel_item(published_at=as_datetime)
    item_text = _intel_item(published_at=as_postgres_text)

    result_datetime = bridge(item_datetime)
    result_text = bridge(item_text)
    assert isinstance(result_datetime, Mapped), result_datetime
    assert isinstance(result_text, Mapped), result_text

    canon = lambda obj: json.dumps(obj, sort_keys=True, default=str)  # noqa: E731
    assert canon(result_datetime.record) == canon(result_text.record)
    assert canon(result_datetime.source_snapshot) == canon(result_text.source_snapshot)

    # And both must actually be ADMITTED -- the bug's live symptom was intel_event_identity_missing
    # (a malformed `times.observed_at` fails `intel_event.schema.json`'s RFC3339 pattern), not a
    # crash, so a test that only compared the two records without asserting admissibility would
    # miss the part of the defect that made the production dry-run's own tally non-deterministic.
    decision_datetime = admit(result_datetime.record, source_snapshot=result_datetime.source_snapshot)
    decision_text = admit(result_text.record, source_snapshot=result_text.source_snapshot)
    assert isinstance(decision_datetime, Admitted), decision_datetime
    assert isinstance(decision_text, Admitted), decision_text


def test_an_unparsable_published_at_string_is_rejected_by_name_not_mangled() -> None:
    """The cure must REFUSE a string it cannot parse as an instant, never concatenate a `Z`
    onto it and hope -- an invented timestamp is exactly the "defaulted silently" failure this
    whole package refuses elsewhere."""

    item = _intel_item(published_at="not a timestamp at all")
    result = bridge(item)
    assert isinstance(result, Rejected)
    assert result.reason == "published_at_missing"


def test_the_same_instant_maps_identically_as_a_datetime_and_as_postgres_text() -> None:
    """The admission verdict must not depend on how the driver typed `published_at`.

    PostgreSQL renders a `timestamptz` as `2026-03-01 00:00:00+00` -- neither `Z` nor
    `+00:00`. Appending `Z` to that produced a malformed instant, a different `object_hash`,
    and a different verdict for the same row. RED before the parse cure, green after.
    """

    from datetime import datetime, timezone

    as_datetime = _intel_item(published_at=datetime(2026, 3, 1, tzinfo=timezone.utc))
    as_pg_text = _intel_item(published_at="2026-03-01 00:00:00+00")

    from_datetime = bridge(as_datetime)
    from_text = bridge(as_pg_text)

    assert isinstance(from_datetime, Mapped), from_datetime
    assert isinstance(from_text, Mapped), from_text
    assert json.dumps(from_datetime.record, sort_keys=True) == json.dumps(
        from_text.record, sort_keys=True
    )
    assert isinstance(admit(from_text.record, source_snapshot=from_text.source_snapshot), Admitted)


def test_a_published_at_that_is_not_an_instant_is_refused_not_fabricated() -> None:
    """A string that is not a timestamp must be REFUSED by name, never concatenated into one."""

    result = bridge(_intel_item(published_at="pubblicato in primavera"))

    assert isinstance(result, Rejected), result
    assert result.reason == "published_at_missing", result.reason

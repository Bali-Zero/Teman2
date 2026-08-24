"""Freshness tripwire for ``bali_zero_official_prices_2026.json``.

MEASURED DEFECT this test exists to close: the file self-reports
``metadata.last_updated``, but nothing ever checked that value against the
priced content it describes. Four price-changing commits landed after the
last recorded ``last_updated`` and nobody — human or CI — noticed, because
the only test that touched the date (``test_evaluate_endpoint.py``) asserted
it against a synthetic mock catalog, never against this file. A stale
timestamp with no tripwire is worse than no timestamp: it reads as current.

This test is that tripwire. It recomputes the canonical content hash
(``compute_price_content_sha256`` — RFC 8785 JCS over ``services`` only, see
that function's docstring for what is in/out of scope and why) straight from
the file on disk and asserts it matches the digest recorded in
``metadata.content_sha256``. Whoever edits a price without updating the hash
gets a RED test with a message that tells them what to do about it — that
is the whole mechanism: it does not stop a stale date from being written, it
makes a stale date impossible to leave unnoticed.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from backend.services.pricing.pricing_service import compute_price_content_sha256

_PRICING_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "bali_zero_official_prices_2026.json"
)


def _load_raw() -> dict[str, Any]:
    with open(_PRICING_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_pricing_file_exists_at_the_expected_path() -> None:
    # Guard for every other test in this module: an assertion against a file
    # that silently failed to load would be vacuous, not a pass. See
    # MEMORY_VERIFICATION_RULES.md — "the proof can be empty".
    assert _PRICING_PATH.is_file(), f"expected pricing file at {_PRICING_PATH}"


def test_content_sha256_matches_the_live_services_tree() -> None:
    """The load-bearing assertion.

    Recomputes SHA256(JCS(services)) from the file's OWN ``services`` object
    right now, and compares it to the ``content_sha256`` the file itself
    declares. This is what goes RED the moment a price changes without the
    hash being regenerated — proven by the guilt/innocence pair below,
    ``test_a_changed_price_would_flip_the_recorded_hash`` and this test's own
    green run on an untouched file.
    """
    raw = _load_raw()
    metadata = raw.get("metadata", {})
    recorded = metadata.get("content_sha256")
    computed = compute_price_content_sha256(raw["services"])

    assert recorded is not None, (
        "bali_zero_official_prices_2026.json metadata is missing "
        "'content_sha256' — every priced file must carry a hash of its own "
        "services tree so a silent price edit can be caught."
    )
    assert recorded == computed, (
        "bali_zero_official_prices_2026.json: metadata.content_sha256 "
        f"({recorded!r}) does not match the hash recomputed from the "
        f"current 'services' tree ({computed!r}). This means the PRICE "
        "CONTENT of this file changed since the hash was last recorded — "
        "someone edited a price, added/removed a service row, or changed a "
        "tier_range without regenerating the hash. "
        "FIX: recompute content_sha256 "
        "(backend.services.pricing.pricing_service.compute_price_content_sha256 "
        "over the file's 'services' object) and write the new digest into "
        "metadata.content_sha256 — AND, in the SAME commit, move "
        "metadata.last_updated to today's date. The two fields must move "
        "together: the hash proves the content changed, last_updated says "
        "when. Updating only one of them is exactly the defect this test "
        "exists to catch."
    )


def test_a_changed_price_would_flip_the_recorded_hash() -> None:
    """Guilt proof, permanently in the suite (not just a one-off manual run).

    Mutates an in-memory copy of the real services tree by one price value
    and asserts the recomputed hash differs from what's on disk — i.e. this
    mechanism actually detects a price edit. Never touches the file on disk.
    """
    raw = _load_raw()
    services = raw["services"]
    real_hash = compute_price_content_sha256(services)

    mutated = json.loads(json.dumps(services))  # deep copy
    entry = mutated["single_entry_visas"]["B1 Visa on Arrival (VOA)"]
    assert entry["price"] != "999.999.999 IDR"
    entry["price"] = "999.999.999 IDR"
    mutated_hash = compute_price_content_sha256(mutated)

    assert mutated_hash != real_hash, (
        "changing a single price did not change the computed hash — "
        "compute_price_content_sha256 is not sensitive to price content"
    )


def test_last_updated_is_shape_checked_never_a_frozen_literal() -> None:
    """Assert SHAPE (present, ISO-8601, parses), never a specific date.

    A test that pins the exact value of ``last_updated`` becomes the thing
    it should be guarding against: every time the date legitimately moves
    forward, a literal-equality assertion goes red for a reason that has
    nothing to do with a real defect, and the fix people learn is "update
    the test's literal" — which is precisely the muscle memory that let the
    real staleness here go unnoticed for ~3.5 months.
    """
    raw = _load_raw()
    last_updated = raw["metadata"]["last_updated"]
    assert isinstance(last_updated, str)
    parsed = date.fromisoformat(last_updated)  # raises ValueError if not ISO-8601
    assert parsed.year >= 2026


def test_content_sha256_is_a_lowercase_64_char_hex_digest() -> None:
    raw = _load_raw()
    digest = raw["metadata"]["content_sha256"]
    assert isinstance(digest, str)
    assert len(digest) == 64
    assert digest == digest.lower()
    int(digest, 16)  # raises ValueError if not hex

"""seq-11 pricing increment — gates for the assembled
``rulepack-prod-011.source.json`` (see
``backend.scripts.visa_engine.fold_pack_seq11``).

This module SKIPS cleanly (not error, not red) while
``rulepack-prod-011.source.json`` does not exist on disk — the fold is
deliberately unrunnable until PR #4383 (the E30A/E30B price-list entries)
lands on main, per the fold's own pricing-resolution gate. Once the fold has
run and the file exists, five checks run, each verified against the real
files on disk:

(a) chain gate — seq-11's ``previous_payload_sha256`` equals the
    RECOMPUTED SHA256(JCS(...)) of seq-10's own source payload (never a
    declared-field-vs-declared-field comparison — the house pattern from
    ``test_seq10_pack.py``'s ``TestChainGate``, one generation later in
    the chain).
(b) identity — ``sequence == 11``, ``rule_pack_id`` matches the uuid5
    convention recomputed in-test (never imported from the fold module as
    a trusted constant).
(c) pricing-key parity — exactly 26 products carry a non-null
    ``pricing_key`` and 12 carry ``null``; E30A/E30B's keys deep-equal the
    expected dicts; every one of the 26 non-null keys resolves against
    ``bali_zero_official_prices_2026.json`` to a catalog row with a
    non-empty ``price`` — with a positive control proving the resolver can
    fail (a fabricated item_key must NOT resolve).
(d) byte-invariance — every rule and every source_record is canonically
    identical to seq-10's (this fold declares ZERO edits in either
    collection); every product except E30A/E30B is canonically identical
    to its seq-10 counterpart.
(e) the 5 E30-family products minus E30A/E30B (E30, E30E, E30F) still
    carry ``pricing_key: null`` — the "Data Belum Tersedia" honesty pin
    this fold does not touch.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from backend.services.visa_engine.bundle import canonicalize_json

_REPO_ROOT = Path(__file__).resolve().parents[6]
_PACKS_DIR = (
    _REPO_ROOT
    / "apps"
    / "backend-rag"
    / "backend"
    / "services"
    / "visa_engine"
    / "contracts"
    / "packs"
)
_SEQ10_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-010.source.json"
_SEQ10_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-010.signed.json"
_SEQ11_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-011.source.json"

_PRICES_PATH = (
    _REPO_ROOT / "apps" / "backend-rag" / "backend" / "data" / "bali_zero_official_prices_2026.json"
)

_E30A_PRICING_KEY = {"category": "kitas_permits", "item_key": "E30A Education Visa (1 Year)"}
_E30B_PRICING_KEY = {"category": "kitas_permits", "item_key": "E30B Higher Education (1 Year)"}
_UNTOUCHED_E30_FAMILY = ("E30", "E30E", "E30F")

_EXPECTED_NON_NULL_COUNT = 26
_EXPECTED_NULL_COUNT = 12

pytestmark = pytest.mark.skipif(
    not _SEQ11_SOURCE_PATH.exists(),
    reason=(
        "rulepack-prod-011.source.json does not exist yet — the seq-11 fold "
        "(backend.scripts.visa_engine.fold_pack_seq11) is deliberately blocked "
        "on its own pricing-resolution gate until PR #4383 (E30A/E30B price-list "
        "entries) lands on main. This module SKIPS, not reds, until then."
    ),
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


@pytest.fixture(scope="module")
def seq10_source() -> dict[str, Any]:
    return _read_json(_SEQ10_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq11_source() -> dict[str, Any]:
    return _read_json(_SEQ11_SOURCE_PATH)


@pytest.fixture(scope="module")
def prices() -> dict[str, Any]:
    return _read_json(_PRICES_PATH)


def _resolves(prices_payload: dict[str, Any], pricing_key: dict[str, str]) -> bool:
    """Independent re-implementation of the resolve check (deliberately not
    imported from the fold module — a test that reuses the code it is
    grading is not evidence, per W100)."""

    services = prices_payload.get("services")
    if not isinstance(services, dict):
        return False
    category = services.get(pricing_key["category"])
    if not isinstance(category, dict):
        return False
    entry = category.get(pricing_key["item_key"])
    if not isinstance(entry, dict):
        return False
    price = entry.get("price")
    return isinstance(price, str) and bool(price.strip())


# ---------------------------------------------------------------------------
# (a) chain + identity
# ---------------------------------------------------------------------------


class TestChainGate:
    def test_previous_payload_sha256_chains_to_recomputed_seq10(
        self, seq10_source: dict[str, Any], seq11_source: dict[str, Any]
    ) -> None:
        recomputed = hashlib.sha256(canonicalize_json(seq10_source)).hexdigest()
        seq10_signed = _read_json(_SEQ10_SIGNED_PATH)
        assert recomputed == seq10_signed["payload_sha256"]
        assert seq11_source["previous_payload_sha256"] == recomputed

    def test_sequence_is_11(self, seq11_source: dict[str, Any]) -> None:
        assert seq11_source["sequence"] == 11

    def test_rule_pack_id_matches_uuid5_convention(self, seq11_source: dict[str, Any]) -> None:
        expected = uuid.uuid5(
            uuid.NAMESPACE_URL,
            "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/11",
        )
        assert seq11_source["rule_pack_id"] == str(expected)
        # Formula sanity: the same convention reproduces seq-10's id.
        seq10_expected = uuid.uuid5(
            uuid.NAMESPACE_URL,
            "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/10",
        )
        assert str(seq10_expected) == "d390c8eb-926d-5c37-9bbb-83e4a8601195"


# ---------------------------------------------------------------------------
# (c) pricing-key parity + real-catalog resolution
# ---------------------------------------------------------------------------


class TestPricingKeyParity:
    def test_exactly_26_non_null_12_null(self, seq11_source: dict[str, Any]) -> None:
        non_null = [p for p in seq11_source["products"] if p.get("pricing_key") is not None]
        null = [p for p in seq11_source["products"] if p.get("pricing_key") is None]
        assert len(non_null) == _EXPECTED_NON_NULL_COUNT
        assert len(null) == _EXPECTED_NULL_COUNT
        assert len(non_null) + len(null) == len(seq11_source["products"])

    def test_e30a_pricing_key(self, seq11_source: dict[str, Any]) -> None:
        product = next(p for p in seq11_source["products"] if p["product_code"] == "E30A")
        assert product["pricing_key"] == _E30A_PRICING_KEY

    def test_e30b_pricing_key(self, seq11_source: dict[str, Any]) -> None:
        product = next(p for p in seq11_source["products"] if p["product_code"] == "E30B")
        assert product["pricing_key"] == _E30B_PRICING_KEY

    def test_all_26_non_null_keys_resolve_in_real_catalog(
        self, seq11_source: dict[str, Any], prices: dict[str, Any]
    ) -> None:
        unresolved = []
        checked = 0
        for product in seq11_source["products"]:
            pricing_key = product.get("pricing_key")
            if pricing_key is None:
                continue
            checked += 1
            if not _resolves(prices, pricing_key):
                unresolved.append((product["product_code"], pricing_key))
        assert checked == _EXPECTED_NON_NULL_COUNT
        assert unresolved == []

    def test_positive_control_fake_key_does_not_resolve(self, prices: dict[str, Any]) -> None:
        fake = {
            "category": "kitas_permits",
            "item_key": "E30A Education Visa (1 Year) DOES-NOT-EXIST-FAKE",
        }
        assert _resolves(prices, fake) is False

    def test_positive_control_fake_category_does_not_resolve(self, prices: dict[str, Any]) -> None:
        fake = {"category": "not_a_real_category", "item_key": "E30A Education Visa (1 Year)"}
        assert _resolves(prices, fake) is False


# ---------------------------------------------------------------------------
# (e) untouched E30-family siblings stay null
# ---------------------------------------------------------------------------


class TestUntouchedE30FamilyStaysNull:
    def test_e30_e30e_e30f_pricing_key_still_null(self, seq11_source: dict[str, Any]) -> None:
        by_code = {p["product_code"]: p for p in seq11_source["products"]}
        for code in _UNTOUCHED_E30_FAMILY:
            assert by_code[code]["pricing_key"] is None, f"{code} should still be null"


# ---------------------------------------------------------------------------
# (d) byte-invariance — rules, source_records, and every other product
# ---------------------------------------------------------------------------


class TestByteInvariance:
    def test_rules_canonically_identical_to_seq10(
        self, seq10_source: dict[str, Any], seq11_source: dict[str, Any]
    ) -> None:
        assert len(seq11_source["rules"]) == len(seq10_source["rules"])
        assert _canon(seq11_source["rules"]) == _canon(seq10_source["rules"])

    def test_source_records_canonically_identical_to_seq10(
        self, seq10_source: dict[str, Any], seq11_source: dict[str, Any]
    ) -> None:
        assert len(seq11_source["source_records"]) == len(seq10_source["source_records"])
        assert _canon(seq11_source["source_records"]) == _canon(seq10_source["source_records"])

    def test_product_set_unchanged(
        self, seq10_source: dict[str, Any], seq11_source: dict[str, Any]
    ) -> None:
        seq10_codes = {p["product_code"] for p in seq10_source["products"]}
        seq11_codes = {p["product_code"] for p in seq11_source["products"]}
        assert seq10_codes == seq11_codes
        assert len(seq11_source["products"]) == len(seq10_source["products"])

    def test_every_product_except_e30a_e30b_canonically_identical(
        self, seq10_source: dict[str, Any], seq11_source: dict[str, Any]
    ) -> None:
        seq10_by_code = {p["product_code"]: p for p in seq10_source["products"]}
        drifted = []
        for product in seq11_source["products"]:
            code = product["product_code"]
            if code in ("E30A", "E30B"):
                continue
            if _canon(product) != _canon(seq10_by_code[code]):
                drifted.append(code)
        assert drifted == []

    def test_e30a_e30b_changed_only_pricing_key(
        self, seq10_source: dict[str, Any], seq11_source: dict[str, Any]
    ) -> None:
        seq10_by_code = {p["product_code"]: p for p in seq10_source["products"]}
        seq11_by_code = {p["product_code"]: p for p in seq11_source["products"]}
        for code in ("E30A", "E30B"):
            baseline = dict(seq10_by_code[code])
            candidate = dict(seq11_by_code[code])
            baseline.pop("pricing_key")
            candidate.pop("pricing_key")
            assert _canon(baseline) == _canon(candidate), f"{code} changed beyond pricing_key"

    def test_top_level_keys_other_than_identity_unchanged(
        self, seq10_source: dict[str, Any], seq11_source: dict[str, Any]
    ) -> None:
        identity_keys = {
            "sequence",
            "version",
            "rule_pack_id",
            "previous_payload_sha256",
            "created_at",
            "created_by",
        }
        for key in set(seq10_source) | set(seq11_source):
            if key in identity_keys or key == "products":
                continue
            assert _canon(seq11_source.get(key)) == _canon(seq10_source.get(key)), (
                f"top-level key {key!r} drifted from seq-10"
            )

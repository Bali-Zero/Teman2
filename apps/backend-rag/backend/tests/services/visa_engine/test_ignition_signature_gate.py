"""The mandate's hardest constraint, made a mechanism instead of a sentence.

`docs/plans/2026-08-24-visa-oracle-live/MANDATE.md` §6, verbatim: "ENFORCE
stays OFF until every §5 signature exists — no exception, no partial
ignition." Until 2026-08-25 that lived only in prose: setting
`VISA_ENGINE_EVALUATE_MODE=ENFORCE` would have made the engine the product
authority for real visitors with zero owner signatures collected.

These tests pin BOTH directions. Guilt alone would pass against a gate that
refuses ignition unconditionally (which would make ignition impossible, not
gated); innocence alone would pass against no gate at all.
"""

from __future__ import annotations

import json

import pytest

from backend.services.visa_engine import evaluate_path
from backend.services.visa_engine.enums import EngineMode


@pytest.fixture(autouse=True)
def _clear_manifest_cache():
    """The manifest is deliberately cached (build-time data). Tests that swap
    it must therefore drop the cache on both sides, or one test's manifest
    silently answers another's question."""
    evaluate_path.unsigned_ignition_decisions.cache_clear()
    yield
    evaluate_path.unsigned_ignition_decisions.cache_clear()


def _write_manifest(tmp_path, entries) -> None:
    path = tmp_path / "ignition_signatures.json"
    path.write_text(json.dumps({"signatures": entries}), encoding="utf-8")
    return path


ALL_FIVE_SIGNED = [
    {"id": i, "decision": name, "signed": True}
    for i, name in enumerate(
        [
            "DPIA",
            "Wizard-data retention",
            "Gold-persona rehearsal",
            "Product to tier map",
            "Prices and terms per tier",
        ],
        start=1,
    )
]


class TestIgnitionRequiresEverySignature:
    def test_the_real_committed_manifest_is_not_yet_fully_signed(self) -> None:
        """Anchors the other tests to reality: if this ever fails because the
        real manifest went fully-signed, ignition became authorised and that
        is an owner decision someone must have taken deliberately."""
        missing = evaluate_path.unsigned_ignition_decisions()
        assert missing, (
            "the committed ignition manifest reports every owner signature as "
            "present — if that is genuinely true, ignition is authorised; if it "
            "is not, a consent record was falsified"
        )

    def test_enforce_is_refused_and_degrades_to_shadow_when_signatures_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GUILT: an env flip must not be able to buy authority."""
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "ENFORCE")
        assert evaluate_path.resolve_evaluate_mode() is EngineMode.SHADOW
        # ...and the surface must not claim engine authority either.
        assert evaluate_path.resolve_response_mode() == "CURATED"

    def test_enforce_is_honoured_once_every_signature_exists(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """INNOCENCE: the gate must open for a genuinely signed manifest —
        otherwise it is not a gate, it is a wall, and the owner could never
        ignite."""
        path = _write_manifest(tmp_path, ALL_FIVE_SIGNED)
        monkeypatch.setattr(evaluate_path, "_IGNITION_SIGNATURES_PATH", path)
        evaluate_path.unsigned_ignition_decisions.cache_clear()
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "ENFORCE")
        assert evaluate_path.resolve_evaluate_mode() is EngineMode.ENFORCE
        assert evaluate_path.resolve_response_mode() == "ENGINE"

    def test_one_missing_signature_is_enough_to_refuse(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """"No partial ignition" is the words of the mandate: four out of five
        is refused exactly like zero out of five."""
        entries = [dict(e) for e in ALL_FIVE_SIGNED]
        entries[3]["signed"] = False
        path = _write_manifest(tmp_path, entries)
        monkeypatch.setattr(evaluate_path, "_IGNITION_SIGNATURES_PATH", path)
        evaluate_path.unsigned_ignition_decisions.cache_clear()
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "ENFORCE")
        assert evaluate_path.resolve_evaluate_mode() is EngineMode.SHADOW
        assert evaluate_path.unsigned_ignition_decisions() == ("Product to tier map",)

    def test_missing_manifest_fails_closed_not_open(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """A consent record that cannot be read is not consent. Deleting the
        file must not be a way to ignite."""
        monkeypatch.setattr(
            evaluate_path, "_IGNITION_SIGNATURES_PATH", tmp_path / "does-not-exist.json"
        )
        evaluate_path.unsigned_ignition_decisions.cache_clear()
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "ENFORCE")
        assert evaluate_path.resolve_evaluate_mode() is EngineMode.SHADOW

    def test_malformed_manifest_fails_closed_not_open(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        path = tmp_path / "ignition_signatures.json"
        path.write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(evaluate_path, "_IGNITION_SIGNATURES_PATH", path)
        evaluate_path.unsigned_ignition_decisions.cache_clear()
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "ENFORCE")
        assert evaluate_path.resolve_evaluate_mode() is EngineMode.SHADOW

    def test_empty_signature_list_fails_closed_not_open(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """An empty list would otherwise satisfy "no unsigned entries" —
        vacuous truth is the classic way a gate opens by accident."""
        path = _write_manifest(tmp_path, [])
        monkeypatch.setattr(evaluate_path, "_IGNITION_SIGNATURES_PATH", path)
        evaluate_path.unsigned_ignition_decisions.cache_clear()
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "ENFORCE")
        assert evaluate_path.resolve_evaluate_mode() is EngineMode.SHADOW

    @pytest.mark.parametrize("mode", ["OFF", "SHADOW", "bogus", ""])
    def test_the_gate_touches_nothing_but_enforce(
        self, monkeypatch: pytest.MonkeyPatch, mode: str
    ) -> None:
        """INNOCENCE: unsigned signatures must not change OFF/SHADOW/unknown
        resolution — the guard is scoped to the one lever it is about."""
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, mode)
        expected = EngineMode.SHADOW if mode == "SHADOW" else EngineMode.OFF
        assert evaluate_path.resolve_evaluate_mode() is expected

"""Tests for ``backend.scripts.visa_engine.compile_pack``.

TDD per the PR-A1 task brief: (a) a clean payload compiles ok (exit 0), (b)
a deliberately broken payload reports a defect and exits nonzero, (c) the
committed first signed TEST pack fixture's SOURCE compiles clean (protects
the fixture against future drift), (d) malformed input (not JSON / wrong
shape / missing file) fails cleanly — never a traceback.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.scripts.visa_engine.compile_pack import (
    compile_pack_source,
    load_rule_pack_payload,
    main,
    wrap_as_unsigned_pack,
)
from backend.services.visa_engine.bundle import StaticTrustStore, verify_rule_pack
from backend.services.visa_engine.errors import RulePackVerificationError
from backend.tests.services.visa_engine._builders import minimal_valid_envelope

_FIXTURE_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "services"
    / "visa_engine"
    / "contracts"
    / "packs"
    / "rulepack-test-c1-tourism.source.json"
)


def _write_payload(tmp_path: Path, payload: dict, *, name: str = "pack.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestInnocence:
    def test_minimal_valid_payload_compiles_clean(self, tmp_path: Path) -> None:
        payload = minimal_valid_envelope()["payload"]
        path = _write_payload(tmp_path, payload)

        rc = main([str(path)])

        assert rc == 0

    def test_committed_fixture_source_compiles_clean(self) -> None:
        assert _FIXTURE_SOURCE.exists(), f"fixture missing: {_FIXTURE_SOURCE}"
        _, report = compile_pack_source(_FIXTURE_SOURCE)
        assert report.ok, report.errors
        assert report.errors == ()
        assert report.sequence == 1

    def test_committed_fixture_has_hard_filter_and_eligibility_rules(self) -> None:
        payload = load_rule_pack_payload(_FIXTURE_SOURCE)
        stages = sorted(rule.stage.value for rule in payload.rules)
        assert stages == ["ELIGIBILITY", "HARD_FILTER"]
        assert len(payload.products) == 1
        assert len(payload.source_records) == 1

    def test_wrap_as_unsigned_pack_never_claims_a_real_signature(self) -> None:
        payload = load_rule_pack_payload(_FIXTURE_SOURCE)
        pack = wrap_as_unsigned_pack(payload)

        assert pack.signature == "0" * 86
        assert pack.protected.environment == payload.environment
        assert pack.protected.kid != ""

    def test_wrap_as_unsigned_pack_is_rejected_by_real_bundle_verify_rule_pack(
        self,
    ) -> None:
        """PR-A1 codex correctness review finding #7 (nitpick): the previous
        version of this test only inspected the ``RulePack`` object's own
        fields — it never proved the placeholder is actually untrusted by
        the REAL verifier. Here the wrapped pack is dumped back to a raw
        wire dict and fed straight into ``bundle.verify_rule_pack`` with an
        EMPTY trust store, with ``allow_unsigned=True`` — deliberately the
        most permissive caller configuration possible. It must still be
        rejected: the placeholder ``signature`` is a non-empty 86-char
        string (``"0" * 86``), so it is NOT treated as an actually-unsigned
        envelope (``bundle._has_signature`` only special-cases an absent/
        null/empty ``signature``) — it goes down the real signed-verification
        path and fails there (no key ``compile-pack-unsigned-scaffold`` is
        known to an empty trust store), proving ``compile_pack``'s scaffold
        can never be mistaken for a trusted pack by the actual runtime
        verifier, decoupled entirely from ``bundle.py``'s own
        ``UNSIGNED-DEV`` firebreak convention.
        """

        payload = load_rule_pack_payload(_FIXTURE_SOURCE)
        pack = wrap_as_unsigned_pack(payload)
        raw_envelope = pack.model_dump(mode="json", by_alias=True)

        with pytest.raises(RulePackVerificationError, match="unknown signing key_id"):
            verify_rule_pack(
                raw_envelope,
                trust_store=StaticTrustStore([]),
                observed_at=datetime(2026, 7, 19, tzinfo=timezone.utc),
                allow_unsigned=True,
            )


class TestGuilt:
    def test_deliberately_broken_payload_reports_defect_and_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        payload = minimal_valid_envelope()["payload"]
        # Deliberate REQUIRED_FACTS_MISMATCH: the eligibility rule's `when`
        # references intent.purposes/intent.stay_days but required_facts is
        # emptied out.
        for rule in payload["rules"]:
            if rule["rule_id"] == "el-tourism":
                rule["required_facts"] = []
        path = _write_payload(tmp_path, payload)

        rc = main([str(path)])

        assert rc == 1
        out = capsys.readouterr().out
        assert "REQUIRED_FACTS_MISMATCH" in out

    def test_not_json_fails_cleanly(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = tmp_path / "garbage.json"
        path.write_text("{not valid json", encoding="utf-8")

        rc = main([str(path)])

        assert rc == 1
        assert "not valid JSON" in capsys.readouterr().err

    def test_wrong_shape_fails_cleanly(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = _write_payload(tmp_path, {"this": "is not a RulePackPayload"})

        rc = main([str(path)])

        assert rc == 1
        assert "does not validate" in capsys.readouterr().err

    def test_missing_file_fails_cleanly(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main([str(tmp_path / "does-not-exist.json")])

        assert rc == 1
        assert "could not read" in capsys.readouterr().err

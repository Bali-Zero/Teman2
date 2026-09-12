"""B2.2 — fail-loud / fail-closed for `DOMAIN_ABSTAIN_THRESHOLDS` (RULING I40(d)).

Before this PR, `_parse_domain_threshold_overrides` accepted a malformed
`DOMAIN_ABSTAIN_THRESHOLDS` env var (e.g. a JSON spec like
`{"tax":0.15,"visa":0.15}` instead of `tax:0.15,visa:0.15`) and silently
produced a GARBAGE key (`'{"tax"'` -> 0.15) that entered the live threshold
dict alongside whatever valid entries happened to parse — a
partially-applied, silently-wrong override, with only a `logger.warning`
to notice it by. RULING I40(d): fail-closed applies to configuration too.

`_parse_domain_threshold_overrides` now raises `ValueError` on the first
malformed entry / out-of-range value / unknown domain key / duplicate
domain key, and `_build_domain_thresholds` (the function actually bound to
`_DOMAIN_THRESHOLDS` at module import) catches that, logs at ERROR, and
falls back to the STRICT thresholds (`_strict_fallback_thresholds()` —
every relief lifted to `default`, anything already stricter kept) — never
a partial merge, and never the permissive `DOMAIN_ABSTAIN_THRESHOLDS_DEFAULT`
(RULING I41, kimi-code/k3 R9: falling back to the defaults is not
fail-closed for an abstain gate, since the defaults carry the reliefs).
`_build_domain_thresholds` itself must never raise: it runs at import
time, and an uncaught exception there would stop the whole app from
booting over a bad env var.
"""

from __future__ import annotations

import importlib
import logging

import pytest

from backend.services.rag.agentic import reasoning_utils

_KNOWN_DOMAINS = set(reasoning_utils.DOMAIN_ABSTAIN_THRESHOLDS_DEFAULT)


class TestParseDomainThresholdOverridesRaisesOnBadInput:
    def test_valid_colon_comma_spec_parses_and_applies(self) -> None:
        result = reasoning_utils._parse_domain_threshold_overrides("tax:0.10,kbli:0.20")
        assert result == {"tax": 0.10, "kbli": 0.20}

    def test_empty_spec_is_not_an_error_and_yields_no_overrides(self) -> None:
        assert reasoning_utils._parse_domain_threshold_overrides("") == {}
        assert reasoning_utils._parse_domain_threshold_overrides("   ") == {}

    def test_json_spec_raises_instead_of_producing_a_garbage_key(self) -> None:
        with pytest.raises(ValueError):
            reasoning_utils._parse_domain_threshold_overrides('{"tax":0.15,"visa":0.15}')

    def test_entry_with_no_colon_raises(self) -> None:
        with pytest.raises(ValueError):
            reasoning_utils._parse_domain_threshold_overrides("garbage")

    def test_non_numeric_value_raises(self) -> None:
        with pytest.raises(ValueError):
            reasoning_utils._parse_domain_threshold_overrides("tax:not-a-number")

    def test_unknown_domain_key_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown domain"):
            reasoning_utils._parse_domain_threshold_overrides("notadomain:0.5")

    @pytest.mark.parametrize("bad_value", ("1.5", "-0.1", "nan", "inf"))
    def test_out_of_range_value_raises(self, bad_value: str) -> None:
        with pytest.raises(ValueError, match="out-of-range"):
            reasoning_utils._parse_domain_threshold_overrides(f"tax:{bad_value}")

    def test_boundary_values_zero_and_one_are_accepted(self) -> None:
        result = reasoning_utils._parse_domain_threshold_overrides("tax:0.0,visa:1.0")
        assert result == {"tax": 0.0, "visa": 1.0}

    def test_one_bad_entry_poisons_the_whole_spec_not_just_itself(self) -> None:
        """Fail-closed is ALL-OR-NOTHING: a spec with one good entry and one
        bad entry must not silently keep the good one — the caller
        (`_build_domain_thresholds`) is the one responsible for discarding
        the whole thing, but `_parse_domain_threshold_overrides` must raise
        before returning anything partial in the first place."""
        with pytest.raises(ValueError):
            reasoning_utils._parse_domain_threshold_overrides("tax:0.10,notadomain:0.5")

    def test_duplicate_domain_key_raises(self) -> None:
        # Council round 1 (kimi-code/k3, R10): `tax:0.10,tax:0.20` used to
        # apply silently with last-wins. An ambiguous spec is not a spec.
        with pytest.raises(ValueError, match="duplicate domain"):
            reasoning_utils._parse_domain_threshold_overrides("tax:0.10,tax:0.20")


class TestBuildDomainThresholdsNeverRaisesAndFallsBackInFull:
    def test_valid_override_applies_on_top_of_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # The values MUST differ from the defaults, or the assertion cannot
        # tell an applied override from an ignored one (council round,
        # codex-gpt-5.6-sol, P3). Defaults here are tax 0.10 / kbli 0.20.
        monkeypatch.setenv("DOMAIN_ABSTAIN_THRESHOLDS", "tax:0.13,kbli:0.17")
        result = reasoning_utils._build_domain_thresholds()
        expected = dict(reasoning_utils.DOMAIN_ABSTAIN_THRESHOLDS_DEFAULT)
        expected.update({"tax": 0.13, "kbli": 0.17})
        assert result == expected
        assert result["tax"] != reasoning_utils.DOMAIN_ABSTAIN_THRESHOLDS_DEFAULT["tax"]

    def test_json_spec_applies_nothing_and_logs_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setenv("DOMAIN_ABSTAIN_THRESHOLDS", '{"tax":0.15,"visa":0.15}')
        with caplog.at_level(logging.ERROR, logger=reasoning_utils.logger.name):
            result = reasoning_utils._build_domain_thresholds()

        assert result == reasoning_utils._strict_fallback_thresholds()
        # no garbage key entered the dict
        assert not any(k.startswith("{") for k in result)
        assert set(result) == _KNOWN_DOMAINS
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert error_records, "expected an ERROR log record for the invalid spec"
        assert "DOMAIN_ABSTAIN_THRESHOLDS" in error_records[0].getMessage()

    def test_unknown_domain_key_applies_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DOMAIN_ABSTAIN_THRESHOLDS", "notadomain:0.5")
        result = reasoning_utils._build_domain_thresholds()
        assert result == reasoning_utils._strict_fallback_thresholds()
        assert "notadomain" not in result

    def test_out_of_range_value_applies_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DOMAIN_ABSTAIN_THRESHOLDS", "tax:1.5")
        result = reasoning_utils._build_domain_thresholds()
        assert result == reasoning_utils._strict_fallback_thresholds()

    def test_one_bad_entry_falls_back_in_full_not_just_for_that_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A spec with one VALID entry and one BAD entry must not apply the
        valid one either — fail-closed is all-or-nothing at the spec level,
        not per-entry."""
        # tax:0.13 differs from the default 0.10, so "the valid entry was not
        # applied either" is observable rather than indistinguishable.
        monkeypatch.setenv("DOMAIN_ABSTAIN_THRESHOLDS", "tax:0.13,notadomain:0.5")
        result = reasoning_utils._build_domain_thresholds()
        assert result == reasoning_utils._strict_fallback_thresholds()
        # Fail-STRICT, not fail-to-defaults (council round 1, kimi-code/k3 R9):
        # an untrusted spec must never hand back the RELIEF, which is the most
        # permissive value in the dict.
        assert result["tax"] > reasoning_utils.DOMAIN_ABSTAIN_THRESHOLDS_DEFAULT["tax"]
        assert result["tax"] == reasoning_utils.DOMAIN_ABSTAIN_THRESHOLDS_DEFAULT["default"]

    def test_duplicate_domain_key_falls_back_strict_and_logs_the_duplicate(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("DOMAIN_ABSTAIN_THRESHOLDS", "tax:0.10,tax:0.20")
        with caplog.at_level(logging.ERROR, logger=reasoning_utils.logger.name):
            result = reasoning_utils._build_domain_thresholds()

        assert result == reasoning_utils._strict_fallback_thresholds()
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert error_records, "expected an ERROR log record for the duplicate key"
        message = error_records[0].getMessage()
        assert "tax" in message
        assert "duplicate" in message.lower()

    def test_unset_env_var_yields_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DOMAIN_ABSTAIN_THRESHOLDS", raising=False)
        result = reasoning_utils._build_domain_thresholds()
        assert result == reasoning_utils.DOMAIN_ABSTAIN_THRESHOLDS_DEFAULT


class TestImportingTheModuleWithAMalformedEnvVarDoesNotRaise:
    """The literal claim in both functions' docstrings: a bad
    `DOMAIN_ABSTAIN_THRESHOLDS` must never prevent the module — and by
    extension the app that imports it — from booting. Proven by reloading
    the real module (not just calling its function directly) under the
    malformed env var, then restoring it so no other test in this session
    observes a polluted `_DOMAIN_THRESHOLDS`."""

    def test_reload_under_a_malformed_env_var_does_not_raise(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DOMAIN_ABSTAIN_THRESHOLDS", '{"tax":0.15,"visa":0.15}')
        try:
            reloaded = importlib.reload(reasoning_utils)
        except Exception as exc:  # pragma: no cover - the thing under test
            pytest.fail(f"importing reasoning_utils raised under a malformed env var: {exc!r}")

        assert reloaded._DOMAIN_THRESHOLDS == reloaded._strict_fallback_thresholds()

        # restore real state for every other test in this session — monkeypatch
        # un-sets the env var on teardown, but the module-level
        # `_DOMAIN_THRESHOLDS` computed during THIS reload would otherwise
        # stay poisoned (to defaults, harmlessly, but still not the state a
        # clean import would have produced) for whoever imports this module
        # object next.
        monkeypatch.undo()
        importlib.reload(reasoning_utils)

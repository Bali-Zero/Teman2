"""The sandbox/live switch is two independent flags, not one.

`XenditPaymentProvider.__init__` takes a `secret_key` (its prefix names the
mode Xendit itself will honour) and a `live_enabled` keyword (wired from
`GARUDA_PAYMENTS_LIVE`, `service_initializer.py` §5.7). Going live must be a
deliberate env change on BOTH axes -- a production key alone must not arm a
real charge, and flipping the flag alone must not make a sandbox key claim
to be live. This file is the 2x2 matrix plus the "any other prefix" and
"the key never appears in an error" guarantees; test_xendit_callback_token_guard.py
covers the pre-existing production-key-without-live-flag half.
"""

from __future__ import annotations

import httpx
import pytest

from backend.services.payments.xendit import XenditFeeConfig, XenditPaymentProvider

_FEE = XenditFeeConfig(percentage_bps=350, fixed_idr=6000)
_TOKEN = "a-real-callback-token"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={})))


def _build(*, secret_key: str, live_enabled: bool = False) -> XenditPaymentProvider:
    return XenditPaymentProvider(
        secret_key=secret_key,
        callback_verification_token=_TOKEN,
        public_base_url="https://example.invalid",
        fee_config=_FEE,
        client=_client(),
        live_enabled=live_enabled,
    )


class TestTheFourCellMatrix:
    def test_production_key_with_live_enabled_constructs_in_live_mode(self) -> None:
        provider = _build(secret_key="xnd_production_real", live_enabled=True)
        assert provider.mode == "live"

    def test_development_key_without_live_enabled_constructs_in_sandbox_mode(self) -> None:
        provider = _build(secret_key="xnd_development_fake", live_enabled=False)
        assert provider.mode == "sandbox"

    def test_production_key_without_live_enabled_is_refused(self) -> None:
        """A live key alone must never arm a real charge -- two independent
        switches, per the module docstring."""
        with pytest.raises(ValueError, match="GARUDA_PAYMENTS_LIVE"):
            _build(secret_key="xnd_production_real", live_enabled=False)

    def test_development_key_with_live_enabled_is_refused(self) -> None:
        """The inverse mistake: flipping the flag alone must not make a
        sandbox key claim to be live -- the customer site would believe
        checkout is real and send tourists to an invoice nobody can pay."""
        with pytest.raises(ValueError, match="GARUDA_PAYMENTS_LIVE"):
            _build(secret_key="xnd_development_fake", live_enabled=True)


class TestOtherPrefixesAndTheModeProperty:
    @pytest.mark.parametrize(
        "secret_key",
        ["xnd_test_something", "sk_live_stripe_shaped", "", "xnd_developmentwrong_"],
    )
    @pytest.mark.parametrize("live_enabled", [False, True])
    def test_any_other_prefix_is_refused_regardless_of_the_flag(
        self, secret_key: str, live_enabled: bool
    ) -> None:
        with pytest.raises(ValueError):
            _build(secret_key=secret_key, live_enabled=live_enabled)

    def test_mode_is_read_only(self) -> None:
        provider = _build(secret_key="xnd_development_fake", live_enabled=False)
        with pytest.raises(AttributeError):
            provider.mode = "live"  # type: ignore[misc]


class TestTheErrorNeverCarriesTheKey:
    @pytest.mark.parametrize(
        ("secret_key", "live_enabled"),
        [
            ("xnd_production_super-secret-material", False),
            ("xnd_development_super-secret-material", True),
            ("totally-unrecognised-super-secret-material", False),
        ],
    )
    def test_the_secret_key_value_is_never_in_the_message(
        self, secret_key: str, live_enabled: bool
    ) -> None:
        with pytest.raises(ValueError) as exc:
            _build(secret_key=secret_key, live_enabled=live_enabled)
        assert secret_key not in str(exc.value)
        assert "super-secret-material" not in str(exc.value)

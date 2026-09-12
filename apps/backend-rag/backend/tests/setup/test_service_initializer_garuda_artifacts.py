"""W3A S2b: `initialize_garuda_services` wires the delivered-artifact object
store FAIL-CLOSED — the attribute is absent, never `None`, unless the store
constructed and its bucket was not proven public.

No network anywhere: the real constructor is exercised only on its refusal
branch (env absent), and the good branch is exercised through a stub bound
in the adapter module's namespace, which is where the initializer imports
it from. Decision #43: `require_verified=False` — an unknown privacy verdict
wires and is logged by name; only a PROVEN public bucket refuses.

Two steps, because `initialize_garuda_services` may contain no await
(`test_no_await_separates_the_pool_from_the_garuda_wiring`): construction
there, the probe in `probe_garuda_artifact_bucket`, awaited right after it
by both entry points. `_wire` below runs the pair the way the entry points do.
"""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI

from backend.app.setup.service_initializer import (
    initialize_garuda_services,
    probe_garuda_artifact_bucket,
)
from backend.services.garuda_artifacts import tigris_store
from backend.services.garuda_artifacts.tigris_store import GarudaArtifactsStoreUnavailable

_SENTINEL_VALUE = "AKIA-SENTINEL-VALUE-NEVER-LOGGED"
_ENV = (
    tigris_store.BUCKET_ENV,
    tigris_store.ACCESS_KEY_ID_ENV,
    tigris_store.SECRET_ACCESS_KEY_ENV,
    tigris_store.ENDPOINT_URL_ENV,
)


def _wiring_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if "GARUDA VOA artifact store" in r.getMessage()]


async def _wire(app: FastAPI) -> None:
    await initialize_garuda_services(app, None)  # must not raise
    await probe_garuda_artifact_bucket(app)  # must not raise


class TestArtifactStoreWiring:
    @pytest.mark.asyncio
    async def test_env_absent_leaves_the_attribute_absent_and_names_the_variables(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        for name in _ENV:
            monkeypatch.delenv(name, raising=False)
        caplog.set_level(logging.INFO, logger="zantara.backend")
        app = FastAPI()

        await _wire(app)

        assert not hasattr(app.state, "garuda_artifact_store"), (
            "absent means 503 for a future reader; None would be a value it has to special-case"
        )
        records = _wiring_records(caplog)
        assert len(records) == 1 and records[0].levelno == logging.INFO
        message = records[0].getMessage()
        assert "skipped (fail closed" in message
        for name in _ENV[:3]:
            assert name in message, f"the refusal must name {name}"

    @pytest.mark.asyncio
    async def test_a_present_value_is_never_logged_when_another_is_missing(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv(tigris_store.BUCKET_ENV, "garuda-voa-artifacts")
        monkeypatch.setenv(tigris_store.ACCESS_KEY_ID_ENV, _SENTINEL_VALUE)
        monkeypatch.delenv(tigris_store.SECRET_ACCESS_KEY_ENV, raising=False)
        caplog.set_level(logging.INFO, logger="zantara.backend")
        app = FastAPI()

        await _wire(app)

        assert not hasattr(app.state, "garuda_artifact_store")
        assert _SENTINEL_VALUE not in caplog.text
        assert tigris_store.SECRET_ACCESS_KEY_ENV in caplog.text

    @pytest.mark.asyncio
    async def test_a_proven_public_bucket_refuses_and_stays_absent(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        class _PublicBucketStore:
            async def assert_private(self, *, require_verified: bool = True) -> dict:
                raise GarudaArtifactsStoreUnavailable(
                    "garuda artifacts store: the configured bucket is PUBLIC; refusing"
                )

        monkeypatch.setattr(tigris_store, "TigrisArtifactObjectStore", _PublicBucketStore)
        caplog.set_level(logging.INFO, logger="zantara.backend")
        app = FastAPI()

        await _wire(app)

        assert not hasattr(app.state, "garuda_artifact_store"), (
            "constructed, then UNWIRED by the probe: the attribute must be gone, not None"
        )
        assert not hasattr(app.state, "garuda_artifact_privacy")
        errors = [r for r in _wiring_records(caplog) if r.levelno == logging.ERROR]
        assert len(errors) == 1 and "PUBLIC" in errors[0].getMessage()

    @pytest.mark.asyncio
    async def test_a_probe_that_fails_for_any_other_reason_also_unwires(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        class _UnreachableStore:
            async def assert_private(self, *, require_verified: bool = True) -> dict:
                raise RuntimeError("endpoint unreachable")

        monkeypatch.setattr(tigris_store, "TigrisArtifactObjectStore", _UnreachableStore)
        caplog.set_level(logging.INFO, logger="zantara.backend")
        app = FastAPI()

        await _wire(app)

        assert not hasattr(app.state, "garuda_artifact_store")

    @pytest.mark.asyncio
    async def test_an_unknown_verdict_wires_and_is_logged_by_name(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Decision #43: Tigris may answer neither probe; that is not a refusal."""
        probes: list[bool] = []

        class _UnprobeableStore:
            async def assert_private(self, *, require_verified: bool = True) -> dict:
                probes.append(require_verified)
                return {"public_access_block": None, "policy_status": None}

        monkeypatch.setattr(tigris_store, "TigrisArtifactObjectStore", _UnprobeableStore)
        caplog.set_level(logging.INFO, logger="zantara.backend")
        app = FastAPI()

        await _wire(app)

        assert isinstance(app.state.garuda_artifact_store, _UnprobeableStore)
        assert app.state.garuda_artifact_privacy == {
            "public_access_block": None,
            "policy_status": None,
        }
        assert probes == [False], "the wiring must pass require_verified=False, once"
        message = _wiring_records(caplog)[-1].getMessage()
        assert "bucket private: unverified" in message and "#G" in message

    @pytest.mark.asyncio
    async def test_a_verified_private_bucket_wires_and_says_so(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        class _PrivateStore:
            async def assert_private(self, *, require_verified: bool = True) -> dict:
                return {"public_access_block": True, "policy_status": None}

        monkeypatch.setattr(tigris_store, "TigrisArtifactObjectStore", _PrivateStore)
        caplog.set_level(logging.INFO, logger="zantara.backend")
        app = FastAPI()

        await _wire(app)

        assert isinstance(app.state.garuda_artifact_store, _PrivateStore)
        assert app.state.garuda_artifact_privacy["public_access_block"] is True
        assert "bucket private: verified" in _wiring_records(caplog)[-1].getMessage()

    @pytest.mark.asyncio
    async def test_any_other_failure_is_a_warning_and_stays_absent(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        class _BrokenStore:
            def __init__(self) -> None:
                raise RuntimeError("boto3 exploded")

        monkeypatch.setattr(tigris_store, "TigrisArtifactObjectStore", _BrokenStore)
        caplog.set_level(logging.INFO, logger="zantara.backend")
        app = FastAPI()

        await _wire(app)

        assert not hasattr(app.state, "garuda_artifact_store")
        records = _wiring_records(caplog)
        assert len(records) == 1 and records[0].levelno == logging.WARNING

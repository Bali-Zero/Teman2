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

import ast
import inspect
import logging

import pytest
from fastapi import FastAPI

from backend.app.setup import service_initializer
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
            "constructed, parked, then NOT published by the probe: the attribute must never appear"
        )
        assert not hasattr(app.state, "garuda_artifact_store_pending")
        assert not hasattr(app.state, "garuda_artifact_privacy")
        errors = [r for r in _wiring_records(caplog) if r.levelno == logging.ERROR]
        assert len(errors) == 1 and "PUBLIC" in errors[0].getMessage()

    @pytest.mark.asyncio
    async def test_the_store_is_never_visible_before_the_probe_answers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sol O1 (S2b): the window between construction and probe. The store
        is parked under a PENDING name and `garuda_artifact_store` appears
        only after the verdict -- so an entry point that forgets the probe
        publishes nothing, and a reader during the network await sees
        nothing."""
        seen_during_probe: dict[str, bool] = {}

        class _SlowStore:
            async def assert_private(self, *, require_verified: bool = True) -> dict:
                seen_during_probe["published"] = hasattr(app.state, "garuda_artifact_store")
                return {"public_access_block": None, "policy_status": None}

        monkeypatch.setattr(tigris_store, "TigrisArtifactObjectStore", _SlowStore)
        app = FastAPI()

        await initialize_garuda_services(app, None)
        assert not hasattr(app.state, "garuda_artifact_store"), "published before any probe"
        assert isinstance(app.state.garuda_artifact_store_pending, _SlowStore)

        await probe_garuda_artifact_bucket(app)
        assert seen_during_probe == {"published": False}
        assert isinstance(app.state.garuda_artifact_store, _SlowStore)
        assert not hasattr(app.state, "garuda_artifact_store_pending")

    @pytest.mark.asyncio
    async def test_sdk_exception_messages_are_never_logged(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Sol O1 (S2b): boto3 may echo an endpoint, bucket or key id into an
        exception message; the catch-all handlers log the TYPE, not the text."""

        class _LeakyConstructor:
            def __init__(self) -> None:
                raise RuntimeError(f"endpoint refused key {_SENTINEL_VALUE}")

        class _LeakyProbe:
            async def assert_private(self, *, require_verified: bool = True) -> dict:
                raise RuntimeError(f"HeadBucket failed for {_SENTINEL_VALUE}")

        caplog.set_level(logging.INFO, logger="zantara.backend")
        for stub in (_LeakyConstructor, _LeakyProbe):
            monkeypatch.setattr(tigris_store, "TigrisArtifactObjectStore", stub)
            app = FastAPI()
            await _wire(app)
            assert not hasattr(app.state, "garuda_artifact_store")
        assert _SENTINEL_VALUE not in caplog.text
        assert "RuntimeError" in caplog.text

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
        assert not hasattr(app.state, "garuda_artifact_store_pending")
        records = _wiring_records(caplog)
        assert len(records) == 1 and records[0].levelno == logging.WARNING


class TestBothEntryPointsProbe:
    """Decision #44: the probe is the only publisher of the store, so an entry
    point that forgets to await it ships a process with no artifact store and
    no log saying why. AST guard, same shape as the readiness one: in BOTH
    entry points the `await probe_garuda_artifact_bucket(app)` statement is
    the one right after `await initialize_garuda_services(...)`."""

    @pytest.mark.parametrize("entry", ["initialize_services", "initialize_services_light"])
    def test_both_entry_points_await_the_probe_right_after_the_wiring(self, entry: str) -> None:
        tree = ast.parse(inspect.getsource(service_initializer))
        fn = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == entry)

        def _awaited_name(stmt: ast.stmt) -> str | None:
            """Name of the awaited call, only if its FIRST positional argument is
            the entry point's own `app` (Sol O2: `probe(FastAPI())` must not pass)."""
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Await):
                call = stmt.value.value
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.args
                    and isinstance(call.args[0], ast.Name)
                    and call.args[0].id == "app"
                ):
                    return call.func.id
            return None

        hits = []
        for node in ast.walk(fn):
            body = getattr(node, "body", None)
            if not isinstance(body, list):
                continue
            for a, b in zip(body, body[1:], strict=False):
                if _awaited_name(a) == "initialize_garuda_services":
                    hits.append(_awaited_name(b))
        assert hits == ["probe_garuda_artifact_bucket"], (
            f"{entry}: the statement after `await initialize_garuda_services(...)` must be "
            f"`await probe_garuda_artifact_bucket(app)`; found {hits}"
        )

    @pytest.mark.asyncio
    async def test_rewiring_starts_from_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sol O2 (S2b): an earlier publication must not outlive a probe that
        now says public -- a second wiring clears store, verdict and pending."""

        class _Private:
            async def assert_private(self, *, require_verified: bool = True) -> dict:
                return {"public_access_block": True, "policy_status": None}

        class _NowPublic:
            async def assert_private(self, *, require_verified: bool = True) -> dict:
                raise GarudaArtifactsStoreUnavailable("PUBLIC")

        app = FastAPI()
        monkeypatch.setattr(tigris_store, "TigrisArtifactObjectStore", _Private)
        await _wire(app)
        assert isinstance(app.state.garuda_artifact_store, _Private)

        monkeypatch.setattr(tigris_store, "TigrisArtifactObjectStore", _NowPublic)
        await initialize_garuda_services(app, None)
        assert not hasattr(app.state, "garuda_artifact_store"), "cleared before the new probe"
        assert not hasattr(app.state, "garuda_artifact_privacy")
        await probe_garuda_artifact_bucket(app)
        assert not hasattr(app.state, "garuda_artifact_store")
        assert not hasattr(app.state, "garuda_artifact_store_pending")

    @pytest.mark.asyncio
    async def test_the_probe_never_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Decision #44 mutation: a probe that raises instead of not publishing
        would turn one product's missing bucket into a process that does not
        boot. Executed: every failure shape returns, none propagates."""

        class _Raises:
            async def assert_private(self, *, require_verified: bool = True) -> dict:
                raise GarudaArtifactsStoreUnavailable("PUBLIC")

        class _Explodes:
            async def assert_private(self, *, require_verified: bool = True) -> dict:
                raise OSError("network")

        for stub in (_Raises, _Explodes):
            app = FastAPI()
            app.state.garuda_artifact_store_pending = stub()
            await probe_garuda_artifact_bucket(app)  # must not raise
            assert not hasattr(app.state, "garuda_artifact_store")

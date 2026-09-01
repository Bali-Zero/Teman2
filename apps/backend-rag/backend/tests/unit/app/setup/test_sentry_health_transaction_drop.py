"""The health-check transaction drop, and the error it must NEVER drop.

WHY: measured on `bali-zero-7p` over 7 days (2026-08-28), the `error` category
took 1,952 accepted against 753 rate_limited — 28% of production errors dropped
for quota, chosen by arrival order rather than by importance. A dropped event is
indistinguishable from one that never happened.

THE LOAD-BEARING HALF is the innocence side. A health check that 200s every 15
seconds is a metronome; a health check that 500s is one of the most important
errors this system can produce — the 2026-04-29 outage was exactly that, and
`/health` answering 200 while the RAG worker was dead is its own scar. A filter
keyed on the URL would delete the second along with the first.
"""

import importlib.util
import sys
from pathlib import Path

_MODULE = (
    Path(__file__).resolve().parents[4]
    / "app"
    / "setup"
    / "sentry_config.py"
)
_SPEC = importlib.util.spec_from_file_location("sentry_config_under_test", _MODULE)
assert _SPEC is not None and _SPEC.loader is not None
sc = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = sc
_SPEC.loader.exec_module(sc)


def _txn(name: str) -> dict:
    return {"type": "transaction", "transaction": name}


def _error(name: str) -> dict:
    # No "type" key at all is how the SDK shapes an error event.
    return {"transaction": name, "exception": {"values": [{"value": "boom"}]}}


class TestTheHookIsACTUALLYWIRED:
    """The defect a cross-family reviewer found by reading the SDK, not the diff.

    `sentry_sdk`'s client guards `before_send` with
    `event.get("type") != "transaction"` and routes transactions to
    `before_send_transaction` instead — verbatim in the installed version. The
    first version of this filter lived in `before_send`, so in production it
    never ran, while a test that called the inner function directly stayed
    green. That is W116 with a passing test on top, which is the only reason it
    could ship.
    """

    def test_the_installed_sdk_really_does_skip_before_send_for_transactions(self) -> None:
        # Anchor the premise to the SDK rather than to a memory of it: if a
        # future SDK starts routing transactions through `before_send`, this
        # test says so instead of leaving the reason for the split unexplained.
        import inspect

        import sentry_sdk.client as client_mod

        src = inspect.getsource(client_mod)
        assert 'event.get("type") != "transaction"' in src
        assert "before_send_transaction" in src

    def test_init_registers_before_send_transaction(self, monkeypatch) -> None:
        captured: dict = {}

        def fake_init(**kwargs):
            captured.update(kwargs)

        # `_init_sentry_blocking` imports sentry_sdk lazily inside the function
        # (it must not block Fly health checks), so the patch goes on the module
        # object the import will resolve to, not on an attribute of the module
        # under test.
        import sentry_sdk

        monkeypatch.setattr(sentry_sdk, "init", fake_init)
        sc._init_sentry_blocking("https://k@o1.ingest.us.sentry.io/2")

        assert captured.get("before_send_transaction") is sc._before_send_transaction, (
            "a transaction filter that is not registered as before_send_transaction "
            "never runs, however well its own function is tested"
        )
        # And the callable really drops through the hook the SDK will call.
        assert captured["before_send_transaction"](_txn("/health"), {}) is None
        assert captured["before_send_transaction"](_txn("/api/crm/practices"), {}) is not None


class TestGuilt:
    def test_a_health_transaction_is_dropped(self) -> None:
        for path in ("/health", "/healthz", "/readyz", "/livez", "/api/health"):
            assert sc._is_health_transaction(_txn(path)) is True, path
            assert sc._before_send_transaction(_txn(path), {}) is None, path

    def test_a_method_prefixed_transaction_name_is_recognised(self) -> None:
        # Sentry names transactions "GET /health" on several integrations.
        assert sc._is_health_transaction(_txn("GET /health")) is True

    def test_a_sub_path_of_a_health_route_is_dropped(self) -> None:
        assert sc._is_health_transaction(_txn("/health/detailed")) is True


class TestInnocence:
    def test_an_ERROR_on_a_health_path_is_KEPT(self) -> None:
        """The case the whole design turns on.

        `/health` returning 500 is the single most valuable error this backend
        can emit. Dropping by URL would have deleted it.
        """
        event = _error("/health")
        assert sc._is_health_transaction(event) is False
        assert sc._before_send_impl(event, {}) is not None
        # ...and through the hook the SDK actually calls for errors.
        assert sc._before_send(event, {}) is not None

    def test_a_real_transaction_is_kept(self) -> None:
        assert sc._is_health_transaction(_txn("/api/crm/practices")) is False
        assert sc._before_send_transaction(_txn("/api/crm/practices"), {}) is not None

    def test_a_route_that_merely_STARTS_with_a_health_word_is_kept(self) -> None:
        # Over-match guard (superscar family #3): substring matching would eat
        # these, and they are real endpoints, not metronomes.
        for name in ("/healthcheck-audit", "/api/health-report", "/healthy-clients"):
            assert sc._is_health_transaction(_txn(name)) is False, name

    def test_malformed_events_are_kept_rather_than_guessed_at(self) -> None:
        # Sentry drops an event silently if before_send raises, so any surprise
        # here would delete a real error. Everything unrecognised is kept.
        for weird in (
            {},
            {"type": "transaction"},
            {"type": "transaction", "transaction": None},
            {"type": "transaction", "transaction": 42},
            {"type": None, "transaction": "/health"},
        ):
            assert sc._is_health_transaction(weird) is False, weird

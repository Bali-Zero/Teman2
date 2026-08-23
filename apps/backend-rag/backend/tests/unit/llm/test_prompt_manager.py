"""
Unit tests for PromptManager
Target: 100% coverage
"""

import importlib
import logging
import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.llm.prompt_manager import (
    PromptManager,
    _get_tone_prompt,
    _TonePromptsDict,
)


class TestPromptManager:
    """Tests for PromptManager"""

    def test_init(self):
        """Test initialization"""
        manager = PromptManager()
        assert manager is not None

    def test_load_system_prompt(self):
        """Test loading system prompt via get_system_prompt (uses ZANTARA_MASTER_TEMPLATE)"""
        manager = PromptManager()
        prompt = manager.get_system_prompt()
        assert prompt is not None
        assert isinstance(prompt, str)

    def test_load_system_prompt_not_found(self):
        """Test get_system_prompt always returns a string (template-based, no file I/O)"""
        manager = PromptManager()
        prompt = manager.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_build_prompt_with_tone(self):
        """Test building prompt with tone via build_system_prompt"""
        manager = PromptManager()
        prompt = manager.build_system_prompt(style="professional")
        assert prompt is not None
        assert isinstance(prompt, str)

    def test_build_prompt_without_tone(self):
        """Test building prompt without tone"""
        manager = PromptManager()
        prompt = manager.build_system_prompt()
        assert prompt is not None
        assert isinstance(prompt, str)

    def test_get_tone_prompt_string(self):
        """Test getting tone prompt with string"""
        result = _get_tone_prompt("professional")
        assert result is not None
        assert isinstance(result, str)

    def test_get_tone_prompt_enum(self):
        """Test getting tone prompt with enum-like object"""

        class MockToneStyle:
            value = "warm"

        result = _get_tone_prompt(MockToneStyle())
        assert result is not None

    def test_get_tone_prompt_none(self):
        """Test getting tone prompt with None"""
        result = _get_tone_prompt(None)
        assert result is None

    def test_get_tone_prompt_invalid(self):
        """Test getting tone prompt with invalid value"""
        result = _get_tone_prompt("invalid_tone")
        assert result is None

    def test_tone_prompts_dict_get(self):
        """Test TonePromptsDict get method"""
        tone_dict = _TonePromptsDict()
        result = tone_dict.get("professional")
        assert result is not None

    def test_tone_prompts_dict_get_default(self):
        """Test TonePromptsDict get with default"""
        tone_dict = _TonePromptsDict()
        result = tone_dict.get("invalid", "default")
        assert result == "default"


class TestPromptManagerVersionSelection:
    """ZANTARA_PROMPT_VERSION selection (v1/v2/v3/v4) via the module-level
    door in prompt_manager.py. _PROMPT_VERSION is read at IMPORT time, so
    each case sets the env var then importlib.reload()s the module — and
    ALWAYS restores the default (v1) afterwards so later tests/imports in
    this process see the same module state they'd see on a fresh import
    (cicatrix #10-adjacent: don't leave cross-test global state behind).

    2026-07-17 design doc §6 promised "a v4 case mirroring the existing
    v2/v3 coverage" — that coverage never existed, so this adds v1/v2/v3/v4
    together rather than mirroring nothing.
    """

    @pytest.fixture(autouse=True)
    def _restore_default_version(self, monkeypatch):
        """Ensure ZANTARA_PROMPT_VERSION is unset and the module is back on
        its default (v1) import state before AND after every test in this
        class, regardless of pass/fail."""
        import backend.llm.prompt_manager as pm

        monkeypatch.delenv("ZANTARA_PROMPT_VERSION", raising=False)
        importlib.reload(pm)
        yield
        monkeypatch.delenv("ZANTARA_PROMPT_VERSION", raising=False)
        importlib.reload(pm)

    def _reload_with_version(self, monkeypatch, version: str | None):
        import backend.llm.prompt_manager as pm

        if version is None:
            monkeypatch.delenv("ZANTARA_PROMPT_VERSION", raising=False)
        else:
            monkeypatch.setenv("ZANTARA_PROMPT_VERSION", version)
        importlib.reload(pm)
        return pm

    def test_default_no_env_var_resolves_v1(self, monkeypatch):
        pm = self._reload_with_version(monkeypatch, None)
        assert pm.ZANTARA_MASTER_TEMPLATE == pm._TEMPLATE_V1

    def test_v2_env_var_resolves_v2_template(self, monkeypatch):
        pm = self._reload_with_version(monkeypatch, "v2")
        from backend.prompts.zantara_core_v2 import (
            ZANTARA_MASTER_TEMPLATE as template_v2,
        )

        assert pm.ZANTARA_MASTER_TEMPLATE == template_v2
        assert pm.ZANTARA_MASTER_TEMPLATE != pm._TEMPLATE_V1

    def test_v3_env_var_resolves_v3_template(self, monkeypatch):
        pm = self._reload_with_version(monkeypatch, "v3")
        from backend.prompts.zantara_core_v3 import (
            ZANTARA_MASTER_TEMPLATE as template_v3,
        )

        assert pm.ZANTARA_MASTER_TEMPLATE == template_v3

    def test_v4_env_var_resolves_v4_template(self, monkeypatch):
        """The whole point of this PR: ZANTARA_PROMPT_VERSION=v4 must
        actually select zantara_core_v4's template through this door."""
        pm = self._reload_with_version(monkeypatch, "v4")
        from backend.prompts.zantara_core_v4 import (
            ZANTARA_MASTER_TEMPLATE as template_v4,
        )

        assert pm.ZANTARA_MASTER_TEMPLATE == template_v4
        assert "unified prompt door" in pm.ZANTARA_MASTER_TEMPLATE
        assert "{today_wita}" in pm.ZANTARA_MASTER_TEMPLATE

    def test_v4_get_today_wita_is_bound_and_callable(self, monkeypatch):
        pm = self._reload_with_version(monkeypatch, "v4")
        result = pm.get_today_wita()
        assert isinstance(result, str)
        assert "WITA" in result

    def test_v5_env_var_resolves_v5_client_template(self, monkeypatch):
        """ZANTARA_PROMPT_VERSION=v5 selects zantara_core_v5's audience-
        composed build through this door, bound (for the legacy flat-string
        name) to the "client" audience — the most-restricted, fail-safe
        default."""
        pm = self._reload_with_version(monkeypatch, "v5")
        from backend.prompts.zantara_core_v5 import (
            build_master_template as build_v5,
        )

        assert pm.PROMPT_VERSION_ACTIVE == "v5"
        assert pm.ZANTARA_MASTER_TEMPLATE == build_v5("client")
        assert pm.ZANTARA_MASTER_TEMPLATE != pm._TEMPLATE_V1
        assert "{today_wita}" in pm.ZANTARA_MASTER_TEMPLATE

    def test_v5_get_today_wita_is_bound_and_callable(self, monkeypatch):
        pm = self._reload_with_version(monkeypatch, "v5")
        result = pm.get_today_wita()
        assert isinstance(result, str)
        assert "WITA" in result

    def test_unrecognized_version_falls_back_to_v1(self, monkeypatch):
        """An unknown value (typo, e.g. 'v9') is not one of the explicit
        branches — falls to the `else` clause, same as no env var set."""
        pm = self._reload_with_version(monkeypatch, "v9")
        assert pm.ZANTARA_MASTER_TEMPLATE == pm._TEMPLATE_V1
        assert pm.PROMPT_VERSION_ACTIVE == "v1"


class TestPromptManagerFailLoudOnUnknownVersion:
    """Task: an EXPLICITLY-SET, non-empty ZANTARA_PROMPT_VERSION that isn't a
    known version (typo'd Fly secret) must fail LOUD — a logger.error naming
    the bad value and the available versions — instead of silently serving
    v1 with zero signal. An UNSET variable must keep today's meaning exactly
    unchanged: silent default to v1, no log at all."""

    @pytest.fixture(autouse=True)
    def _restore_default_version(self, monkeypatch):
        import backend.llm.prompt_manager as pm

        monkeypatch.delenv("ZANTARA_PROMPT_VERSION", raising=False)
        importlib.reload(pm)
        yield
        monkeypatch.delenv("ZANTARA_PROMPT_VERSION", raising=False)
        importlib.reload(pm)

    @staticmethod
    def _capture_module_errors(reload_target):
        """Capture ERROR records emitted DURING an import, independently of the
        global logging config AND of any ambient suppression already in effect
        when this runs.

        `caplog` reaches this logger only while propagation to the root handler
        is intact — and in a full-suite run an earlier import can leave
        propagation off or the root reconfigured, so the same assertion passed
        alone and failed in batch (order-dependent, i.e. it would fail in CI and
        pass locally). Attaching a handler to THIS logger removes the dependency
        on propagation — but level/handlers/disabled alone are not enough: two
        OTHER knobs are process-global (or at least logger-persistent) and are
        not scoped to "this test":

        * `logging.Logger.manager.disable` — the process-global mute set by
          `logging.disable(N)`. `Logger.isEnabledFor()` checks it BEFORE this
          logger's own level or handlers are ever consulted, so a suppressed
          level never even constructs a record — no handler, including ours,
          gets a chance to see it. pytest's own `caplog.set_level()`/
          `at_level()` do touch this exact global under the hood
          (`_pytest/logging.py::_force_enable_logging`) — but only ever to
          LOOSEN it: that helper's two write paths either lower the
          threshold (`logging.disable(max(level - 10, logging.NOTSET))`) or
          clear it outright (`logging.disable(logging.NOTSET)`), and
          `at_level()` restores the pre-existing value in a `finally`. So
          pytest is not a suppression source for this knob — cited here for
          the direction it moves it, not as a threat. No producer of an
          elevated global mute exists in this repo today: across the whole
          `backend/` tree, all 21 `conftest.py` included, the only site that
          touches `manager.disable` at all is
          `backend/tests/core/test_telegram_token_never_reaches_a_log.py`,
          and it only ever *un*-mutes (`logging.disable(logging.NOTSET)`),
          saving and restoring around it. This capture is therefore
          hardening of the promise this docstring already makes —
          "independently of the global logging config" — not the diagnosis
          of whatever CI failure motivated it, which remains unreproduced.
        * this logger's own `.filters` — `Logger.filter()` runs before
          `callHandlers()`, so a drop-everything filter attached directly to
          `backend.llm.prompt_manager` (by this test file or any other) would
          silently eat the record before our sink ever sees it, exactly like
          the propagation gap this helper already existed to close.

        Both are saved and neutralised on entry, and both are restored in
        `finally` — a failing assertion here must never leak either into the
        next test, which is how one broken test becomes a shard-wide outbreak
        (cicatrix-superscar #2, "esiste != armato").

        `importlib.reload()` (not a plain `import`) is what makes the
        module-scope `logger.error()` call happen HERE, inside the capture
        window, regardless of whether some earlier test in this process
        already imported/reloaded the module: reload always re-executes the
        module body against the CURRENT env var, it never short-circuits on
        `sys.modules` already having an entry — so a prior successful import
        with a different (or valid) `ZANTARA_PROMPT_VERSION` cannot suppress a
        later fail-loud capture.
        """
        records: list[logging.LogRecord] = []

        class _Sink(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        logger = logging.getLogger("backend.llm.prompt_manager")
        sink = _Sink(level=logging.ERROR)
        previous_level = logger.level
        previous_disabled = logger.disabled
        previous_filters = list(logger.filters)
        previous_manager_disable = logging.root.manager.disable

        logger.filters = []
        logging.disable(logging.NOTSET)  # neutralise any ambient global mute
        logger.addHandler(sink)
        logger.setLevel(logging.ERROR)
        logger.disabled = False
        try:
            importlib.reload(reload_target)
        finally:
            logger.removeHandler(sink)
            logger.setLevel(previous_level)
            logger.disabled = previous_disabled
            logger.filters = previous_filters
            logging.root.manager.disable = previous_manager_disable
        return records

    def test_unrecognized_explicit_value_logs_error(self, monkeypatch):
        import backend.llm.prompt_manager as pm

        monkeypatch.setenv("ZANTARA_PROMPT_VERSION", "v9")
        error_records = [
            r for r in self._capture_module_errors(pm) if r.levelname == "ERROR"
        ]
        assert error_records, "Expected a logger.error for an unrecognised ZANTARA_PROMPT_VERSION"
        assert any("v9" in r.getMessage() for r in error_records)
        assert any("v1" in r.getMessage() for r in error_records)
        # Still serves v1 — loud, not a crash.
        assert pm.ZANTARA_MASTER_TEMPLATE == pm._TEMPLATE_V1

    def test_unset_version_stays_silent_and_identical_to_today(self, monkeypatch):
        import backend.llm.prompt_manager as pm

        monkeypatch.delenv("ZANTARA_PROMPT_VERSION", raising=False)
        error_records = [
            r for r in self._capture_module_errors(pm) if r.levelname == "ERROR"
        ]
        assert error_records == [], (
            "Unset ZANTARA_PROMPT_VERSION must never log an error — this is "
            "today's default path, not a misconfiguration."
        )
        assert pm.ZANTARA_MASTER_TEMPLATE == pm._TEMPLATE_V1
        assert pm.PROMPT_VERSION_ACTIVE == "v1"

    def test_capture_survives_a_pre_existing_global_logging_disable(self, monkeypatch):
        """GUILT: a process-global mute — whatever calls `logging.disable(N)` —
        must not blind the capture. pytest's own `caplog.set_level()`/
        `at_level()` do touch this exact global (`_pytest/logging.py::
        _force_enable_logging`), but only ever to LOOSEN it, never to raise
        it — so this is not a reproduction of pytest's own behaviour. It is a
        synthetic worst case: simulates a sibling test/module in the SAME
        process (CI runs this suite under `pytest-xdist --dist loadfile`,
        many files per worker) leaving `logging.Logger.manager.disable`
        elevated by SOME OTHER means when this test starts, so the capture
        stays defensive even though no such producer is known to exist in
        this repo today.
        """
        import backend.llm.prompt_manager as pm

        logging.disable(logging.CRITICAL)
        try:
            monkeypatch.setenv("ZANTARA_PROMPT_VERSION", "v9")
            error_records = [
                r for r in self._capture_module_errors(pm) if r.levelname == "ERROR"
            ]
        finally:
            logging.disable(logging.NOTSET)
        assert error_records, (
            "a pre-existing logging.disable(CRITICAL) must not suppress the "
            "fail-loud ERROR record — the capture must neutralise it"
        )
        assert any("v9" in r.getMessage() for r in error_records)

    def test_capture_survives_a_drop_everything_filter_on_the_logger(self, monkeypatch):
        """GUILT: a filter attached directly to `backend.llm.prompt_manager`
        runs (via `Logger.filter()`) BEFORE any handler — including our own
        sink — ever sees the record. A filter left behind by an unrelated test
        (or a defensive "quiet this logger during tests" helper elsewhere)
        must not make this capture read as silence.
        """
        import backend.llm.prompt_manager as pm

        logger = logging.getLogger("backend.llm.prompt_manager")

        class _DropEverything(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                return False

        drop_all = _DropEverything()
        logger.addFilter(drop_all)
        try:
            monkeypatch.setenv("ZANTARA_PROMPT_VERSION", "v9")
            error_records = [
                r for r in self._capture_module_errors(pm) if r.levelname == "ERROR"
            ]
        finally:
            logger.removeFilter(drop_all)
        assert error_records, (
            "a pre-existing drop-everything filter on the logger must not "
            "suppress the fail-loud ERROR record — the capture must clear it"
        )
        assert any("v9" in r.getMessage() for r in error_records)

    def test_capture_stays_silent_for_known_versions_under_a_prior_global_mute(
        self, monkeypatch
    ):
        """INNOCENCE: neutralising ambient suppression must not manufacture a
        false ERROR for a legitimate version — the cure only removes noise
        that would otherwise hide a real record, it never adds one.
        """
        import backend.llm.prompt_manager as pm

        logging.disable(logging.CRITICAL)
        try:
            monkeypatch.setenv("ZANTARA_PROMPT_VERSION", "v2")
            error_records = [
                r for r in self._capture_module_errors(pm) if r.levelname == "ERROR"
            ]
        finally:
            logging.disable(logging.NOTSET)
        assert error_records == [], (
            "a valid version must never trip the fail-loud path, ambient mute "
            "or not"
        )

    def test_known_versions_never_log_the_unrecognised_error(self, monkeypatch, caplog):
        import backend.llm.prompt_manager as pm

        for version in ("v1", "v2", "v3", "v4", "v5"):
            monkeypatch.setenv("ZANTARA_PROMPT_VERSION", version)
            caplog.clear()
            with caplog.at_level("ERROR", logger="backend.llm.prompt_manager"):
                importlib.reload(pm)
            unrecognised_errors = [
                r for r in caplog.records if "not a recognised version" in r.getMessage()
            ]
            assert unrecognised_errors == [], f"version={version} should not trip the fail-loud path"

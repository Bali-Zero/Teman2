"""Unit tests for the PII-sovereignty cloud-vision gate.

SYMBIOSIS Law 2 / UU PDP Art. 56: OCR of client documents must NOT fall back to
cloud Gemini Vision unless OCR_ALLOW_CLOUD_VISION is explicitly enabled. These
tests lock in: default-deny, env-enable, fail-closed on config error, and that
the alert helper never raises on the degradation path.
"""

from unittest.mock import patch

from backend.services.multimodal import cloud_vision_gate


class TestCloudVisionAllowed:
    def test_real_config_source_declares_false_default(self) -> None:
        """The config source declares the flag with a False default (PII-safe).

        Read from the real source FILE rather than the imported module, because
        some router unit conftests swap `sys.modules['backend.app.core.config']`
        for a FakeSettings stub that has no `model_fields`. The on-disk source is
        the ground truth and is immune to that session-level pollution."""
        import pathlib
        import re

        cfg = pathlib.Path(__file__).resolve()
        # backend/tests/services/multimodal/ -> backend/app/core/config.py
        backend_root = cfg.parents[3]
        config_src = (backend_root / "app" / "core" / "config.py").read_text()
        m = re.search(r"ocr_allow_cloud_vision\s*:\s*bool\s*=\s*(\w+)", config_src)
        assert m is not None, "ocr_allow_cloud_vision field not found in config.py"
        assert m.group(1) == "False", "default MUST be False (PII-safe)"

    def test_deny_when_singleton_flag_false(self) -> None:
        """With a settings object whose flag is False, the gate denies.

        (We patch in a real-shaped object rather than trust the ambient
        singleton, which other test files' conftests may replace with a
        truthy MagicMock — that pollution is the subject of a dedicated test
        below.)"""

        class _S:
            ocr_allow_cloud_vision = False

        with patch("backend.app.core.config.settings", _S()):
            assert cloud_vision_gate.cloud_vision_allowed() is False

    def test_magicmock_settings_reads_truthy_documented_caveat(self) -> None:
        """DOCUMENTED CAVEAT: a MagicMock settings object (as some router unit
        conftests install) auto-vivifies the attr as a truthy Mock, so the gate
        reads ALLOWED under that mock. Prod settings is a real pydantic object,
        so this never affects production — but tests touching cloud OCR under
        the router conftest MUST patch cloud_vision_allowed() explicitly rather
        than rely on the default. This test pins that behavior so it's not a
        silent surprise."""
        from unittest.mock import MagicMock

        with patch("backend.app.core.config.settings", MagicMock()):
            # bool(MagicMock().ocr_allow_cloud_vision) is True
            assert cloud_vision_gate.cloud_vision_allowed() is True

    def test_enabled_when_flag_true(self) -> None:
        """When the flag is True, cloud vision is allowed."""

        class _S:
            ocr_allow_cloud_vision = True

        with patch("backend.app.core.config.settings", _S()):
            assert cloud_vision_gate.cloud_vision_allowed() is True

    def test_missing_attr_fails_closed(self) -> None:
        """A settings object without the attr → fail closed (deny)."""

        class _S:
            pass  # no ocr_allow_cloud_vision attribute

        with patch("backend.app.core.config.settings", _S()):
            assert cloud_vision_gate.cloud_vision_allowed() is False

    def test_config_import_error_fails_closed(self) -> None:
        """If reading config raises, the gate denies (never accidentally allows)."""

        # Force the lazy `from backend.app.core.config import settings` to explode
        # by replacing the module attribute with something whose getattr raises.
        class _Boom:
            @property
            def ocr_allow_cloud_vision(self):  # type: ignore[no-untyped-def]
                raise RuntimeError("config blew up")

        with patch("backend.app.core.config.settings", _Boom()):
            assert cloud_vision_gate.cloud_vision_allowed() is False


class TestNoteCloudOcrBlocked:
    def test_logs_warning(self, caplog) -> None:  # type: ignore[no-untyped-def]
        import logging

        with caplog.at_level(logging.WARNING):
            cloud_vision_gate.note_cloud_ocr_blocked("unit.test.context")
        joined = " ".join(r.getMessage() for r in caplog.records)
        assert "PII-SOVEREIGNTY" in joined
        assert "unit.test.context" in joined

    def test_never_raises_when_alerter_unimportable(self) -> None:
        """If `scripts.sentinel_lib.alerter` can't be imported (real test-env
        condition), the helper must still complete — the import is inside a
        try/except by design."""
        # No patching: in the test environment scripts.sentinel_lib is not on the
        # path, so the inner import raises ImportError. Must not propagate.
        cloud_vision_gate.note_cloud_ocr_blocked("ctx-unimportable")

    def test_never_raises_when_send_alert_explodes(self) -> None:
        """When send_alert IS importable but raises, the failure is swallowed."""
        import sys
        import types

        fake_alerter = types.ModuleType("scripts.sentinel_lib.alerter")

        def _boom(*_a, **_k):  # noqa: ANN002, ANN003
            raise RuntimeError("telegram down")

        fake_alerter.send_alert = _boom  # type: ignore[attr-defined]
        fake_pkg = types.ModuleType("scripts.sentinel_lib")
        with patch.dict(
            sys.modules,
            {
                "scripts.sentinel_lib": fake_pkg,
                "scripts.sentinel_lib.alerter": fake_alerter,
            },
        ):
            # Must complete without raising despite send_alert exploding.
            cloud_vision_gate.note_cloud_ocr_blocked("ctx-explode")

    def test_returns_none(self) -> None:
        assert cloud_vision_gate.note_cloud_ocr_blocked("ctx") is None

import os
import pytest
from unittest.mock import patch
from mata_garuda.foundations.openllmetry_init import (
    init_openllmetry,
    is_openllmetry_enabled,
)


def test_is_disabled_when_no_env_vars():
    with patch.dict(os.environ, {}, clear=True):
        assert is_openllmetry_enabled() is False


def test_is_enabled_when_endpoint_set():
    with patch.dict(os.environ, {"OPENLLMETRY_ENDPOINT": "http://localhost:4318"}, clear=True):
        assert is_openllmetry_enabled() is True


def test_is_disabled_via_kill_switch():
    """LANGFUSE_ENABLED=false acts as full kill-switch (Nuzantara PR #312 pattern)."""
    with patch.dict(
        os.environ,
        {"OPENLLMETRY_ENDPOINT": "http://localhost:4318", "LANGFUSE_ENABLED": "false"},
        clear=True,
    ):
        assert is_openllmetry_enabled() is False


def test_init_returns_quickly_when_disabled():
    """Dormant mode = 1ms no-op (Nuzantara cicatrix pattern)."""
    with patch.dict(os.environ, {}, clear=True):
        result = init_openllmetry(service_name="test-service")
    assert result is False  # not initialized

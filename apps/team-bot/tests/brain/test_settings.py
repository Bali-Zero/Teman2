"""Tests for team_bot.brain.settings.load_tp1_api_key — mirrors
scripts/arsenal_probe.py::load_tp1_settings_key's own test coverage shape
(scripts/tests/test_arsenal_probe.py), independently, since this module is
a deliberate mirror not an import."""

from __future__ import annotations

import json

import pytest

from team_bot.brain.settings import TP1CredentialError, load_tp1_api_key


def test_missing_file_raises_named_error(tmp_path) -> None:
    missing = tmp_path / "does-not-exist.json"
    with pytest.raises(TP1CredentialError, match="not found"):
        load_tp1_api_key(str(missing))


def test_not_json_raises_named_error(tmp_path) -> None:
    p = tmp_path / "settings.json"
    p.write_text("not json", encoding="utf-8")
    with pytest.raises(TP1CredentialError, match="unreadable"):
        load_tp1_api_key(str(p))


def test_missing_env_block_raises(tmp_path) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"other": "stuff"}), encoding="utf-8")
    with pytest.raises(TP1CredentialError, match="BAILIAN_TOKEN_PLAN_API_KEY"):
        load_tp1_api_key(str(p))


def test_missing_key_field_raises(tmp_path) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"env": {"OTHER_KEY": "x"}}), encoding="utf-8")
    with pytest.raises(TP1CredentialError, match="BAILIAN_TOKEN_PLAN_API_KEY"):
        load_tp1_api_key(str(p))


def test_empty_key_value_raises(tmp_path) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"env": {"BAILIAN_TOKEN_PLAN_API_KEY": "   "}}), encoding="utf-8")
    with pytest.raises(TP1CredentialError, match="BAILIAN_TOKEN_PLAN_API_KEY"):
        load_tp1_api_key(str(p))


def test_valid_key_returned_stripped(tmp_path) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"env": {"BAILIAN_TOKEN_PLAN_API_KEY": "  sk-abc123  "}}), encoding="utf-8")
    assert load_tp1_api_key(str(p)) == "sk-abc123"


def test_non_utf8_bytes_raise_named_error_not_uncaught_unicode_error(tmp_path) -> None:
    p = tmp_path / "settings.json"
    p.write_bytes(b"\xff\xfe not valid utf-8 json")
    with pytest.raises(TP1CredentialError, match="unreadable"):
        load_tp1_api_key(str(p))

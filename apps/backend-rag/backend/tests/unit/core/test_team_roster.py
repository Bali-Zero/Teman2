"""Tests for the single staff-roster loader. Invented data only."""

import importlib
import json
import logging

import pytest

from backend.core import team_roster
from backend.core.team_roster import TeamRosterError, load_team_roster, team_roster_source

SENTINEL = "SENTINEL-do-not-leak"


def _doc(tag: str) -> str:
    return json.dumps([{"id": tag, "email": f"{tag}@example.test"}])


@pytest.fixture(autouse=True)
def _clean(monkeypatch, tmp_path):
    monkeypatch.delenv("TEAM_MEMBERS_JSON", raising=False)
    monkeypatch.delenv("TEAM_MEMBERS_FILE", raising=False)
    default = tmp_path / "default.json"
    default.write_text(_doc("default"))
    monkeypatch.setattr(team_roster, "DEFAULT_ROSTER_PATH", default)
    return default


def test_env_json_wins_over_env_file_and_default(monkeypatch, tmp_path):
    f = tmp_path / "f.json"
    f.write_text(_doc("file"))
    monkeypatch.setenv("TEAM_MEMBERS_FILE", str(f))
    monkeypatch.setenv("TEAM_MEMBERS_JSON", _doc("inline"))
    assert load_team_roster()[0]["id"] == "inline"
    assert team_roster_source() == "env:TEAM_MEMBERS_JSON"


def test_env_file_wins_over_default(monkeypatch, tmp_path):
    f = tmp_path / "f.json"
    f.write_text(_doc("file"))
    monkeypatch.setenv("TEAM_MEMBERS_FILE", str(f))
    assert load_team_roster()[0]["id"] == "file"
    assert team_roster_source() == f"file:{f}"


def test_default_path_used(_clean):
    assert load_team_roster()[0]["id"] == "default"
    assert team_roster_source() == f"file:{_clean}"


def test_env_file_pointing_nowhere_falls_through_to_default(monkeypatch, tmp_path):
    monkeypatch.setenv("TEAM_MEMBERS_FILE", str(tmp_path / "missing.json"))
    assert load_team_roster()[0]["id"] == "default"


def test_no_source(monkeypatch, tmp_path):
    monkeypatch.setattr(team_roster, "DEFAULT_ROSTER_PATH", tmp_path / "nope.json")
    assert load_team_roster() == []
    assert team_roster_source() is None


@pytest.mark.parametrize("blank", ["", "   \n"])
def test_empty_env_is_absent(monkeypatch, blank):
    monkeypatch.setenv("TEAM_MEMBERS_JSON", blank)
    monkeypatch.setenv("TEAM_MEMBERS_FILE", blank)
    assert load_team_roster()[0]["id"] == "default"


@pytest.mark.parametrize(
    "bad",
    [
        "{not json " + SENTINEL,
        json.dumps({"k": SENTINEL}),
        json.dumps([{"ok": 1}, SENTINEL]),
    ],
)
def test_malformed_env_json_names_source_not_content(monkeypatch, bad):
    monkeypatch.setenv("TEAM_MEMBERS_JSON", bad)
    with pytest.raises(TeamRosterError) as ei:
        load_team_roster()
    assert "TEAM_MEMBERS_JSON" in str(ei.value)
    assert SENTINEL not in str(ei.value)
    assert isinstance(ei.value, ValueError)


def test_malformed_file_names_path_not_content(monkeypatch, tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("[1, 2] " + SENTINEL)
    monkeypatch.setenv("TEAM_MEMBERS_FILE", str(f))
    with pytest.raises(TeamRosterError) as ei:
        load_team_roster()
    assert str(f) in str(ei.value)
    assert SENTINEL not in str(ei.value)


@pytest.fixture
def shim(monkeypatch):
    """The shim module, reloaded against the real environment again on teardown."""
    import backend.data.team_members as module

    yield module
    monkeypatch.undo()
    importlib.reload(module)


def test_shim_matches_loader(monkeypatch, shim):
    monkeypatch.setenv("TEAM_MEMBERS_JSON", _doc("inline"))
    importlib.reload(shim)
    assert shim.TEAM_MEMBERS == [{"id": "inline", "email": "inline@example.test"}]


def test_shim_degrades_to_empty_with_warning(monkeypatch, caplog, shim):
    monkeypatch.setenv("TEAM_MEMBERS_JSON", "{bad " + SENTINEL)
    with caplog.at_level(logging.WARNING):
        importlib.reload(shim)
    assert shim.TEAM_MEMBERS == []
    assert any("TEAM_MEMBERS_JSON" in r.getMessage() for r in caplog.records)
    assert SENTINEL not in caplog.text

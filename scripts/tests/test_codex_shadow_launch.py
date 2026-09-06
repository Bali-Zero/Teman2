"""The private launcher preserves native metadata, never refresh authority."""

from copy import deepcopy
import json
from pathlib import Path
import stat

import pytest

from scripts.conductor.codex_shadow_launch import prepare_auth

AUTH = {
    "auth_mode": "chatgpt",
    "OPENAI_API_KEY": None,
    "last_refresh": "2026-09-06T00:00:00Z",
    "unexpected": "must-not-copy",
    "tokens": {
        "access_token": "synthetic-access",
        "id_token": "synthetic-id",
        "refresh_token": "synthetic-refresh",
        "account_id": "synthetic-account",
        "unexpected": "must-not-copy",
    },
}


def test_access_snapshot_cannot_rotate_source_oauth_and_is_private(
    tmp_path: Path,
) -> None:
    source, target = tmp_path / "source.json", tmp_path / "target.json"
    source.write_text(json.dumps(AUTH))
    original = source.read_bytes()
    prepare_auth(source, target)
    copied = json.loads(target.read_text())
    assert copied["last_refresh"] == AUTH["last_refresh"]
    assert copied["tokens"]["refresh_token"] == ""
    assert copied["tokens"]["access_token"] == "synthetic-access"
    assert "unexpected" not in copied and "unexpected" not in copied["tokens"]
    assert source.read_bytes() == original
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


@pytest.mark.parametrize(
    "change", ["paid", "key", "missing_access", "missing_refresh_time"]
)
def test_unqualified_credentials_are_not_copied(tmp_path: Path, change: str) -> None:
    auth = deepcopy(AUTH)
    if change == "paid":
        auth["auth_mode"] = "apikey"
    if change == "key":
        auth["OPENAI_API_KEY"] = "synthetic-noncredential"
    if change == "missing_access":
        auth["tokens"].pop("access_token")
    if change == "missing_refresh_time":
        auth.pop("last_refresh")
    source, target = tmp_path / "source.json", tmp_path / "target.json"
    source.write_text(json.dumps(auth))
    with pytest.raises(PermissionError):
        prepare_auth(source, target)
    assert not target.exists()


def test_existing_auth_snapshot_is_never_overwritten(tmp_path: Path) -> None:
    source, target = tmp_path / "source.json", tmp_path / "target.json"
    source.write_text(json.dumps(AUTH))
    target.write_text("preserve")
    with pytest.raises(FileExistsError):
        prepare_auth(source, target)
    assert target.read_text() == "preserve"

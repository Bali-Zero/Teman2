"""The private launcher preserves native metadata, never refresh authority."""

from copy import deepcopy
import json
from pathlib import Path
import stat
from unittest.mock import AsyncMock

import pytest

from scripts.conductor import codex_shadow_launch as launcher
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


@pytest.mark.parametrize("version", tuple(launcher.QUALIFIED_BINARY_SHA256))
def test_only_the_observed_version_and_binary_pair_is_qualified(version: str) -> None:
    launcher.validate_runtime_binding(
        version, launcher.QUALIFIED_BINARY_SHA256[version]
    )
    with pytest.raises(PermissionError, match="native_binary_unqualified"):
        launcher.validate_runtime_binding(version, "unobserved-bytes")
    other = next(v for v in launcher.QUALIFIED_BINARY_SHA256 if v != version)
    with pytest.raises(PermissionError, match="native_binary_unqualified"):
        launcher.validate_runtime_binding(
            version, launcher.QUALIFIED_BINARY_SHA256[other]
        )


def test_newer_version_is_not_implicitly_qualified() -> None:
    with pytest.raises(PermissionError, match="native_version_unqualified"):
        launcher.validate_runtime_binding(
            "codex-cli 0.150.0", launcher.QUALIFIED_BINARY_SHA256["codex-cli 0.149.0"]
        )


@pytest.mark.parametrize("npm_present", (True, False))
def test_observed_native_npm_and_cask_layouts(
    monkeypatch: pytest.MonkeyPatch, npm_present: bool
) -> None:
    import platform

    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    cask = Path("/opt/homebrew/Caskroom/codex/0.148.0/bin/codex")
    npm = Path(
        "/opt/homebrew/lib/node_modules/@openai/codex/node_modules/"
        "@openai/codex-darwin-arm64/vendor/aarch64-apple-darwin/bin/codex"
    )
    monkeypatch.setattr(
        Path, "is_file", lambda path: path == cask or npm_present and path == npm
    )
    monkeypatch.setattr(Path, "resolve", lambda path: path)
    monkeypatch.setattr(launcher.os, "access", lambda path, mode: True)
    assert launcher.native_binary() == (npm if npm_present else cask)


@pytest.mark.asyncio
async def test_unknown_binary_is_not_executed_or_given_an_auth_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio

    binary = tmp_path / "codex"
    binary.write_bytes(b"unqualified executable")
    monkeypatch.setattr(launcher, "native_binary", lambda: binary)
    launched = AsyncMock()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", launched)
    with pytest.raises(PermissionError, match="native_binary_unqualified"):
        async with launcher.launch_shadow(tmp_path / "missing-auth-home"):
            pytest.fail("unknown runtime admitted")
    launched.assert_not_called()

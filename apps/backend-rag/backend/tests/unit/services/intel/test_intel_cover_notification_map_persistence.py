"""
Guilt AND innocence for the Intel cover-handler notification map path.

PENDING-ARMS 2026-08-02: `NOTIFICATION_MAP_FILE` was a module-level constant
hardcoded to `/tmp/staging/notification_map.json`, while every sibling path in
this module resolves through `settings.get_intel_staging_base_dir` (which
answers `/data/staging` on Fly, `/tmp/staging` locally). `/tmp` does not
survive a container restart, so the map that lets a Telegram `/cover` caption
find its article was silently emptied by every deploy — after which
`_match_article()` falls through to the Priority-2 branch, the same one that
used the caption's id verbatim (the arbitrary-write chain closed by #3505).

No cross-deploy migration is needed: a Fly rolling deploy replaces the
container, so a new process cannot see the old container's `/tmp` filesystem
regardless of where the map file lived — there is nothing to copy forward.
"""

import json

import pytest

from backend.app.core.config import settings
from backend.services.intel import intel_cover_handler as cover_mod


def _redirect_staging_root(monkeypatch, tmp_path) -> None:
    """
    Point the staging root at tmp_path BEFORE any handler is constructed.

    Twin of the identically-named helper in
    `test_intel_item_id_shape.py::_redirect_staging_root` — deliberately
    duplicated rather than hoisted into the root conftest, which is a hot
    zone. See that docstring for why both branches (property vs plain
    attribute) exist: this module can be collected either standalone (real
    `Settings`, read-only property) or alongside routers tests that install a
    MagicMock `settings` (plain attribute).
    """
    if isinstance(getattr(type(settings), "get_intel_staging_base_dir", None), property):
        monkeypatch.setattr(
            type(settings),
            "get_intel_staging_base_dir",
            property(lambda _self: str(tmp_path)),
            raising=True,
        )
    else:
        monkeypatch.setattr(settings, "get_intel_staging_base_dir", str(tmp_path), raising=False)
    assert settings.get_intel_staging_base_dir == str(tmp_path), (
        "staging-root redirect did not take — the test would read/write the real tree"
    )


class TestMapPathFollowsStagingBase:
    def test_guilt_map_path_is_not_hardcoded_to_tmp_staging(self, tmp_path, monkeypatch) -> None:
        """
        The pre-fix constant pointed at `/tmp/staging` unconditionally — redirecting
        `get_intel_staging_base_dir` to a tmp_path that is NOT `/tmp/staging` must
        move the resolved map path along with it, or this assertion reproduces the
        original bug.
        """
        _redirect_staging_root(monkeypatch, tmp_path)
        resolved = cover_mod._notification_map_file()
        assert resolved.parent == tmp_path
        assert resolved == tmp_path / "notification_map.json"
        assert str(resolved) != "/tmp/staging/notification_map.json"

    def test_innocence_resolution_tracks_settings_not_a_frozen_snapshot(
        self, tmp_path, monkeypatch
    ) -> None:
        """Two different staging roots must produce two different resolved paths."""
        first_root = tmp_path / "root-a"
        first_root.mkdir()
        second_root = tmp_path / "root-b"
        second_root.mkdir()

        _redirect_staging_root(monkeypatch, first_root)
        first = cover_mod._notification_map_file()

        _redirect_staging_root(monkeypatch, second_root)
        second = cover_mod._notification_map_file()

        assert first == first_root / "notification_map.json"
        assert second == second_root / "notification_map.json"
        assert first != second


class TestMapSurvivesAHandlerRestart:
    """
    A fresh `IntelCoverHandler()` instance stands in for "the process restarted" —
    the persistence contract this whole fix exists for.
    """

    @pytest.mark.asyncio
    async def test_guilt_registration_survives_a_new_instance_reading_the_same_root(
        self, tmp_path, monkeypatch
    ) -> None:
        _redirect_staging_root(monkeypatch, tmp_path)

        writer = cover_mod.IntelCoverHandler()
        writer.register_notification(
            telegram_message_id=42,
            chat_id=1813875994,
            intel_type="news",
            item_id="news_20260801_120000_a1b2c3d4",
            title="Test article",
        )

        # File must actually be on the resolved (redirected) root, not a
        # hardcoded elsewhere — this is the "proof-of-armed" from the ledger.
        map_file = tmp_path / "notification_map.json"
        assert map_file.exists(), "save did not land under the resolved staging base dir"

        # A brand-new instance ("restart") must see the same mapping.
        reader = cover_mod.IntelCoverHandler()
        assert "42" in reader._notification_map
        assert reader._notification_map["42"]["item_id"] == "news_20260801_120000_a1b2c3d4"

    def test_innocence_saved_json_round_trips_exactly(self, tmp_path, monkeypatch) -> None:
        _redirect_staging_root(monkeypatch, tmp_path)

        writer = cover_mod.IntelCoverHandler()
        writer.register_notification(
            telegram_message_id=7,
            chat_id=1813875994,
            intel_type="visa",
            item_id="visa_20260731_235959_deadbeef",
            title="Another article",
        )

        on_disk = json.loads((tmp_path / "notification_map.json").read_text())
        assert on_disk["7"]["intel_type"] == "visa"
        assert on_disk["7"]["item_id"] == "visa_20260731_235959_deadbeef"
        assert on_disk["7"]["title"] == "Another article"

    def test_innocence_a_fresh_root_with_no_file_yet_starts_empty(
        self, tmp_path, monkeypatch
    ) -> None:
        """No crash, no phantom entries, on the very first boot against a new volume."""
        _redirect_staging_root(monkeypatch, tmp_path)
        handler = cover_mod.IntelCoverHandler()
        assert handler._notification_map == {}

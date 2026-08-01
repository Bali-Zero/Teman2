"""
Guilt AND innocence for the intel staging item_id shape guard.

CodeQL py/path-injection #7793/#7794/#7795/#7796/#7797 (intel_staging_service) and
#3677/#3678/#3679/#6462 (intel_cover_handler): every staging path is built as
`staging_dir / f"{item_id}.json"`, and item_id reaches those joins from a JSON body
(`POST /api/intel/staging/bulk-reject/{type}` takes `item_ids: list[str]`) and from a
Telegram `/cover` caption — neither passes through a URL decoder, so the percent-decoding
that made the path-param call sites safe does not apply.

Innocence matters as much as guilt here: the ids this pipeline really uses must keep
working, or the guard trades a path traversal for an outage.
"""

import pytest

from backend.app.core.config import settings
from backend.services.intel import intel_cover_handler as cover_mod
from backend.services.intel.intel_staging_service import (
    IntelStagingService,
    assert_valid_item_id,
)


def _redirect_staging_root(monkeypatch, tmp_path) -> None:
    """
    Point the staging root at tmp_path BEFORE any service is constructed.

    `get_intel_staging_base_dir` is a property on Settings, so it has to be replaced on
    the class, not the instance — and it has to happen before `__init__`, whose
    `_ensure_directories()` would otherwise mkdir the REAL staging tree from a unit test
    (W96: tests must not write production state).
    """
    monkeypatch.setattr(
        type(settings),
        "get_intel_staging_base_dir",
        property(lambda _self: str(tmp_path)),
        raising=True,
    )

# Shapes that must keep working — `generate_item_id` emits `{type}_{ts}_{sha8}`.
LEGITIMATE = [
    "news_20260801_120000_a1b2c3d4",
    "visa_20260731_235959_deadbeef",
    "a",
    "A-B_c-9",
    "x" * 128,
]

# Shapes that must be refused. Every one of these either escapes the staging directory
# when joined, or names something outside it.
MALICIOUS = [
    "../../../../etc/passwd",
    "../../secrets",
    "/etc/passwd",
    "news/../../../etc/shadow",
    "..",
    ".",
    "",
    "x" * 129,
    "with space",
    "semi;colon",
    "null\x00byte",
    "new\nline",
    "sub/dir",
    "back\\slash",
]


class TestShapeGuard:
    @pytest.mark.parametrize("item_id", LEGITIMATE)
    def test_innocence_real_ids_are_accepted(self, item_id: str) -> None:
        assert assert_valid_item_id(item_id) is None

    @pytest.mark.parametrize("item_id", MALICIOUS)
    def test_guilt_traversal_and_junk_are_refused(self, item_id: str) -> None:
        with pytest.raises(ValueError):
            assert_valid_item_id(item_id)

    def test_guilt_non_string_is_refused(self) -> None:
        with pytest.raises(ValueError):
            assert_valid_item_id(None)  # type: ignore[arg-type]

    def test_the_message_does_not_echo_the_offending_value(self) -> None:
        """It arrives from a request body / chat caption and lands in logs and responses."""
        secret_looking = "../../../../etc/passwd"
        with pytest.raises(ValueError) as exc:
            assert_valid_item_id(secret_looking)
        assert secret_looking not in str(exc.value)

    def test_generated_ids_satisfy_their_own_guard(self, tmp_path, monkeypatch) -> None:
        """The producer and the validator must agree, or staging breaks on the next write."""
        _redirect_staging_root(monkeypatch, tmp_path)
        svc = IntelStagingService()
        generated = svc.generate_item_id("news", "Some Title", "https://example.com/a")
        assert assert_valid_item_id(generated) is None


class TestWhyTheGuardExists:
    def test_an_unguarded_join_really_does_escape_the_staging_dir(self, tmp_path) -> None:
        """Pins the premise. If this ever stops being true the guard's rationale changed."""
        staging_dir = tmp_path / "news"
        staging_dir.mkdir()
        escaped = (staging_dir / "../../../../etc/passwd.json").resolve()
        assert not str(escaped).startswith(str(staging_dir.resolve()))


class TestServiceSinks:
    @pytest.fixture()
    def svc(self, tmp_path, monkeypatch) -> IntelStagingService:
        _redirect_staging_root(monkeypatch, tmp_path)
        return IntelStagingService()

    def test_read_of_a_malformed_id_is_not_found_not_a_crash(self, svc) -> None:
        """A read answers "does this exist"; callers already map None to 404."""
        assert svc.load_staging_item("news", "../../../../etc/passwd") is None

    def test_read_of_a_real_but_absent_id_is_also_none(self, svc) -> None:
        """Innocence: the guard must not be why ordinary misses return None."""
        assert svc.load_staging_item("news", "news_20260801_120000_a1b2c3d4") is None

    def test_read_of_a_real_present_id_still_works(self, svc) -> None:
        """Innocence at the sink: a legitimate item is still readable after the guard."""
        item_id = "news_20260801_120000_a1b2c3d4"
        svc.save_staging_item("news", item_id, {"title": "ok"})
        assert svc.load_staging_item("news", item_id) == {"title": "ok"}

    def test_write_of_a_malformed_id_refuses_loudly(self, svc) -> None:
        with pytest.raises(ValueError):
            svc.save_staging_item("news", "../../../../tmp/pwned", {"title": "x"})

    def test_move_of_a_malformed_id_refuses_loudly(self, svc) -> None:
        """archive_item MOVES the file it finds — an action, not a lookup."""
        with pytest.raises(ValueError):
            svc.archive_item("news", "../../../../etc/passwd", "rejected")

    def test_move_does_not_create_anything_outside_staging(self, svc, tmp_path) -> None:
        outside = tmp_path.parent / "zz-should-never-exist"
        with pytest.raises(ValueError):
            svc.archive_item("news", f"../../{outside.name}", "rejected")
        assert not outside.exists()


class TestCoverHandlerTwin:
    """The write sink in the other module must be guarded by the SAME validator."""

    def test_cover_handler_imports_the_shared_validator(self) -> None:
        from backend.services.intel.intel_staging_service import (
            assert_valid_item_id as canonical,
        )

        assert cover_mod.assert_valid_item_id is canonical

    @pytest.mark.asyncio
    async def test_upload_cover_refuses_a_malformed_id(self) -> None:
        handler = cover_mod.IntelCoverHandler()
        with pytest.raises(ValueError):
            await handler._upload_cover("news", "../../../../tmp/pwned", b"not-an-image")

import pytest
from unittest.mock import AsyncMock, patch

from organism.post_commit_hook import main as hook_main


@pytest.mark.asyncio
async def test_emits_event_per_app_subdir(tmp_path, monkeypatch):
    apps = tmp_path / "apps"
    apps.mkdir()
    (apps / "mod_a").mkdir()
    (apps / "mod_b").mkdir()
    (apps / "_hidden").mkdir()
    monkeypatch.chdir(tmp_path)

    with patch("organism.post_commit_hook.emit_event", AsyncMock()) as mock_emit:
        count = await hook_main()

    assert count == 2  # mod_a + mod_b, _hidden skipped
    names = [c.kwargs["payload"]["module_name"] for c in mock_emit.call_args_list]
    assert "mod_a" in names
    assert "mod_b" in names
    assert "_hidden" not in names


@pytest.mark.asyncio
async def test_skips_adopted_marker_modules(tmp_path, monkeypatch):
    apps = tmp_path / "apps"
    apps.mkdir()
    (apps / "mod").mkdir()
    (apps / "mod" / ".adopted_marker").write_text("")
    monkeypatch.chdir(tmp_path)

    with patch("organism.post_commit_hook.emit_event", AsyncMock()) as mock_emit:
        count = await hook_main()

    assert count == 0
    mock_emit.assert_not_called()


@pytest.mark.asyncio
async def test_returns_zero_when_no_apps_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no apps/ subdir

    with patch("organism.post_commit_hook.emit_event", AsyncMock()) as mock_emit:
        count = await hook_main()

    assert count == 0
    mock_emit.assert_not_called()

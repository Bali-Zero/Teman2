from __future__ import annotations

from pathlib import Path


WRAPPER = (
    Path(__file__).resolve().parents[2]
    / "infra/launchagents/wrappers/bali-zero-magazine-publish.sh"
)


def test_magazine_wrapper_uses_process_held_advisory_lock() -> None:
    source = WRAPPER.read_text(encoding="utf-8")

    assert "zmodload zsh/system" in source
    assert "zsystem flock -t 0 -f" in source
    assert "zsystem flock -u" in source
    assert 'mkdir "$LOCKDIR"' not in source
    assert 'rm -rf "$LOCKDIR"' not in source

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import pytest

import wr2_ig_publish_remote as publisher


def test_carousel_root_uses_synced_war_room_override() -> None:
    env = {"WR2_WARROOM_ROOT": "/Users/nuzantara/.wr2-warroom-sync/output"}

    assert publisher._carousel_root_from_env(env, Path("/Users/nuzantara")) == Path(
        "/Users/nuzantara/.wr2-warroom-sync/output/carousel"
    )


def test_explicit_carousel_root_wins_over_war_room_override() -> None:
    env = {
        "WR2_CAROUSEL_ROOT": "/tmp/explicit-carousel",
        "WR2_WARROOM_ROOT": "/tmp/war-room-output",
    }

    assert publisher._carousel_root_from_env(env, Path("/Users/nuzantara")) == Path(
        "/tmp/explicit-carousel"
    )


def test_resolve_caption_uses_generated_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(publisher, "_build_caption", lambda slug: f"generated:{slug}")

    assert publisher._resolve_caption("visa-update", None) == "generated:visa-update"


def test_resolve_caption_reads_utf8_override(tmp_path: Path) -> None:
    caption_file = tmp_path / "caption.txt"
    approved = "A Bali update.\n\nPeriksa izin Anda — sekarang."
    caption_file.write_text(approved, encoding="utf-8")

    assert publisher._resolve_caption("unused", caption_file) == approved


def test_resolve_caption_rejects_blank_override(tmp_path: Path) -> None:
    caption_file = tmp_path / "caption.txt"
    caption_file.write_text("  \n\t", encoding="utf-8")

    with pytest.raises(publisher.PublishAborted, match="caption file is empty"):
        publisher._resolve_caption("unused", caption_file)


def test_print_caption_short_circuits_slides_credentials_and_network(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(publisher, "_build_caption", lambda slug: "approved default")
    monkeypatch.setattr(
        publisher,
        "_slug_dir",
        lambda slug: pytest.fail("caption-only mode must not discover slides"),
    )
    monkeypatch.setattr(
        publisher,
        "_resolve_pin",
        lambda email: pytest.fail("caption-only mode must not resolve credentials"),
    )
    args = argparse.Namespace(
        slug="visa-update", confirm=False, caption_file=None, print_caption=True
    )

    assert asyncio.run(publisher._run(args)) == 0
    assert capsys.readouterr().out == "approved default"


def test_parse_args_accepts_caption_options(tmp_path: Path) -> None:
    caption_file = tmp_path / "caption.txt"

    args = publisher._parse_args(
        ["visa-update", "--caption-file", str(caption_file), "--print-caption"]
    )

    assert args.caption_file == caption_file
    assert args.print_caption is True

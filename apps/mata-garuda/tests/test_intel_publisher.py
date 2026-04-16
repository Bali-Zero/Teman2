"""Tests for intel_publisher — War Room → bridge:outbound CLI tool."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from mata_garuda.bridge.envelope import Envelope
from mata_garuda.tools.intel_publisher import (
    _build_content_md,
    _extract_tags,
    _load_json,
    build_envelope,
    main,
)


# ── Fixtures ───────────────────────────────────────────────────────────


def _sample_canva() -> dict:
    return {
        "template_design_id": "DAHE6lx1lf8",
        "design_id": None,
        "design_url": None,
        "topic": "Fake Docs Crackdown: Investors Face Hurdles",
        "tone": "Urgent, Tactical",
        "slides_count": 4,
        "operations_count": 12,
        "instagram_caption": (
            "The D12 Scammer Legacy\n\n"
            "12 Japanese scammers turned the most popular visa into a red flag.\n\n"
            "#BaliZero #IndonesiaVisa #Bali"
        ),
        "created_at": "2026-04-16T02:10:57",
        "status": "pending",
    }


def _sample_slides() -> dict:
    return {
        "topic": "Fake Docs Crackdown: Investors Face Hurdles",
        "tone": "Urgent, Tactical",
        "slides": [
            {
                "slide_number": 1,
                "is_cover": True,
                "headline": "THE D12 SCAMMER LEGACY",
                "subhead": "12 Japanese scammers triggered an audit.",
                "body": None,
            },
            {
                "slide_number": 2,
                "is_cover": False,
                "headline": "THE REAL RISK",
                "body": "The deportation triggered a retroactive audit of all D12 holders.",
            },
        ],
    }


# ── unit: helpers ──────────────────────────────────────────────────────


def test_extract_tags_picks_hashtags():
    caption = "Some headline\n\n#BaliZero #IndonesiaVisa not_tag #Bali"
    tags = _extract_tags([], caption)
    assert tags == ["balizero", "indonesiavisa", "bali"]


def test_extract_tags_empty_when_no_hashtags():
    assert _extract_tags([], "no tags here") == []


def test_extract_tags_caps_at_10():
    caption = " ".join(f"#tag{i}" for i in range(20))
    tags = _extract_tags([], caption)
    assert len(tags) == 10


def test_build_content_md_uses_subhead_when_no_body():
    slides = [{"is_cover": True, "headline": "H", "subhead": "S"}]
    md = _build_content_md(slides)
    assert md == "# H\n\nS"


def test_build_content_md_separates_slides():
    slides = [
        {"is_cover": True, "headline": "Cover", "body": "x"},
        {"is_cover": False, "headline": "Two", "body": "y"},
    ]
    md = _build_content_md(slides)
    assert "# Cover" in md
    assert "## Two" in md
    assert "---" in md


# ── unit: envelope builder ─────────────────────────────────────────────


def test_build_envelope_produces_valid_envelope():
    env = build_envelope(_sample_canva(), _sample_slides())

    assert isinstance(env, Envelope)
    assert env.type == "intel.article_ready"
    assert env.source == "war_room"
    assert env.priority == 2
    assert "T" in env.timestamp


def test_build_envelope_payload_has_required_fields():
    env = build_envelope(_sample_canva(), _sample_slides())
    p = env.payload

    assert p["title"] == "Fake Docs Crackdown: Investors Face Hurdles"
    assert p["slug"].startswith("fake-docs-crackdown")
    assert ":" not in p["slug"]
    assert "BaliZero".lower() in p["tags"]
    assert p["slides_count"] == 4
    assert p["tone"] == "Urgent, Tactical"
    # article_id is a UUID
    assert len(p["article_id"]) == 36


def test_build_envelope_content_md_includes_all_slides():
    env = build_envelope(_sample_canva(), _sample_slides())
    md = env.payload["content_md"]
    assert "THE D12 SCAMMER LEGACY" in md
    assert "THE REAL RISK" in md


def test_build_envelope_handles_missing_canva_caption():
    canva = _sample_canva()
    del canva["instagram_caption"]
    slides = _sample_slides()
    slides["instagram_caption"] = "fallback #tag1"

    env = build_envelope(canva, slides)
    assert "tag1" in env.payload["tags"]


def test_build_envelope_handles_design_id_present():
    canva = _sample_canva()
    canva["design_id"] = "DAFinal123"
    canva["design_url"] = "https://canva.com/design/DAFinal123"

    env = build_envelope(canva, _sample_slides())
    assert env.payload["canva_design_id"] == "DAFinal123"
    assert env.payload["canva_design_url"] == "https://canva.com/design/DAFinal123"


# ── unit: file loading ─────────────────────────────────────────────────


def test_load_json_returns_none_for_missing_file(tmp_path: Path):
    assert _load_json(tmp_path / "nope.json") is None


def test_load_json_returns_none_for_invalid_json(tmp_path: Path):
    f = tmp_path / "bad.json"
    f.write_text("{not json")
    assert _load_json(f) is None


def test_load_json_returns_dict_for_valid_json(tmp_path: Path):
    f = tmp_path / "ok.json"
    f.write_text('{"a": 1}')
    assert _load_json(f) == {"a": 1}


# ── integration: main() with mocked Redis ──────────────────────────────


def test_main_dry_run_does_not_call_redis(tmp_path: Path, capsys):
    canva_p = tmp_path / "canva.json"
    slides_p = tmp_path / "slides.json"
    canva_p.write_text(json.dumps(_sample_canva()))
    slides_p.write_text(json.dumps(_sample_slides()))

    with patch("mata_garuda.tools.intel_publisher.publish_to_redis") as fake_pub:
        rc = main(["--canva", str(canva_p), "--slides", str(slides_p), "--dry-run"])

    assert rc == 0
    fake_pub.assert_not_called()
    output = capsys.readouterr().out
    assert "intel.article_ready" in output


def test_main_publishes_envelope_to_redis(tmp_path: Path):
    canva_p = tmp_path / "canva.json"
    slides_p = tmp_path / "slides.json"
    canva_p.write_text(json.dumps(_sample_canva()))
    slides_p.write_text(json.dumps(_sample_slides()))

    with patch("mata_garuda.tools.intel_publisher.publish_to_redis", return_value="123-0") as fake_pub:
        rc = main(["--canva", str(canva_p), "--slides", str(slides_p)])

    assert rc == 0
    fake_pub.assert_called_once()
    envelope_arg = fake_pub.call_args.args[0]
    assert isinstance(envelope_arg, Envelope)
    assert envelope_arg.type == "intel.article_ready"


def test_main_returns_1_on_missing_file(tmp_path: Path):
    rc = main(["--canva", str(tmp_path / "missing.json"), "--slides", str(tmp_path / "x.json")])
    assert rc == 1


def test_main_returns_1_on_invalid_json(tmp_path: Path):
    canva_p = tmp_path / "bad.json"
    slides_p = tmp_path / "ok.json"
    canva_p.write_text("not json {")
    slides_p.write_text(json.dumps(_sample_slides()))

    rc = main(["--canva", str(canva_p), "--slides", str(slides_p)])
    assert rc == 1

from datetime import datetime, timezone

from scripts.wa_corpus.db import ChatLine
from scripts.wa_corpus.renderer import render_markdown


def test_render_marks_team_and_counterpart():
    lines = [
        ChatLine("outbound", datetime(2026, 5, 29, tzinfo=timezone.utc), "Hello from team"),
        ChatLine("inbound", datetime(2026, 5, 29, tzinfo=timezone.utc), "Hi from client"),
    ]
    md = render_markdown("+62TEAM", "+33CP", lines)
    assert "TEAM:" in md and "COUNTERPART:" in md
    assert "Hello from team" in md and "Hi from client" in md
    assert "Message count: 2" in md


def test_render_skips_empty_bodies():
    lines = [ChatLine("inbound", None, ""), ChatLine("inbound", None, "real")]
    md = render_markdown("+62TEAM", "+33CP", lines)
    assert "real" in md
    assert md.count("COUNTERPART:") == 1

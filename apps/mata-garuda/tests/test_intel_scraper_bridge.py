"""Tests for intel_scraper_bridge agent and tools."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from mata_garuda.agents.intel_scraper_bridge import bridge_intel_scraper
from mata_garuda.tools import intel_scraper_tools as ist


def _write_articles(dir_path: Path, items: list[dict]) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    target = dir_path / ist.PUBLISHED_FILE
    target.write_text(
        json.dumps({"articles": items}, ensure_ascii=False),
        encoding="utf-8",
    )
    return target


def test_read_published_articles_missing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("BALI_INTEL_SCRAPER_DATA_DIR", str(tmp_path))
    assert ist.read_published_articles() == []


def test_read_published_articles_malformed_json(tmp_path, monkeypatch):
    (tmp_path / ist.PUBLISHED_FILE).write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("BALI_INTEL_SCRAPER_DATA_DIR", str(tmp_path))
    assert ist.read_published_articles() == []


def test_read_published_articles_happy(tmp_path, monkeypatch):
    _write_articles(
        tmp_path,
        [
            {
                "url": "https://example.com/a",
                "title": "A",
                "published_at": "2026-04-20T01:00:00",
            },
            {"title": "no url — dropped"},
        ],
    )
    monkeypatch.setenv("BALI_INTEL_SCRAPER_DATA_DIR", str(tmp_path))
    out = ist.read_published_articles()
    assert len(out) == 1
    assert out[0]["url"] == "https://example.com/a"


def test_filter_recent_lexicographic():
    items = [
        {"url": "u1", "published_at": "2026-04-19T00:00:00"},
        {"url": "u2", "published_at": "2026-04-20T12:00:00"},
        {"url": "u3"},
    ]
    cut = "2026-04-20T00:00:00"
    out = ist.filter_recent(items, cut)
    assert [a["url"] for a in out] == ["u2"]


def _stub_redis_cmd_factory(seen: set[str]):
    """Build a redis_cmd stub that answers SISMEMBER / SADD / EXPIRE."""
    def stub(*args: str, timeout: int = 10) -> str:
        if not args:
            return ""
        op = args[0].upper()
        if op == "SISMEMBER":
            _, _, member = args
            return "1" if member in seen else "0"
        if op == "SADD":
            _, _, member = args
            seen.add(member)
            return "1"
        if op == "EXPIRE":
            return "1"
        return ""
    return stub


def test_bridge_publishes_to_garuda_raw(tmp_path, monkeypatch):
    _write_articles(
        tmp_path,
        [
            {
                "url": "https://example.com/new",
                "title": "Fresh piece",
                "published_at": "2999-01-01T00:00:00",
            }
        ],
    )
    monkeypatch.setenv("BALI_INTEL_SCRAPER_DATA_DIR", str(tmp_path))

    with patch(
        "mata_garuda.agents.intel_scraper_bridge.stream_publish_redis",
        return_value="1-0",
    ) as fake_publish, patch(
        "mata_garuda.agents.intel_scraper_bridge.redis_cmd",
        side_effect=_stub_redis_cmd_factory(set()),
    ):
        result = bridge_intel_scraper()

    assert result["case_resolved"] is True
    assert result["published"] == 1
    assert result["skipped"] == 0
    fake_publish.assert_called_once()
    stream, fields = fake_publish.call_args.args
    assert stream == "garuda:raw"
    assert fields["agent"] == "intel_scraper_bridge"
    assert fields["source_agent"] == "intel_scraper_bridge"
    assert fields["source_type"] == "intel_scraper"
    assert fields["url"] == "https://example.com/new"
    assert fields["source"] == "example.com"


def test_bridge_dedup_via_redis_set(tmp_path, monkeypatch):
    """Second run with same URL must skip — Redis SET dedup."""
    _write_articles(
        tmp_path,
        [
            {
                "url": "https://example.com/same",
                "title": "Same article",
                "published_at": "2999-01-01T00:00:00",
            }
        ],
    )
    monkeypatch.setenv("BALI_INTEL_SCRAPER_DATA_DIR", str(tmp_path))

    seen: set[str] = set()
    with patch(
        "mata_garuda.agents.intel_scraper_bridge.stream_publish_redis",
        return_value="1-0",
    ) as fake_publish, patch(
        "mata_garuda.agents.intel_scraper_bridge.redis_cmd",
        side_effect=_stub_redis_cmd_factory(seen),
    ):
        first = bridge_intel_scraper()
        second = bridge_intel_scraper()

    assert first["published"] == 1 and first["skipped"] == 0
    assert second["published"] == 0 and second["skipped"] == 1
    assert second["case_resolved"] is False
    assert "already seen" in second["reason"]
    # Only one real publish across both runs.
    assert fake_publish.call_count == 1


def test_bridge_window_hours_legacy_filter(tmp_path, monkeypatch):
    """Optional legacy window_hours filter still works when set."""
    _write_articles(
        tmp_path,
        [
            {
                "url": "https://example.com/old",
                "title": "old",
                "published_at": "1970-01-01T00:00:00",
            }
        ],
    )
    monkeypatch.setenv("BALI_INTEL_SCRAPER_DATA_DIR", str(tmp_path))

    with patch(
        "mata_garuda.agents.intel_scraper_bridge.stream_publish_redis"
    ) as fake_publish, patch(
        "mata_garuda.agents.intel_scraper_bridge.redis_cmd",
        side_effect=_stub_redis_cmd_factory(set()),
    ):
        result = bridge_intel_scraper(window_hours=1)

    assert result["case_resolved"] is False
    assert result["published"] == 0
    assert "no items newer" in result["reason"]
    fake_publish.assert_not_called()


def test_bridge_file_missing(tmp_path, monkeypatch):
    # Empty dir → no file
    monkeypatch.setenv("BALI_INTEL_SCRAPER_DATA_DIR", str(tmp_path))
    with patch(
        "mata_garuda.agents.intel_scraper_bridge.stream_publish_redis"
    ) as fake_publish, patch(
        "mata_garuda.agents.intel_scraper_bridge.redis_cmd",
        side_effect=_stub_redis_cmd_factory(set()),
    ):
        result = bridge_intel_scraper()
    assert result["case_resolved"] is False
    assert "missing" in result["reason"].lower() or "empty" in result["reason"].lower()
    fake_publish.assert_not_called()


def test_bridge_content_empty_by_default(tmp_path, monkeypatch):
    """Default behavior: content="" — no network fetch. Backward compat."""
    monkeypatch.delenv("MATAGARUDA_FETCH_CONTENT", raising=False)
    _write_articles(
        tmp_path,
        [
            {
                "url": "https://example.com/a",
                "title": "A",
                "published_at": "2999-01-01T00:00:00",
            }
        ],
    )
    monkeypatch.setenv("BALI_INTEL_SCRAPER_DATA_DIR", str(tmp_path))

    with patch(
        "mata_garuda.agents.intel_scraper_bridge.stream_publish_redis",
        return_value="1-0",
    ) as fake_publish, patch(
        "mata_garuda.agents.intel_scraper_bridge.redis_cmd",
        side_effect=_stub_redis_cmd_factory(set()),
    ):
        bridge_intel_scraper()

    _, fields = fake_publish.call_args.args
    assert fields["content"] == ""


def test_bridge_fetches_content_when_env_set(tmp_path, monkeypatch):
    """MATAGARUDA_FETCH_CONTENT=1 enables HTTP fetch + HTML strip."""
    monkeypatch.setenv("MATAGARUDA_FETCH_CONTENT", "1")
    _write_articles(
        tmp_path,
        [
            {
                "url": "https://example.com/a",
                "title": "A",
                "published_at": "2999-01-01T00:00:00",
            }
        ],
    )
    monkeypatch.setenv("BALI_INTEL_SCRAPER_DATA_DIR", str(tmp_path))

    with patch(
        "mata_garuda.agents.intel_scraper_bridge.stream_publish_redis",
        return_value="1-0",
    ) as fake_publish, patch(
        "mata_garuda.agents.intel_scraper_bridge.redis_cmd",
        side_effect=_stub_redis_cmd_factory(set()),
    ), patch(
        "mata_garuda.agents.intel_scraper_bridge._fetch_article_text",
        return_value="Indonesia announced new visa rules on 12 March 2026.",
    ) as fake_fetch:
        bridge_intel_scraper()

    fake_fetch.assert_called_once_with("https://example.com/a")
    _, fields = fake_publish.call_args.args
    assert "Indonesia announced new visa rules" in fields["content"]


def test_bridge_fetch_failure_leaves_content_empty(tmp_path, monkeypatch):
    """If _fetch_article_text returns None (network/4xx/5xx), publish still
    proceeds with content="" — graceful degradation, not a hard failure."""
    monkeypatch.setenv("MATAGARUDA_FETCH_CONTENT", "1")
    _write_articles(
        tmp_path,
        [
            {
                "url": "https://example.com/a",
                "title": "A",
                "published_at": "2999-01-01T00:00:00",
            }
        ],
    )
    monkeypatch.setenv("BALI_INTEL_SCRAPER_DATA_DIR", str(tmp_path))

    with patch(
        "mata_garuda.agents.intel_scraper_bridge.stream_publish_redis",
        return_value="1-0",
    ) as fake_publish, patch(
        "mata_garuda.agents.intel_scraper_bridge.redis_cmd",
        side_effect=_stub_redis_cmd_factory(set()),
    ), patch(
        "mata_garuda.agents.intel_scraper_bridge._fetch_article_text",
        return_value=None,
    ):
        result = bridge_intel_scraper()

    assert result["case_resolved"] is True
    assert result["published"] == 1
    _, fields = fake_publish.call_args.args
    assert fields["content"] == ""


def test_strip_html_removes_tags_scripts_and_collapses_whitespace():
    from mata_garuda.agents.intel_scraper_bridge import _strip_html
    html = """
    <html><head><script>var x=1;</script><style>body{}</style><title>T</title></head>
    <body>
      <h1>Headline</h1>
      <p>Paragraph one.</p>
      <p>Paragraph    two.</p>
      <script>alert('x');</script>
    </body></html>
    """
    out = _strip_html(html)
    assert "var x" not in out
    assert "body{}" not in out
    assert "alert" not in out
    assert "<" not in out and ">" not in out
    assert "Headline" in out
    assert "Paragraph one." in out
    assert "Paragraph two." in out  # collapsed whitespace
    # No giant blank runs
    assert "    " not in out


def test_strip_html_handles_empty_input():
    from mata_garuda.agents.intel_scraper_bridge import _strip_html
    assert _strip_html("") == ""
    assert _strip_html(None) == ""  # type: ignore[arg-type]


def test_fetch_curl_uses_compressed_flag():
    """curl must run with --compressed so gzip/deflate responses are
    decoded transparently. Without it, subprocess(text=True) blows up
    with UnicodeDecodeError on byte 0x8b (gzip magic) — verified
    empirically against tempo.co on 2026-05-06 first prod run."""
    from mata_garuda.agents.intel_scraper_bridge import _fetch_article_text
    captured = {}
    fake_completed = type("R", (), {
        "returncode": 0,
        "stdout": "<html><body>hi</body></html>\n200",
        "stderr": "",
    })()
    def fake_run(cmd, *a, **kw):
        captured["cmd"] = cmd
        return fake_completed
    with patch("mata_garuda.agents.intel_scraper_bridge.subprocess.run", side_effect=fake_run):
        out = _fetch_article_text("https://example.com/foo")
    assert "--compressed" in captured["cmd"], (
        "curl invocation must include --compressed to decode gzip responses"
    )
    assert out is not None and "hi" in out


def test_fetch_swallows_unicode_decode_error():
    """If subprocess.run raises UnicodeDecodeError (e.g. server sent gzip
    bytes despite our --compressed request), the bridge must NOT crash
    — return None and let the caller publish content="" gracefully."""
    from mata_garuda.agents.intel_scraper_bridge import _fetch_article_text
    def boom(*a, **kw):
        raise UnicodeDecodeError("utf-8", b"\x1f\x8b", 1, 2, "invalid start byte")
    with patch("mata_garuda.agents.intel_scraper_bridge.subprocess.run", side_effect=boom):
        out = _fetch_article_text("https://example.com/gzip-only")
    assert out is None  # graceful: no exception, no partial content


def test_fetch_swallows_generic_exception():
    """Any other unexpected exception from curl/subprocess (e.g. OSError,
    UnicodeError variants, malformed redirect chain) must also be
    contained — bridge processes 50 URLs/run, one bad URL must NOT take
    down the whole batch."""
    from mata_garuda.agents.intel_scraper_bridge import _fetch_article_text
    def boom(*a, **kw):
        raise RuntimeError("unexpected curl crash")
    with patch("mata_garuda.agents.intel_scraper_bridge.subprocess.run", side_effect=boom):
        out = _fetch_article_text("https://example.com/weird")
    assert out is None


def test_agent_registered_and_has_genome():
    import mata_garuda.agents.intel_scraper_bridge  # noqa: F401
    from mata_garuda.registry import get_agent

    agent = get_agent("intel_scraper_bridge")
    assert agent is not None
    assert agent.layer == "harvester"
    fn_names = {fn.__name__ for fn in agent.functions}
    assert "bridge_intel_scraper" in fn_names
    assert "case_resolved" in fn_names
    assert "case_not_resolved" in fn_names

    genome = (
        Path(__file__).parent.parent
        / "mata_garuda" / "agents" / "intel_scraper_bridge_GENOME.md"
    )
    assert genome.exists()
    text = genome.read_text()
    assert "garuda:raw" in text
    assert "OSINT blindato" in text

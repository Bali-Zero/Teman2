from __future__ import annotations

from pathlib import Path


SOURCE_PATH = Path(__file__).resolve().parents[2] / "apps/evaluator/seo_auto_fixer.py"


def test_seo_auto_fixer_has_no_direct_anthropic_api_path() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")

    assert "ANTHROPIC_API_KEY" not in source
    assert "api.anthropic.com" not in source
    assert "anthropic-version" not in source
    assert "claude-haiku" not in source


def test_seo_auto_fixer_still_generates_meta_description_locally() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")

    assert "def generate_meta_description(" in source
    assert "def _truncate_meta(" in source
    assert "urllib.request.urlopen" not in source.split("def generate_meta_description(", 1)[1].split(
        "def fetch_article_from_backend(", 1
    )[0]

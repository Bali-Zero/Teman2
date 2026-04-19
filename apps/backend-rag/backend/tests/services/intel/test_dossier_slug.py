"""Tests for build_dossier_slug + categorize_topic."""

from __future__ import annotations

from uuid import UUID

from backend.services.intel.dossier_models import TopicCategory
from backend.services.intel.dossier_slug import (
    build_dossier_slug,
    categorize_topic,
    flatten_topics,
)

DID = UUID("12345678-1234-1234-1234-123456789abc")


# ── build_dossier_slug ────────────────────────────────────────


def test_slug_basic():
    slug = build_dossier_slug("Permenkumham 22/2023 art.51", DID)
    assert slug.startswith("permenkumham-22-2023-art-51-")
    # suffix = last 8 hex chars of uuid without hyphens
    assert slug.endswith("3456789abc"[-8:])


def test_slug_without_anchor_no_suffix():
    slug = build_dossier_slug("B211A extension", None)
    assert slug == "b211a-extension"


def test_slug_collapses_special_chars():
    slug = build_dossier_slug("!!! Weird -- Title ---", DID)
    assert "---" not in slug
    assert not slug.startswith("-")


def test_slug_fallback_when_topic_empty():
    slug = build_dossier_slug("", DID)
    assert slug.startswith("trend-")


def test_slug_truncates_at_60_chars():
    long = "a" * 200
    slug = build_dossier_slug(long, DID)
    # suffix adds 9 chars (-xxxxxxxx) → total <= 60 + 9 = 69
    topic_part = slug.rsplit("-", 1)[0]
    assert len(topic_part) <= 60


def test_slug_deterministic():
    assert (
        build_dossier_slug("Coretax DPP update", DID)
        == build_dossier_slug("Coretax DPP update", DID)
    )


# ── categorize_topic ──────────────────────────────────────────


def test_category_visa():
    assert categorize_topic("B211A extension rules") == TopicCategory.VISA
    assert categorize_topic("KITAS investor update") == TopicCategory.VISA


def test_category_tax():
    assert categorize_topic("Coretax DPP 2026") == TopicCategory.TAX
    assert categorize_topic("PPh 21 change") == TopicCategory.TAX


def test_category_kbli():
    assert categorize_topic("KBLI 47711 migration") == TopicCategory.KBLI
    assert categorize_topic("New OSS NIB release") == TopicCategory.KBLI


def test_category_property():
    assert categorize_topic("Hak Pakai Bali villa") == TopicCategory.PROPERTY


def test_category_compliance():
    assert categorize_topic("LKPM deadline announcement") == TopicCategory.COMPLIANCE


def test_category_crypto():
    assert categorize_topic("Crypto exchange Bappebti rule") == TopicCategory.CRYPTO


def test_category_cultural():
    assert categorize_topic("Nyepi 2026 traffic ban") == TopicCategory.CULTURAL


def test_category_falls_back_to_other():
    assert categorize_topic("random thing with no keywords") == TopicCategory.OTHER


def test_category_empty_topic():
    assert categorize_topic("") == TopicCategory.OTHER


# ── flatten_topics ────────────────────────────────────────────


def test_flatten_topics_joins_first_four():
    result = flatten_topics(["a", "b", "c", "d", "e"])
    assert result == "a · b · c · d"


def test_flatten_topics_skips_empty():
    result = flatten_topics(["a", "", "  ", "b"])
    assert result == "a · b"

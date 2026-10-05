#!/usr/bin/env python3
"""Guilt+innocence tests for the TP1 burn guard and lane-3 discovery helpers.

Born from the codex adversarial review of 2026-10-05 (REQUEST-CHANGES on commit
21d6254b04): the cap must reserve atomically, count retried attempts, and the
EN-original discovery must not misread locale-suffixed translations as sources.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tp1_burn_common import BurnGuard  # noqa: E402
import tp1_burn_translate_id as tr  # noqa: E402


def test_reserve_is_atomic_and_bounded():
    guard = BurnGuard(max_tokens=10**9, max_calls=2)
    assert guard.reserve() is True
    assert guard.reserve() is True
    assert guard.reserve() is False  # third submit refused before any work exists
    assert guard.stats()["calls"] == 2


def test_failed_attempts_count_against_cap():
    guard = BurnGuard(max_tokens=10**9, max_calls=3)
    assert guard.reserve() is True          # call 1
    assert guard.add_attempt() is True      # call 2 (retry, no usage block)
    assert guard.add_attempt() is False     # call 3 hits the cap -> over
    assert guard.ok() is False


def test_token_cap_stops_after_success():
    guard = BurnGuard(max_tokens=100, max_calls=10**9)
    assert guard.reserve() is True
    assert guard.add({"total_tokens": 60}) is True
    assert guard.add({"total_tokens": 60}) is False  # 120 >= 100
    assert guard.ok() is False


def test_discover_skips_locale_suffixed_translations(tmp_path, monkeypatch):
    articles = tmp_path / "articles"
    drafts = tmp_path / "drafts"
    (articles / "visa").mkdir(parents=True)
    (articles / "visa" / "a.mdx").write_text("body\n", encoding="utf-8")
    (articles / "visa" / "a.id.mdx").write_text("body id\n", encoding="utf-8")
    (articles / "visa" / "b.mdx").write_text("body\n", encoding="utf-8")
    (articles / "visa" / "b.it.mdx").write_text("body it\n", encoding="utf-8")
    (articles / "visa" / "c.mdx").write_text("body\n", encoding="utf-8")
    (articles / "visa" / "c.id.mdx").write_text("exists\n", encoding="utf-8")
    monkeypatch.setattr(tr, "ARTICLES", articles)
    monkeypatch.setattr(tr, "DRAFTS", drafts)
    todo = [p.name for p in tr.discover(0)]
    assert todo == ["b.mdx"]  # a has its id target; c too; b.it is a translation


def test_strip_wrap_fence_keeps_inner_fences():
    wrapped = '```mdx\nkeep ```py\ncode\n``` inner\n```'
    out = tr.strip_wrap_fence(wrapped)
    assert out == "keep ```py\ncode\n``` inner"
    assert tr.strip_wrap_fence("no fence here") == "no fence here"

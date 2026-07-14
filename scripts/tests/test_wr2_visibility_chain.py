"""Tests for the WR2 visibility chain (R1-R3 cure, docs/specs/wr2-definitiva-v1.md).

Covers the pure/local pieces of wr2_html_render_apply: durable artifact persist,
review-queue entry shape, atomic queue append with dedup, corrupt-queue refusal.
No DB, no Drive, no Telegram — tmp_path only.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    assert spec and spec.loader, f"cannot load {name}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


html = _load("wr2_html_render_apply")


def _pngs(tmp_path: Path, n: int = 3) -> list[Path]:
    src = tmp_path / "render-tmp"
    src.mkdir()
    out = []
    for i in range(1, n + 1):
        p = src / f"{i:02d}.png"
        p.write_bytes(b"\x89PNG-fake-" + bytes([i]))
        out.append(p)
    return out


def test_slugify_is_fs_safe():
    s = html._slugify("Golden Visa Attracts Rp2 Trillion — DG Immigration!")
    assert s == "golden-visa-attracts-rp2-trillion-dg-immigration"
    assert html._slugify("///") == "carousel"


def test_persist_local_artifacts_copies_and_writes_meta(tmp_path):
    pngs = _pngs(tmp_path)
    car_dir = html._persist_local_artifacts(
        draft_id="abcd1234-0000-0000-0000-000000000000", topic="Test Topic",
        png_paths=pngs, drive_url="https://drive/x", weak_count=1,
        fact_check_status="pass", out_root=tmp_path / "output",
        rendered_at="2026-07-07T12:00:00Z",
    )
    assert sorted(p.name for p in (car_dir / "slides").glob("*.png")) == ["01.png", "02.png", "03.png"]
    meta = json.loads((car_dir / "meta.json").read_text())
    assert meta["drive_url"] == "https://drive/x"
    assert meta["slide_count"] == 3 and meta["weak_slides"] == 1
    assert car_dir.name.startswith("2026-07-07-test-topic-abcd1234")
    # source PNGs still in place (copy, not move — tempdir cleanup owns them)
    assert all(p.exists() for p in pngs)


def test_queue_append_and_exact_id_dedup(tmp_path):
    qp = tmp_path / "queue" / "human-review-queue.json"
    entry = html._make_queue_entry(
        draft_id="d1", topic="A Topic", carousel_dir=tmp_path / "car",
        drive_url="https://drive/y", slide_count=5, weak_count=0,
        fact_check_status="degraded", drafted_at="2026-07-07T12:00:00Z",
    )
    assert entry["state"] == "drafted"
    assert entry["state_history"][0]["by"] == "wr2-html-apply"
    assert entry["critic_overall_verdict"] == "legibility_only_pass"

    assert html._append_review_queue(entry, queue_path=qp) is True
    # SAME render batch re-applied (identical id) → pure dup, skip
    assert html._append_review_queue(dict(entry), queue_path=qp) is False
    queue = json.loads(qp.read_text())
    assert len(queue) == 1 and queue[0]["draft_id"] == "d1"


def test_queue_entry_never_writes_bare_pass_or_soft_fail(tmp_path):
    """INNOCENCE (spec §4a): a queue entry built with weak_count=0 must contain
    the honest legibility_only_pass value and never the bare "pass" string
    (which would be indistinguishable from a real constitution-critic verdict
    to every downstream consumer — the app, the analyst, reflexion). Regex/
    substring check on the SERIALIZED entry, not just dict equality, so a
    future edit that reintroduces the bare value by accident (e.g. concatenating
    a legacy string somewhere) is caught even if it doesn't touch this exact
    key."""
    import re

    entry = html._make_queue_entry(
        draft_id="d5", topic="E", carousel_dir=tmp_path / "car", drive_url="u",
        slide_count=2, weak_count=0, fact_check_status="pass",
        drafted_at="2026-07-14T10:00:00Z",
    )
    assert entry["critic_overall_verdict"] == "legibility_only_pass"
    serialized = json.dumps(entry)
    # the bare "pass" string must never appear as critic_overall_verdict's
    # value — only as a substring of the honest legibility_only_pass value
    # (fact_check_status="pass" is a DIFFERENT field, deliberately untouched
    # by this rename — §1 of the edit spec).
    assert not re.search(r'"critic_overall_verdict"\s*:\s*"pass"', serialized)
    assert not re.search(r'"critic_overall_verdict"\s*:\s*"soft_fail"', serialized)


def test_queue_rerender_repoints_drafted_entry_in_place(tmp_path):
    """GUILT (W82 exist-not-content): before the repoint existed, a re-rendered
    draft kept its queue entry pointed at the OLD slides_dir forever."""
    qp = tmp_path / "queue" / "human-review-queue.json"
    first = html._make_queue_entry(
        draft_id="d1", topic="A Topic", carousel_dir=tmp_path / "car-old",
        drive_url="https://drive/old", slide_count=5, weak_count=2,
        fact_check_status="degraded", drafted_at="2026-07-07T12:00:00Z",
    )
    assert html._append_review_queue(first, queue_path=qp) is True
    # re-render: same draft, NEW batch (new drafted_at → new id), fresh artifacts
    second = html._make_queue_entry(
        draft_id="d1", topic="A Topic", carousel_dir=tmp_path / "car-new",
        drive_url="https://drive/new", slide_count=6, weak_count=0,
        fact_check_status="pass", drafted_at="2026-07-08T09:00:00Z",
    )
    assert second["id"] != first["id"]
    assert html._append_review_queue(second, queue_path=qp) is True
    queue = json.loads(qp.read_text())
    assert len(queue) == 1  # never double-queued
    item = queue[0]
    # identity survives (ref_code stability): id + drafted_at are the ORIGINAL ones
    assert item["id"] == first["id"]
    assert item["drafted_at"] == "2026-07-07T12:00:00Z"
    # content repointed to the fresh render
    assert item["slides_dir"] == str(tmp_path / "car-new" / "slides")
    assert item["carousel_path"] == str(tmp_path / "car-new")
    assert item["drive_url"] == "https://drive/new"
    assert item["slide_count"] == 6
    assert item["critic_overall_verdict"] == "legibility_only_pass"
    # breadcrumb: the repoint is visible in state_history
    assert item["state_history"][-1]["by"] == "wr2-html-apply-rerender"
    assert item["state_history"][-1]["at"] == "2026-07-08T09:00:00Z"
    assert len(item["state_history"]) == 2


def test_queue_rejected_entry_repoints_and_resets_to_drafted(tmp_path):
    """GUILT (Codex 2026-07-13): rejected/needs-edit/reviewed are PRE-publish —
    a re-render after a rejection must repoint AND go back through review;
    equating them to published would strand the corrected carousel."""
    qp = tmp_path / "queue" / "human-review-queue.json"
    rejected = html._make_queue_entry(
        draft_id="d1", topic="A Topic", carousel_dir=tmp_path / "car-old",
        drive_url="https://drive/old", slide_count=5, weak_count=0,
        fact_check_status="pass", drafted_at="2026-07-07T12:00:00Z",
    )
    rejected["state"] = "rejected"
    qp.parent.mkdir(parents=True, exist_ok=True)
    qp.write_text(json.dumps([rejected]))
    second = html._make_queue_entry(
        draft_id="d1", topic="A Topic", carousel_dir=tmp_path / "car-new",
        drive_url="https://drive/new", slide_count=6, weak_count=0,
        fact_check_status="pass", drafted_at="2026-07-08T09:00:00Z",
    )
    assert html._append_review_queue(second, queue_path=qp) is True
    queue = json.loads(qp.read_text())
    assert len(queue) == 1
    item = queue[0]
    assert item["state"] == "drafted"  # re-enters review — old verdict is void
    assert item["slides_dir"] == str(tmp_path / "car-new" / "slides")
    assert item["id"] == rejected["id"]


def test_queue_published_entry_is_never_repointed(tmp_path):
    """INNOCENCE: published history is immutable — a re-render of an already
    published draft must not rewrite what went live."""
    qp = tmp_path / "queue" / "human-review-queue.json"
    published = html._make_queue_entry(
        draft_id="d1", topic="A Topic", carousel_dir=tmp_path / "car-old",
        drive_url="https://drive/old", slide_count=5, weak_count=0,
        fact_check_status="pass", drafted_at="2026-07-07T12:00:00Z",
    )
    published["state"] = "published"
    qp.parent.mkdir(parents=True, exist_ok=True)
    qp.write_text(json.dumps([published]))
    second = html._make_queue_entry(
        draft_id="d1", topic="A Topic", carousel_dir=tmp_path / "car-new",
        drive_url="https://drive/new", slide_count=6, weak_count=0,
        fact_check_status="pass", drafted_at="2026-07-08T09:00:00Z",
    )
    assert html._append_review_queue(second, queue_path=qp) is False
    queue = json.loads(qp.read_text())
    assert len(queue) == 1
    assert queue[0]["drive_url"] == "https://drive/old"
    assert queue[0]["slides_dir"] == str(tmp_path / "car-old" / "slides")


def test_queue_appends_preserve_existing_items(tmp_path):
    qp = tmp_path / "human-review-queue.json"
    qp.write_text(json.dumps([{"id": "legacy-1", "state": "published"}]))
    entry = html._make_queue_entry(
        draft_id="d2", topic="B", carousel_dir=tmp_path, drive_url="u",
        slide_count=1, weak_count=2, fact_check_status=None,
        drafted_at="2026-07-07T13:00:00Z",
    )
    assert entry["critic_overall_verdict"] == "legibility_soft_fail"
    assert html._append_review_queue(entry, queue_path=qp) is True
    queue = json.loads(qp.read_text())
    assert [i["id"] for i in queue][0] == "legacy-1" and len(queue) == 2


def test_corrupt_queue_is_refused_not_rebuilt(tmp_path):
    qp = tmp_path / "human-review-queue.json"
    qp.write_text("{not json")
    entry = html._make_queue_entry(
        draft_id="d3", topic="C", carousel_dir=tmp_path, drive_url="u",
        slide_count=1, weak_count=0, fact_check_status="pass",
        drafted_at="2026-07-07T14:00:00Z",
    )
    with pytest.raises(ValueError):  # json.JSONDecodeError is a ValueError
        html._append_review_queue(entry, queue_path=qp)
    # the corrupt file was NOT clobbered
    assert qp.read_text() == "{not json"


def test_non_array_queue_is_refused(tmp_path):
    qp = tmp_path / "human-review-queue.json"
    qp.write_text(json.dumps({"items": []}))
    entry = html._make_queue_entry(
        draft_id="d4", topic="D", carousel_dir=tmp_path, drive_url="u",
        slide_count=1, weak_count=0, fact_check_status="pass",
        drafted_at="2026-07-07T15:00:00Z",
    )
    with pytest.raises(ValueError):
        html._append_review_queue(entry, queue_path=qp)

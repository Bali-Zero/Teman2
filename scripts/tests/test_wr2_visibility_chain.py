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


def test_queue_append_and_dedup(tmp_path):
    qp = tmp_path / "queue" / "human-review-queue.json"
    entry = html._make_queue_entry(
        draft_id="d1", topic="A Topic", carousel_dir=tmp_path / "car",
        drive_url="https://drive/y", slide_count=5, weak_count=0,
        fact_check_status="degraded", drafted_at="2026-07-07T12:00:00Z",
    )
    assert entry["state"] == "drafted"
    assert entry["state_history"][0]["by"] == "wr2-html-apply"
    assert entry["critic_overall_verdict"] == "pass"

    assert html._append_review_queue(entry, queue_path=qp) is True
    # same draft again (re-render) → dedup skip, still one item
    assert html._append_review_queue(dict(entry, id="other-id"), queue_path=qp) is False
    queue = json.loads(qp.read_text())
    assert len(queue) == 1 and queue[0]["draft_id"] == "d1"


def test_queue_appends_preserve_existing_items(tmp_path):
    qp = tmp_path / "human-review-queue.json"
    qp.write_text(json.dumps([{"id": "legacy-1", "state": "published"}]))
    entry = html._make_queue_entry(
        draft_id="d2", topic="B", carousel_dir=tmp_path, drive_url="u",
        slide_count=1, weak_count=2, fact_check_status=None,
        drafted_at="2026-07-07T13:00:00Z",
    )
    assert entry["critic_overall_verdict"] == "soft_fail"
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
    with pytest.raises(Exception):
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

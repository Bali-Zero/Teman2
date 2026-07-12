"""Tests for wr2_queue_hygiene (W96) + the _publish_visibility junk guard.

Guilt AND innocence per scar family #3: every predicate is exercised on the
junk shape it must catch AND on the nearest legitimate neighbor it must spare.
tmp_path only — no DB, no Drive, no Telegram.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock

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


hyg = _load("wr2_queue_hygiene")
html = _load("wr2_html_render_apply")


# ── fixtures: the REAL shapes observed in production 2026-07-13 ──────────────

def _junk_entry(entry_id: str = "carousel_2026-07-12T23:12:04Z_carousel") -> dict:
    """The leaked-test shape: empty topic, slug 'carousel', 1 slide, drive/x."""
    return {
        "id": entry_id,
        "draft_id": "ffbd313e-35db-4237-ac90-fb74b2b89929",
        "topic_slug": "carousel",
        "topic": "",
        "drafted_at": "2026-07-12T23:12:04Z",
        "carousel_path": "/Users/nuzantara/Desktop/x/2026-07-12-carousel-ffbd313e",
        "drive_url": "https://drive/x",
        "media_type": "carousel",
        "slide_count": 1,
        "state": "drafted",
        "instagram_post_url": None,
    }


def _legit_entry() -> dict:
    return {
        "id": "carousel_2026-07-07T14:10:11Z_itas-vs-kitas",
        "draft_id": "b713c8fc-3053-411b-9932-769a5e63182b",
        "topic_slug": "itas-vs-kitas",
        "topic": "ITAS vs KITAS in Bali",
        "state": "drafted",
        "slide_count": 9,
        "instagram_post_url": None,
    }


def _old_schema_entry() -> dict:
    """Pre-2026-07 schema: NO 'topic' key at all — absence is not emptiness."""
    return {
        "id": "carousel_2026-06-25T12:42:00Z_indonesia-visafree-myth-reality",
        "topic_slug": "indonesia-visafree-myth-reality",
        "state": "drafted",
        "slide_count": 8,
        "instagram_post_url": None,
    }


# ── is_junk_entry: guilt ─────────────────────────────────────────────────────

def test_junk_entry_empty_topic_is_junk():
    assert hyg.is_junk_entry(_junk_entry()) is True


def test_junk_entry_whitespace_topic_is_junk():
    e = _junk_entry()
    e["topic"] = "   "
    assert hyg.is_junk_entry(e) is True


# ── is_junk_entry: innocence ─────────────────────────────────────────────────

def test_legit_drafted_entry_is_not_junk():
    assert hyg.is_junk_entry(_legit_entry()) is False


def test_old_schema_entry_without_topic_key_is_not_junk():
    assert hyg.is_junk_entry(_old_schema_entry()) is False


def test_published_entry_is_never_junk_even_with_empty_topic():
    e = _junk_entry()
    e["state"] = "published"
    assert hyg.is_junk_entry(e) is False


def test_entry_with_ig_url_is_never_junk():
    e = _junk_entry()
    e["instagram_post_url"] = "https://instagram.com/p/abc/"
    assert hyg.is_junk_entry(e) is False


def test_non_dict_entry_is_not_junk():
    assert hyg.is_junk_entry("garbage") is False


# ── sweep_queue ──────────────────────────────────────────────────────────────

def _write_queue(tmp_path: Path, items: list) -> Path:
    qp = tmp_path / "queue" / "human-review-queue.json"
    qp.parent.mkdir(parents=True)
    qp.write_text(json.dumps(items), encoding="utf-8")
    return qp


def test_sweep_moves_junk_and_keeps_legit(tmp_path):
    qp = _write_queue(tmp_path, [_junk_entry("j1"), _legit_entry(), _old_schema_entry()])
    report = hyg.sweep_queue(qp, dry_run=False)
    assert report.moved == ["j1"]
    assert report.kept == 2
    remaining = json.loads(qp.read_text())
    assert [e["id"] for e in remaining] == [_legit_entry()["id"], _old_schema_entry()["id"]]
    quarantine = json.loads(qp.with_name("queue-quarantine.json").read_text())
    assert [e["id"] for e in quarantine] == ["j1"]


def test_sweep_dry_run_mutates_nothing(tmp_path):
    qp = _write_queue(tmp_path, [_junk_entry("j1"), _legit_entry()])
    before = qp.read_text()
    report = hyg.sweep_queue(qp, dry_run=True)
    assert report.moved == ["j1"] and report.dry_run is True
    assert qp.read_text() == before
    assert not qp.with_name("queue-quarantine.json").exists()


def test_sweep_appends_to_existing_quarantine(tmp_path):
    qp = _write_queue(tmp_path, [_junk_entry("j1")])
    hyg.sweep_queue(qp, dry_run=False)
    _write_queue_items = json.loads(qp.read_text())
    assert _write_queue_items == []
    qp.write_text(json.dumps([_junk_entry("j2")]), encoding="utf-8")
    hyg.sweep_queue(qp, dry_run=False)
    quarantine = json.loads(qp.with_name("queue-quarantine.json").read_text())
    assert [e["id"] for e in quarantine] == ["j1", "j2"]


def test_sweep_missing_queue_is_noop(tmp_path):
    report = hyg.sweep_queue(tmp_path / "nope.json", dry_run=False)
    assert report.moved == [] and report.kept == 0


def test_sweep_refuses_non_list_queue(tmp_path):
    qp = tmp_path / "q.json"
    qp.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    report = hyg.sweep_queue(qp, dry_run=False)
    assert report.moved == []
    assert json.loads(qp.read_text()) == {"not": "a list"}  # untouched


# ── is_junk_dir / purge_junk_dirs ────────────────────────────────────────────

def _mk_dir(root: Path, name: str, *, topic: str, drive_url: str, pngs: int) -> Path:
    d = root / "carousel" / name
    (d / "slides").mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"topic": topic, "drive_url": drive_url}))
    for i in range(pngs):
        (d / "slides" / f"{i + 1:02d}.png").write_bytes(b"PNG")
    return d


def test_junk_dir_guilt(tmp_path):
    d = _mk_dir(tmp_path, "2026-07-12-carousel-abcdef12",
                topic="", drive_url="https://drive/x", pngs=1)
    assert hyg.is_junk_dir(d) is True


def test_junk_named_dir_without_meta_and_no_slides_is_junk(tmp_path):
    d = tmp_path / "carousel" / "2026-07-11-carousel-00ff00aa"
    d.mkdir(parents=True)
    assert hyg.is_junk_dir(d) is True


def test_real_carousel_dir_is_innocent_by_name(tmp_path):
    d = _mk_dir(tmp_path, "2026-07-07-itas-vs-kitas-in-bali-b713c8fc",
                topic="ITAS vs KITAS in Bali", drive_url="https://drive.google.com/x", pngs=9)
    assert hyg.is_junk_dir(d) is False


def test_junk_named_dir_with_many_slides_is_spared(tmp_path):
    # even a suspicious name is spared when it holds a real slide deck
    d = _mk_dir(tmp_path, "2026-07-10-carousel-11111111",
                topic="", drive_url="https://drive/x", pngs=8)
    assert hyg.is_junk_dir(d) is False


def test_junk_named_dir_with_real_meta_is_spared(tmp_path):
    d = _mk_dir(tmp_path, "2026-07-10-carousel-22222222",
                topic="Carousel regulations digest", drive_url="https://drive.google.com/d/1", pngs=1)
    assert hyg.is_junk_dir(d) is False


def test_purge_junk_dirs_deletes_only_guilty(tmp_path):
    guilty = _mk_dir(tmp_path, "2026-07-12-carousel-abcdef12",
                     topic="", drive_url="https://drive/x", pngs=1)
    innocent = _mk_dir(tmp_path, "2026-07-07-itas-vs-kitas-b713c8fc",
                       topic="ITAS vs KITAS", drive_url="https://drive.google.com/x", pngs=9)
    purged = hyg.purge_junk_dirs(tmp_path, dry_run=False)
    assert purged == ["2026-07-12-carousel-abcdef12"]
    assert not guilty.exists() and innocent.exists()


def test_purge_dry_run_deletes_nothing(tmp_path):
    guilty = _mk_dir(tmp_path, "2026-07-12-carousel-abcdef12",
                     topic="", drive_url="https://drive/x", pngs=1)
    purged = hyg.purge_junk_dirs(tmp_path, dry_run=True)
    assert purged == ["2026-07-12-carousel-abcdef12"] and guilty.exists()


# ── _publish_visibility W96 guard (guilt + innocence) ────────────────────────

@pytest.mark.asyncio
async def test_publish_visibility_refuses_empty_topic(tmp_path, monkeypatch):
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path / "out"))
    alert = AsyncMock()
    monkeypatch.setattr(html, "_ops_alert", alert)
    monkeypatch.setattr(html, "_tg_notify", lambda *a, **k: True)
    png = tmp_path / "01.png"
    png.write_bytes(b"PNG")
    await html._publish_visibility(
        draft_id="d-guilty", topic="", png_paths=[png],
        drive_url="https://drive/x", weak_count=0, fact_check_status=None,
    )
    alert.assert_awaited_once()
    assert not (tmp_path / "out" / "queue" / "human-review-queue.json").exists()
    assert not (tmp_path / "out" / "carousel").exists()


@pytest.mark.asyncio
async def test_publish_visibility_refuses_zero_slides(tmp_path, monkeypatch):
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path / "out"))
    alert = AsyncMock()
    monkeypatch.setattr(html, "_ops_alert", alert)
    monkeypatch.setattr(html, "_tg_notify", lambda *a, **k: True)
    await html._publish_visibility(
        draft_id="d-empty", topic="A real topic", png_paths=[],
        drive_url="https://drive.google.com/x", weak_count=0, fact_check_status=None,
    )
    alert.assert_awaited_once()
    assert not (tmp_path / "out" / "queue" / "human-review-queue.json").exists()


@pytest.mark.asyncio
async def test_publish_visibility_accepts_legit_draft(tmp_path, monkeypatch):
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path / "out"))
    alert = AsyncMock()
    monkeypatch.setattr(html, "_ops_alert", alert)
    monkeypatch.setattr(html, "_tg_notify", lambda *a, **k: True)
    pngs = []
    for i in range(3):
        p = tmp_path / f"{i + 1:02d}.png"
        p.write_bytes(b"PNG")
        pngs.append(p)
    await html._publish_visibility(
        draft_id="d-legit", topic="ITAS vs KITAS in Bali", png_paths=pngs,
        drive_url="https://drive.google.com/x", weak_count=0, fact_check_status="pass",
    )
    alert.assert_not_awaited()
    qp = tmp_path / "out" / "queue" / "human-review-queue.json"
    queue = json.loads(qp.read_text())
    assert len(queue) == 1 and queue[0]["topic"] == "ITAS vs KITAS in Bali"
    assert queue[0]["slide_count"] == 3 and queue[0]["state"] == "drafted"

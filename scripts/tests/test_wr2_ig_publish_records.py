"""Tests for the A4 publish-record helpers in wr2_ig_publish (file-based pieces).

Spec: docs/specs/wr2-definitiva-v1.md R4 — war_room_posts and the review-queue
entry are the learning loops' food; both were empty forever. DB writes are
covered by their simple SQL + best-effort contract; these tests pin the local
file logic (meta.json draft-id read, queue publish-mark with lock + matching).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

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


pub = _load("wr2_ig_publish")


def _with_root(monkeypatch, tmp_path: Path) -> Path:
    """Point the CLI's carousel root at a tmp output tree."""
    out = tmp_path / "output"
    (out / "carousel").mkdir(parents=True)
    monkeypatch.setattr(pub, "_carousel_root", lambda: out / "carousel")
    return out


def test_read_meta_draft_id(tmp_path, monkeypatch):
    out = _with_root(monkeypatch, tmp_path)
    slug_dir = out / "carousel" / "2026-07-07-topic-abcd1234"
    slug_dir.mkdir()
    (slug_dir / "meta.json").write_text(json.dumps({"draft_id": "d-real-uuid"}))
    assert pub._read_meta_draft_id("2026-07-07-topic-abcd1234") == "d-real-uuid"


def test_read_meta_draft_id_legacy_dir_returns_none(tmp_path, monkeypatch):
    out = _with_root(monkeypatch, tmp_path)
    (out / "carousel" / "legacy-slug").mkdir()
    assert pub._read_meta_draft_id("legacy-slug") is None


def test_mark_queue_published_by_draft_id(tmp_path, monkeypatch):
    out = _with_root(monkeypatch, tmp_path)
    qdir = out / "queue"
    qdir.mkdir()
    qp = qdir / "human-review-queue.json"
    qp.write_text(json.dumps([
        {"id": "a", "draft_id": "d1", "state": "drafted", "state_history": []},
        {"id": "b", "draft_id": "d2", "state": "drafted"},
    ]))
    pub._mark_queue_published(slug="whatever", draft_id="d2", permalink="https://ig/p/1")
    queue = json.loads(qp.read_text())
    assert queue[1]["state"] == "published"
    assert queue[1]["instagram_post_url"] == "https://ig/p/1"
    assert queue[1]["state_history"][-1]["by"] == "wr2_ig_publish"
    # the other entry untouched
    assert queue[0]["state"] == "drafted"


def test_mark_queue_published_by_slug_fallback(tmp_path, monkeypatch):
    out = _with_root(monkeypatch, tmp_path)
    qdir = out / "queue"
    qdir.mkdir()
    qp = qdir / "human-review-queue.json"
    qp.write_text(json.dumps([
        {"id": "x", "topic_slug": "my-carousel", "state": "drafted"},
    ]))
    pub._mark_queue_published(slug="my-carousel", draft_id=None, permalink="https://ig/p/2")
    queue = json.loads(qp.read_text())
    assert queue[0]["state"] == "published"


def test_mark_queue_published_no_match_is_noop(tmp_path, monkeypatch):
    out = _with_root(monkeypatch, tmp_path)
    qdir = out / "queue"
    qdir.mkdir()
    qp = qdir / "human-review-queue.json"
    original = [{"id": "y", "topic_slug": "other", "state": "drafted"}]
    qp.write_text(json.dumps(original))
    pub._mark_queue_published(slug="nope", draft_id="dz", permalink="u")
    assert json.loads(qp.read_text()) == original


def test_mark_queue_missing_file_is_noop(tmp_path, monkeypatch):
    _with_root(monkeypatch, tmp_path)
    # no queue file at all — must not raise
    pub._mark_queue_published(slug="s", draft_id=None, permalink="u")
